"""Opt-in private cloud reads, one resumable page per request, no disk credentials.

Unknown numeric fields stay explicitly raw. A manifest named stress does not
establish that its numbers use Samsung's visible scale; no scale is invented.
"""
import json
import math
import time
import hashlib
from datetime import datetime, timezone
from importlib.resources import files
import httpx
import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException
from ..db import engine
from .. import schema as s
from ..security import owner, get_secret
from ..services import config, setting, ingest
from .samsung_storage import SecretSlot, EncryptedStateStore, read_json, write_json, secure_unlink

router = APIRouter(prefix="/api/integrations/samsung", dependencies=[Depends(owner)])
LOCK = 71003248


def lock(conn):
    return conn.execute(sa.text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK}).scalar()


@router.post("/auth/start")
def start(payload: dict = Body(default={})):
    from .samsung_account import AccountBootstrap
    country = payload.get("country", "us")
    if not isinstance(country, str) or len(country) != 2 or not country.isalpha():
        raise ValueError("Use the two-letter Samsung account country code")
    try:
        with engine.begin() as conn:
            if not lock(conn):
                raise HTTPException(409, "A Samsung request is already running")
            with AccountBootstrap(conn=conn) as auth:
                return {"login_url": auth.start(country=country), "expires_in": 900}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Samsung sign-in could not start. Try again later.") from None


@router.post("/auth/finish")
def finish(payload: dict = Body(...)):
    from .samsung_account import AccountBootstrap
    try:
        with engine.begin() as conn:
            if not lock(conn):
                raise HTTPException(409, "A Samsung request is already running")
            with AccountBootstrap(conn=conn) as auth:
                result = auth.complete(payload.get("callback", ""))
            secure_unlink(SecretSlot(conn, "samsung_cursor"))
            secure_unlink(SecretSlot(conn, "samsung_session"))
            setting(conn, "samsung_cloud", {"enabled": True, "interval_minutes": 60})
            return result
    except HTTPException:
        raise
    except Exception as exc:
        # Classify known failures without returning callback data or provider bodies.
        message = str(exc).lower()
        reason = "unexpected_response"
        for phrase, code in (("expired", "expired"), ("missing or duplicates", "incomplete_callback"), ("decrypt", "invalid_callback"), ("callback target", "unexpected_callback"), ("network request failed", "provider_unreachable"), ("failed with http", "provider_rejected"), ("untrusted", "unexpected_provider"), ("omitted master", "missing_credentials")):
            if phrase in message:
                reason = code
                break
        raise HTTPException(400, {"message": "Samsung sign-in did not complete", "reason": reason}) from None


@router.post("/disconnect")
def disconnect():
    with engine.begin() as conn:
        if not lock(conn):
            raise HTTPException(409, "A Samsung request is already running")
        for name in ("samsung_master", "samsung_pending", "samsung_session", "samsung_cursor"):
            secure_unlink(SecretSlot(conn, name))
        setting(conn, "samsung_cloud", {"enabled": False, "interval_minutes": 60})
    return {"connected": False}


def normalize_documents(documents, manifest):
    # Preserve numeric source fields separately from validated UI metrics.
    # Raw fields are not used for targets, health advice, or daily sums.
    excluded = {"start_time", "end_time", "create_time", "update_time", "day_time", "time_offset", "deviceuuid", "datauuid", "id", "uuid", "latitude", "longitude", "altitude"}
    records, skipped = [], 0
    for document in documents:
        data = document.get("data", {})
        if document.get("needToDecrypt") or not isinstance(data, dict):
            skipped += 1
            continue
        ident = next((data.get(k) for k in ("datauuid", "uuid", "id") if isinstance(data.get(k), str) and data[k]), None)
        stamp = next((data.get(k) for k in ("start_time", "end_time", "create_time") if isinstance(data.get(k), (int, float)) and not isinstance(data[k], bool)), None)
        if ident is None or stamp is None:
            skipped += 1
            continue
        try:
            at = datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            skipped += 1
            continue
        for field, value in data.items():
            if field in excluded or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            metric = "samsung_raw/" + manifest.removeprefix("com.samsung.") + "/" + field
            external_id = hashlib.sha256(json.dumps([ident, metric]).encode()).hexdigest()
            records.append({"metric": metric, "value": value, "unit": "raw", "recorded_at": at, "source": "samsung-cloud", "device": "Samsung Cloud", "external_id": external_id})
    return records, skipped


