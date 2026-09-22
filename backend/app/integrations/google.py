"""Google Calendar transport for one explicitly configured calendar.

Sync is bounded, resumable, and safe to call from a cold-starting host. Google
is pulled incrementally before local changes are pushed. Content timestamps,
not sync bookkeeping, choose the winner; Google wins an exact tie.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .. import schema as s
from ..db import engine
from ..security import get_secret, owner, put_secret
from ..services import config, setting


router = APIRouter(prefix="/api/integrations/google")
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_ROOT = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
LOCK_NAME = "life-os-google-calendar-v1"


class GoogleError(RuntimeError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


def resolve(local, remote):
    """Compare content timestamps; Google wins ties."""
    return "google" if remote["updated_at"] >= local["updated_at"] else "local"


def _oauth_config():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    public = os.getenv("PUBLIC_API_URL", "").rstrip("/")
    redirect = os.getenv("GOOGLE_REDIRECT_URI", "").strip() or (
        public + "/api/integrations/google/auth/callback" if public else ""
    )
    if not client_id or not client_secret or not redirect:
        raise HTTPException(
            409,
            "Google Calendar needs GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and PUBLIC_API_URL on the API host.",
        )
    return client_id, client_secret, redirect


def _google_config(conn):
    value = config(conn).get("google", {})
    return {
        "calendar_id": str(value.get("calendar_id", "")).strip(),
        "transport": value.get("transport", "poll"),
        "poll_minutes": int(value.get("poll_minutes", 15)),
    }


def _dt(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not value:
        return s.now()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _json(value):
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _request(client, method, url, token, *, params=None, payload=None, headers=None):
    merged = {"Authorization": "Bearer " + token}
    merged.update(headers or {})
    try:
        response = client.request(
            method, url, params=params, json=payload, headers=merged, timeout=25
        )
    except httpx.HTTPError as exc:
        raise GoogleError(503, "Google Calendar is temporarily unreachable") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message")
        except Exception:
            detail = None
        raise GoogleError(response.status_code, detail or "Google Calendar request failed")
    return response.json() if response.content else {}


def _access_token(refresh_token):
    client_id, client_secret, _ = _oauth_config()
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise GoogleError(503, "Google authorization is temporarily unreachable") from exc
    if response.status_code >= 400:
        raise GoogleError(response.status_code, "Google authorization expired; reconnect Calendar")
    token = response.json().get("access_token")
    if not token:
        raise GoogleError(401, "Google did not return an access token")
    return token


def _calendar_row(conn, calendar_id):
    conn.execute(
        pg_insert(s.calendar_sync)
        .values(calendar_id=calendar_id)
        .on_conflict_do_nothing(index_elements=[s.calendar_sync.c.calendar_id])
    )
    return conn.execute(
        sa.select(s.calendar_sync)
        .where(s.calendar_sync.c.calendar_id == calendar_id)
        .with_for_update()
    ).mappings().one()


def _remote_shape(event, owner_zone="UTC"):
    updated = _dt(event.get("updated"))
    cancelled = event.get("status") == "cancelled"
    start = event.get("start") or event.get("originalStartTime") or {}
    end = event.get("end") or {}
    all_day = "date" in start
    zone = start.get("timeZone") or end.get("timeZone") or owner_zone
    if all_day:
        starts_at = datetime.combine(date.fromisoformat(start["date"]), time.min, timezone.utc)
        ends_at = datetime.combine(
            date.fromisoformat(end.get("date", start["date"])), time.min, timezone.utc
        )
        if ends_at <= starts_at:
            ends_at = starts_at + timedelta(days=1)
    else:
        starts_at = _dt(start.get("dateTime"))
        ends_at = _dt(end.get("dateTime")) if end.get("dateTime") else starts_at + timedelta(hours=1)
    original = event.get("originalStartTime") or {}
    original_start = None
    if original.get("dateTime"):
        original_start = _dt(original["dateTime"])
    elif original.get("date"):
        original_start = datetime.combine(date.fromisoformat(original["date"]), time.min, timezone.utc)
    return {
        "title": event.get("summary") or "Untitled event",
        "description": event.get("description") or "",
        "starts_at": starts_at,
        "ends_at": ends_at,
        "all_day": all_day,
        "timezone": zone,
        "recurrence": event.get("recurrence") or [],
        "original_start": original_start,
        "google_event_id": event["id"],
        "etag": event.get("etag"),
        "sync_state": "synced",
        "deleted_at": updated if cancelled else None,
        "updated_at": updated,
    }


def _fetch_event(client, token, calendar_id, event_id):
    return _request(
        client,
        "GET",
        f"{API_ROOT}/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
        token,
    )


def _apply_remote(conn, client, token, calendar_id, event, owner_zone="UTC"):
    local = conn.execute(
        sa.select(s.calendar_events).where(
            s.calendar_events.c.google_event_id == event["id"]
        )
    ).mappings().first()
    remote = _remote_shape(event, owner_zone)
    recurring_id = event.get("recurringEventId")
    master_id = None
    if recurring_id:
        master_id = conn.execute(
            sa.select(s.calendar_events.c.id).where(
                s.calendar_events.c.google_event_id == recurring_id
            )
        ).scalar_one_or_none()
        if not master_id:
            try:
                master = _fetch_event(client, token, calendar_id, recurring_id)
                master_id = _apply_remote(
                    conn, client, token, calendar_id, master, owner_zone
                )["id"]
            except GoogleError:
                master_id = None
    remote["master_id"] = master_id
    if not local:
        return dict(
            conn.execute(
                sa.insert(s.calendar_events).values(**remote).returning(s.calendar_events)
            ).mappings().one()
        )
    changed_remote = bool(local["etag"] and local["etag"] != remote["etag"])
    changed_local = local["sync_state"] in {"dirty", "deleted"}
    if changed_remote and changed_local:
        winner = resolve(dict(local), {"updated_at": remote["updated_at"]})
        conn.execute(
            sa.insert(s.sync_conflicts).values(
                event_id=local["id"],
                local_version=_json(dict(local)),
                remote_version=_json(event),
                winner=winner,
            )
        )
        if winner == "local":
            return dict(local)
    elif changed_local and not changed_remote:
        return dict(local)
    return dict(
        conn.execute(
            sa.update(s.calendar_events)
            .where(s.calendar_events.c.id == local["id"])
            .values(**remote)
            .returning(s.calendar_events)
        ).mappings().one()
    )


def _pull_pages(conn, client, token, calendar_id, owner_zone):
    pulled = 0
    restarted = False
    while True:
        with conn.begin():
            state = _calendar_row(conn, calendar_id)
            params = {"singleEvents": "false", "showDeleted": "true", "maxResults": 250}
            if state["page_token"]:
                params["pageToken"] = state["page_token"]
            elif state["sync_token"]:
                params["syncToken"] = state["sync_token"]
            try:
                page = _request(
                    client,
                    "GET",
                    f"{API_ROOT}/calendars/{quote(calendar_id, safe='')}/events",
                    token,
                    params=params,
                )
            except GoogleError as exc:
                if exc.status == 410 and not restarted:
                    conn.execute(
                        sa.update(s.calendar_sync)
                        .where(s.calendar_sync.c.id == state["id"])
                        .values(sync_token=None, page_token=None, last_error=None)
                    )
                    restarted = True
                    continue
                raise
            items = page.get("items", [])
            items.sort(key=lambda item: bool(item.get("recurringEventId")))
            for item in items:
                _apply_remote(conn, client, token, calendar_id, item, owner_zone)
                pulled += 1
            next_page = page.get("nextPageToken")
            values = {"page_token": next_page, "last_error": None}
            if not next_page:
                values.update(
                    sync_token=page.get("nextSyncToken") or state["sync_token"],
                    last_synced_at=s.now(),
                )
            conn.execute(
                sa.update(s.calendar_sync)
                .where(s.calendar_sync.c.id == state["id"])
                .values(**values)
            )
        if not next_page:
            return pulled


def _event_payload(conn, row):
    payload = {"summary": row["title"], "description": row["description"]}
    if row["all_day"]:
        payload["start"] = {"date": row["starts_at"].date().isoformat()}
        payload["end"] = {"date": row["ends_at"].date().isoformat()}
    else:
        payload["start"] = {
            "dateTime": row["starts_at"].isoformat(),
            "timeZone": row["timezone"],
        }
        payload["end"] = {
            "dateTime": row["ends_at"].isoformat(),
            "timeZone": row["timezone"],
        }
    if row["recurrence"]:
        payload["recurrence"] = row["recurrence"]
    return payload


def _exception_instance(conn, client, token, calendar_id, row):
    if not row["master_id"]:
        return None
    master = conn.execute(
        sa.select(s.calendar_events.c.google_event_id).where(
            s.calendar_events.c.id == row["master_id"]
        )
    ).scalar_one_or_none()
    if not master:
        raise GoogleError(409, "Sync the recurring event before its exception")
    stamp = row["original_start"] or row["starts_at"]
    result = _request(
        client,
        "GET",
        f"{API_ROOT}/calendars/{quote(calendar_id, safe='')}/events/{quote(master, safe='')}/instances",
        token,
        params={"originalStart": stamp.isoformat(), "showDeleted": "true", "maxResults": 1},
    )
    items = result.get("items", [])
    if not items:
        raise GoogleError(409, "Google could not find the recurring occurrence to change")
    return items[0]


def _push_one(conn, client, token, calendar_id, row):
    event_url = f"{API_ROOT}/calendars/{quote(calendar_id, safe='')}/events"
    headers = {"If-Match": row["etag"]} if row["etag"] else {}
    if row["sync_state"] == "deleted":
        if not row["google_event_id"]:
            instance = _exception_instance(conn, client, token, calendar_id, row)
            if instance:
                row["google_event_id"] = instance["id"]
                row["etag"] = instance.get("etag")
                headers = {"If-Match": row["etag"]} if row["etag"] else {}
            else:
                conn.execute(
                    sa.update(s.calendar_events)
                    .where(s.calendar_events.c.id == row["id"])
                    .values(sync_state="synced")
                )
                return
        try:
            _request(
                client,
                "DELETE",
                event_url + "/" + quote(row["google_event_id"], safe=""),
                token,
                headers=headers,
            )
        except GoogleError as exc:
            if exc.status not in {404, 410}:
                raise
        conn.execute(
            sa.update(s.calendar_events)
            .where(s.calendar_events.c.id == row["id"])
            .values(sync_state="synced")
        )
        return
    payload = _event_payload(conn, row)
    if row["google_event_id"]:
        try:
            saved = _request(
                client,
                "PATCH",
                event_url + "/" + quote(row["google_event_id"], safe=""),
                token,
                payload=payload,
                headers=headers,
            )
        except GoogleError as exc:
            if exc.status != 412:
                raise
            remote = _fetch_event(client, token, calendar_id, row["google_event_id"])
            current = _apply_remote(conn, client, token, calendar_id, remote)
            if current["sync_state"] == "synced":
                return
            saved = _request(
                client,
                "PATCH",
                event_url + "/" + quote(row["google_event_id"], safe=""),
                token,
                payload=payload,
                headers={"If-Match": remote.get("etag", "")},
            )
    elif row["master_id"]:
        instance = _exception_instance(conn, client, token, calendar_id, row)
        saved = _request(
            client,
            "PATCH",
            event_url + "/" + quote(instance["id"], safe=""),
            token,
            payload=payload,
            headers={"If-Match": instance.get("etag", "")},
        )
    else:
        google_id = "lifeos" + row["id"].hex
        payload["id"] = google_id
        try:
            saved = _request(client, "POST", event_url, token, payload=payload)
        except GoogleError as exc:
            if exc.status != 409:
                raise
            saved = _fetch_event(client, token, calendar_id, google_id)
    conn.execute(
        sa.update(s.calendar_events)
        .where(s.calendar_events.c.id == row["id"])
        .values(
            google_event_id=saved.get("id", row["google_event_id"]),
            etag=saved.get("etag"),
            sync_state="synced",
        )
    )


def _push_changes(conn, client, token, calendar_id):
    pushed = 0
    while True:
        with conn.begin():
            row = conn.execute(
                sa.select(s.calendar_events)
                .where(s.calendar_events.c.sync_state.in_(["local", "dirty", "deleted"]))
                .order_by(s.calendar_events.c.master_id.asc().nullsfirst(), s.calendar_events.c.updated_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).mappings().first()
            if not row:
                return pushed
            _push_one(conn, client, token, calendar_id, dict(row))
            pushed += 1


def _ensure_channel(conn, client, token, calendar_id, cfg):
    if cfg["transport"] != "push":
        return False
    public = os.getenv("PUBLIC_API_URL", "").rstrip("/")
    if not public.startswith("https://"):
        raise GoogleError(409, "Webhook mode needs an HTTPS PUBLIC_API_URL")
    with conn.begin():
        row = _calendar_row(conn, calendar_id)
        if row["channel_expires_at"] and row["channel_expires_at"] > s.now() + timedelta(hours=12):
            return False
        channel_id = str(uuid.uuid4())
        channel_token = secrets.token_urlsafe(32)
        watched = _request(
            client,
            "POST",
            f"{API_ROOT}/calendars/{quote(calendar_id, safe='')}/events/watch",
            token,
            payload={
                "id": channel_id,
                "type": "web_hook",
                "address": public + "/api/integrations/google/webhook",
                "token": channel_token,
                "params": {"ttl": "604800"},
            },
        )
        expiration = watched.get("expiration")
        expires = datetime.fromtimestamp(int(expiration) / 1000, timezone.utc) if expiration else s.now() + timedelta(days=6)
        put_secret(conn, "google_channel_token", channel_token)
        conn.execute(
            sa.update(s.calendar_sync)
            .where(s.calendar_sync.c.id == row["id"])
            .values(
                channel_id=channel_id,
                channel_resource_id=watched.get("resourceId"),
                channel_expires_at=expires,
            )
        )
    return True


def sync_calendar(force=False):
    """Run one pull/push pass. Safe for requests, digests and webhook wakeups."""
    conn = engine.connect()
    locked = False
    try:
        locked = bool(
            conn.execute(sa.text("SELECT pg_try_advisory_lock(hashtext(:name))"), {"name": LOCK_NAME}).scalar_one()
        )
        conn.commit()
        if not locked:
            return {"state": "busy", "message": "A calendar sync is already running"}
        with conn.begin():
            cfg = _google_config(conn)
            refresh = get_secret(conn, "google_refresh_token")
            owner_zone = config(conn).get("timezone", "UTC")
        if not cfg["calendar_id"] or not refresh:
            return {"state": "not_connected", "message": "Choose a calendar and connect Google first"}
        token = _access_token(refresh)
        with httpx.Client() as client:
            pulled = _pull_pages(conn, client, token, cfg["calendar_id"], owner_zone)
            pushed = _push_changes(conn, client, token, cfg["calendar_id"])
            channel = _ensure_channel(conn, client, token, cfg["calendar_id"], cfg)
        with conn.begin():
            conn.execute(
                sa.insert(s.integration_runs).values(
                    provider="google-calendar",
                    status="ok",
                    detail="Google Calendar sync completed",
                    cursor={"pulled": pulled, "pushed": pushed, "channel_renewed": channel},
                )
            )
        return {"state": "ok", "pulled": pulled, "pushed": pushed, "channel_renewed": channel}
    except GoogleError as exc:
        if conn.in_transaction():
            conn.rollback()
        with conn.begin():
            cfg = _google_config(conn)
            if cfg["calendar_id"]:
                conn.execute(
                    sa.update(s.calendar_sync)
                    .where(s.calendar_sync.c.calendar_id == cfg["calendar_id"])
                    .values(last_error=str(exc))
                )
            conn.execute(
                sa.insert(s.integration_runs).values(
                    provider="google-calendar", status="failed", detail=str(exc), cursor={"status": exc.status}
                )
            )
        return {"state": "failed", "message": str(exc)}
    finally:
        if locked:
            try:
                if conn.in_transaction():
                    conn.rollback()
                conn.execute(sa.text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": LOCK_NAME})
                conn.commit()
            except Exception:
                pass
        conn.close()


def google_status(conn):
    cfg = _google_config(conn)
    row = None
    if cfg["calendar_id"]:
        row = conn.execute(
            sa.select(s.calendar_sync).where(s.calendar_sync.c.calendar_id == cfg["calendar_id"])
        ).mappings().first()
    connected = get_secret(conn, "google_refresh_token") is not None
    configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("PUBLIC_API_URL"))
    return {
        "configured": configured,
        "connected": connected,
        "calendar_id": cfg["calendar_id"],
        "transport": cfg["transport"],
        "poll_minutes": cfg["poll_minutes"],
        "last_synced_at": row["last_synced_at"] if row else None,
        "last_error": row["last_error"] if row else None,
        "channel_expires_at": row["channel_expires_at"] if row else None,
    }


@router.post("/config", dependencies=[Depends(owner)])
def configure(payload: dict = Body(...)):
    calendar_id = str(payload.get("calendar_id", "")).strip()
    transport = payload.get("transport", "poll")
    poll_minutes = int(payload.get("poll_minutes", 15))
    if transport not in {"poll", "push"}:
        raise HTTPException(422, "Calendar transport must be poll or push")
    if not 5 <= poll_minutes <= 1440:
        raise HTTPException(422, "Polling interval must be 5–1440 minutes")
    with engine.begin() as conn:
        previous = _google_config(conn)["calendar_id"]
        if previous and previous != calendar_id:
            conn.execute(
                sa.update(s.calendar_events)
                .where(s.calendar_events.c.google_event_id.is_not(None))
                .values(google_event_id=None, etag=None, sync_state="local")
            )
        setting(conn, "google", {"calendar_id": calendar_id, "transport": transport, "poll_minutes": poll_minutes})
        if calendar_id:
            _calendar_row(conn, calendar_id)
    return {"ok": True}


@router.get("/auth/start", dependencies=[Depends(owner)])
def auth_start():
    client_id, _, redirect = _oauth_config()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with engine.begin() as conn:
        if not _google_config(conn)["calendar_id"]:
            raise HTTPException(409, "Save the designated Google calendar ID first")
        put_secret(
            conn,
            "google_oauth_pending",
            json.dumps({"state": state, "verifier": verifier, "expires_at": (s.now() + timedelta(minutes=10)).isoformat()}),
        )
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return {"authorization_url": AUTH_URL + "?" + query}


@router.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(400, "Google authorization was cancelled")
    client_id, client_secret, redirect = _oauth_config()
    with engine.begin() as conn:
        raw = get_secret(conn, "google_oauth_pending")
        if not raw:
            raise HTTPException(400, "Google authorization state is missing; start again")
        pending = json.loads(raw)
        conn.execute(sa.delete(s.secrets).where(s.secrets.c.name == "google_oauth_pending"))
        if not secrets.compare_digest(state, pending.get("state", "")) or _dt(pending.get("expires_at")) < s.now():
            raise HTTPException(400, "Google authorization state expired; start again")
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "code_verifier": pending["verifier"],
                "grant_type": "authorization_code",
                "redirect_uri": redirect,
            },
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Google authorization is temporarily unreachable") from exc
    if response.status_code >= 400 or not response.json().get("refresh_token"):
        raise HTTPException(400, "Google did not provide an offline refresh token; reconnect and allow access")
    with engine.begin() as conn:
        put_secret(conn, "google_refresh_token", response.json()["refresh_token"])
    return """<!doctype html><meta charset=utf-8><title>Life OS connected</title><body style='font:16px system-ui;padding:40px;background:#0d1117;color:#eef2ff'><h1>Google Calendar connected</h1><p>You can close this tab and return to Life OS.</p></body>"""


@router.post("/sync", dependencies=[Depends(owner)])
def sync_now():
    result = sync_calendar(True)
    if result["state"] == "failed":
        raise HTTPException(502, result["message"])
    return result


@router.post("/webhook")
def webhook(request: Request):
    channel_id = request.headers.get("x-goog-channel-id", "")
    resource_id = request.headers.get("x-goog-resource-id", "")
    supplied = request.headers.get("x-goog-channel-token", "")
    with engine.connect() as conn:
        expected = get_secret(conn, "google_channel_token")
        row = conn.execute(
            sa.select(s.calendar_sync).where(s.calendar_sync.c.channel_id == channel_id)
        ).mappings().first()
    if not expected or not secrets.compare_digest(expected, supplied) or not row or row["channel_resource_id"] != resource_id:
        raise HTTPException(401, "Unknown Google notification channel")
    sync_calendar(True)
    return Response(status_code=204)


@router.post("/disconnect", dependencies=[Depends(owner)])
def disconnect():
    with engine.begin() as conn:
        conn.execute(
            sa.delete(s.secrets).where(
                s.secrets.c.name.in_(["google_refresh_token", "google_oauth_pending", "google_channel_token"])
            )
        )
        conn.execute(
            sa.update(s.calendar_sync).values(
                sync_token=None,
                page_token=None,
                channel_id=None,
                channel_resource_id=None,
                channel_expires_at=None,
                last_error=None,
            )
        )
    return {"connected": False}
