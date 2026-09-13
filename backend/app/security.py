import os, secrets as random, hashlib
import jwt
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from sqlalchemy import select, insert, delete
from .db import engine
from .schema import sessions, owners, secrets, now

hasher = PasswordHasher()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def signing_key():
    raw = os.getenv("ENCRYPTION_KEY")
    if not raw:
        raise HTTPException(503, "Encryption key is not configured on the API")
    return hashlib.sha256(b"life-os/session-signing/v1/" + raw.encode()).digest()


def issue_session(owner_id, expires):
    return jwt.encode(
        {
            "sub": str(owner_id),
            "iss": "life-os",
            "aud": "life-os-owner",
            "iat": now(),
            "exp": expires,
            "jti": random.token_urlsafe(24),
        },
        signing_key(),
        algorithm="HS256",
    )


def cipher():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise HTTPException(503, "Encryption key is not configured on the API")
    try:
        return Fernet(key.encode())
    except ValueError:
        raise HTTPException(503, "Encryption key is invalid")


def put_secret(conn, name, value):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    encrypted = cipher().encrypt(value.encode()).decode()
    conn.execute(
        pg_insert(secrets)
        .values(name=name, ciphertext=encrypted)
        .on_conflict_do_update(
            index_elements=[secrets.c.name],
            set_={"ciphertext": encrypted, "updated_at": now()},
        )
    )


def get_secret(conn, name):
    val = conn.execute(
        select(secrets.c.ciphertext).where(secrets.c.name == name)
    ).scalar_one_or_none()
    return cipher().decrypt(val.encode()).decode() if val else None


def owner(request: Request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(401, "Please sign in")
    try:
        claims = jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            issuer="life-os",
            audience="life-os-owner",
            options={"require": ["exp", "sub", "jti", "iat"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    with engine.connect() as conn:
        session = (
            conn.execute(
                select(sessions).where(
                    sessions.c.token_hash == digest(token),
                    sessions.c.expires_at > now(),
                )
            )
            .mappings()
            .first()
        )
    if not session or str(session["owner_id"]) != claims["sub"]:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return session["owner_id"]


def trigger_auth(request: Request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    with engine.connect() as conn:
        expected = get_secret(conn, "digest_token")
    if expected and random.compare_digest(token, expected):
        return True
    owner(request)
    return True