def pull_page():
    from samsung_health_cloud.auth import HealthAuth
    from samsung_health_cloud.scsp import ScspIdentity
    from samsung_health_cloud.data import CloudDataClient
    from samsung_health_cloud.models import DeviceProfile
    from .samsung_session import SamsungHealthService
    with engine.begin() as conn:
        cfg = config(conn).get("samsung_cloud", {})
        if not cfg.get("enabled") or not get_secret(conn, "samsung_master"):
            return {"state": "not_connected", "message": "Samsung account sign-in is needed"}
        if not lock(conn):
            return {"state": "busy", "message": "Another Samsung request is running"}
        cursor_slot = SecretSlot(conn, "samsung_cursor")
        cursor = read_json(cursor_slot) if cursor_slot.exists() else {}
        now = int(time.time() * 1000)
        if cursor.get("complete") and now < cursor.get("finished_at", 0) + max(15, int(cfg.get("interval_minutes", 60))) * 60000:
            return {"state": "complete", "message": "Current Samsung import pass is finished", "accepted": 0}
        if cursor.get("complete"):
            cursor = {"since": max(0, cursor["finished_at"] - 86400000)}
        catalog = json.loads(files("samsung_health_cloud").joinpath("resources/manifests.json").read_text())
        manifests = catalog["manifests"] if isinstance(catalog, dict) else catalog
        # Stress is attempted first; unsupported/deprecated manifests remain visible.
        manifests = sorted(manifests, key=lambda m: (m["manifest_id"] != "com.samsung.health.stress", m["manifest_id"]))
        index = cursor.get("index", 0)
        manifest = manifests[index]
        status, message, accepted, duplicates, skipped = "running", "Page received", 0, 0, 0
        try:
            with httpx.Client(timeout=12, follow_redirects=False) as http:
                service = SamsungHealthService(store=EncryptedStateStore(conn), master_state_path=SecretSlot(conn, "samsung_master"), health_auth=HealthAuth(http), scsp=ScspIdentity(http, profile=DeviceProfile()))
                session = service.initialize()
                page = CloudDataClient(http).list_documents(manifest_id=manifest["manifest_id"], schema_revision=manifest["schema_revision"], cloud_authorization=session.cloud_token, limit=100, page_token=cursor.get("page"), start_time=cursor.get("since", 0))
            records, skipped = normalize_documents(page.get("documents", []), manifest["manifest_id"])
            if records:
                result = ingest(conn, records)
                accepted, duplicates = result["accepted"], result["duplicates"]
            next_page = page.get("nextPageToken")
            if next_page and next_page == cursor.get("page"):
                raise ValueError("Pagination did not advance")
            cursor["page"] = next_page
            if not next_page:
                cursor["index"] = index + 1
        except Exception as exc:
            # Keep credentials encrypted and preserve the cursor; never send raw
            # provider errors, signed URLs, or authentication details to the UI.
            if "HTTP 404" in str(exc):
                status, message = "unavailable", "Samsung does not expose this collection"
                cursor.update(index=index + 1, page=None)
            else:
                status, message = "failed", "Samsung could not finish this page. Retry or reconnect."
        if cursor.get("index", 0) >= len(manifests):
            cursor.update(complete=True, finished_at=now)
        write_json(cursor_slot, cursor)
        conn.execute(sa.insert(s.integration_runs).values(provider="samsung-cloud", status=status, detail=message, cursor={"collection": manifest["manifest_id"], "accepted": accepted, "duplicates": duplicates, "skipped": skipped}))
        return {"state": "complete" if cursor.get("complete") else status, "message": message, "collection": manifest["manifest_id"], "accepted": accepted, "duplicates": duplicates, "skipped": skipped, "collections_finished": cursor.get("index", 0), "collections_total": len(manifests)}


@router.post("/pull")
def pull():
    try:
        return pull_page()
    except Exception:
        return {"state": "failed", "message": "Samsung sync is unavailable. Your saved data is still available."}
