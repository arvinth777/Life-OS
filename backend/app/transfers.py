"""One owner transfer at a time, durable across serverless restarts.

Each HTTP body is at most 1 MB. Chunks are encrypted in PostgreSQL, expire
after one hour, and are deleted on completion/cancel or the next transfer.
The download snapshot includes every table, including the empty transfer
table, before its own transport row is created. Restore remains atomic.
"""

import hashlib
import math
import uuid
import zipfile
from datetime import timedelta
import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import Response
from .db import engine
from .schema import backup_transfers as table, now
from .security import owner, cipher
from .backup import export_data, archive, restore, parse_backup

router = APIRouter(prefix="/api/transfers")
CHUNK = 1_000_000
MAX_SIZE = 25_000_000


def vacant(conn):
    # Serialize creation before selecting a repeatable-read export snapshot.
    conn.exec_driver_sql("LOCK TABLE backup_transfers IN EXCLUSIVE MODE")
    conn.execute(sa.delete(table).where(table.c.expires_at <= now()))
    if conn.execute(sa.select(table.c.id).limit(1)).first():
        raise HTTPException(
            409,
            "Another backup transfer is in progress. Finish or cancel it, or retry after one hour.",
        )


def locked(conn, key, identity, direction=None):
    row = (
        conn.execute(
            sa.select(table)
            .where(table.c.id == key, table.c.owner_id == identity)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not row or row["expires_at"] <= now():
        raise HTTPException(404, "Backup transfer expired. Start again.")
    if direction and row["direction"] != direction:
        raise HTTPException(409, "Wrong transfer direction")
    return row


def info(row):
    return {
        "id": str(row["id"]),
        "size": row["size"],
        "sha256": row["sha256"],
        "chunk_size": CHUNK,
        "count": math.ceil(row["size"] / CHUNK),
    }


@router.post("/download")
def start_download(identity=Depends(owner)):
    with engine.begin() as conn:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        vacant(conn)
        raw = archive(export_data(conn, set_isolation=False))
        if len(raw) > MAX_SIZE:
            raise HTTPException(
                413,
                "Backup exceeds the 25 MB browser transfer limit; use the documented CLI export.",
            )
        chunks = {
            str(i // CHUNK): cipher().encrypt(raw[i : i + CHUNK]).decode()
            for i in range(0, len(raw), CHUNK)
        }
        row = (
            conn.execute(
                sa.insert(table)
                .values(
                    owner_id=identity,
                    direction="download",
                    size=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    chunks=chunks,
                    expires_at=now() + timedelta(hours=1),
                )
                .returning(table)
            )
            .mappings()
            .one()
        )
        return info(row)


@router.get("/{key}/chunks/{index}")
def download_chunk(key: uuid.UUID, index: int, identity=Depends(owner)):
    with engine.begin() as conn:
        row = locked(conn, key, identity, "download")
        encrypted = row["chunks"].get(str(index))
        if encrypted is None:
            raise HTTPException(404, "Chunk does not exist")
        return Response(
            cipher().decrypt(encrypted.encode()), media_type="application/octet-stream"
        )


@router.post("/upload")
def start_upload(payload: dict = Body(...), identity=Depends(owner)):
    size, sha = payload.get("size"), payload.get("sha256", "")
    if type(size) is not int or not 0 < size <= MAX_SIZE:
        raise ValueError("Backup must be between 1 byte and 25 MB")
    if (
        not isinstance(sha, str)
        or len(sha) != 64
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise ValueError("A SHA-256 checksum is required")
    with engine.begin() as conn:
        vacant(conn)
        row = (
            conn.execute(
                sa.insert(table)
                .values(
                    owner_id=identity,
                    direction="upload",
                    size=size,
                    sha256=sha,
                    chunks={},
                    expires_at=now() + timedelta(hours=1),
                )
                .returning(table)
            )
            .mappings()
            .one()
        )
        return info(row)


@router.post("/{key}/chunks/{index}")
async def upload_chunk(
    key: uuid.UUID, index: int, request: Request, identity=Depends(owner)
):
    raw = await request.body()
    if not 0 < len(raw) <= CHUNK:
        raise HTTPException(413, "Chunk exceeds 1 MB or is empty")
    with engine.begin() as conn:
        row = locked(conn, key, identity, "upload")
        if not 0 <= index < math.ceil(row["size"] / CHUNK):
            raise ValueError("Chunk index is outside the backup")
        if len(raw) != min(CHUNK, row["size"] - index * CHUNK):
            raise ValueError("Chunk has the wrong size")
        chunks = dict(row["chunks"])
        if (
            str(index) in chunks
            and cipher().decrypt(chunks[str(index)].encode()) != raw
        ):
            raise HTTPException(409, "A different chunk already occupies this position")
        chunks[str(index)] = cipher().encrypt(raw).decode()
        conn.execute(
            sa.update(table)
            .where(table.c.id == key)
            .values(chunks=chunks, updated_at=now())
        )
    return {"ok": True}


@router.post("/{key}/restore")
def finish_upload(key: uuid.UUID, replace: bool = False, identity=Depends(owner)):
    if not replace:
        raise ValueError("Confirm replacement before restoring")
    try:
        with engine.begin() as conn:
            row = locked(conn, key, identity, "upload")
            count = math.ceil(row["size"] / CHUNK)
            if set(row["chunks"]) != {str(i) for i in range(count)}:
                raise ValueError("Backup upload is incomplete")
            raw = b"".join(
                cipher().decrypt(row["chunks"][str(i)].encode()) for i in range(count)
            )
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Backup checksum does not match")
            restore(conn, parse_backup(raw), replace=True)
            conn.execute(sa.delete(table).where(table.c.id == key))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, TypeError):
        raise ValueError("Backup archive is invalid or missing required files")
    return {"ok": True}


@router.delete("/{key}")
def cancel(key: uuid.UUID, identity=Depends(owner)):
    with engine.begin() as conn:
        conn.execute(
            sa.delete(table).where(table.c.id == key, table.c.owner_id == identity)
        )
    return {"ok": True}
