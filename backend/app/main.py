import os, json, uuid, secrets as random, math
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import FastAPI, Depends, HTTPException, Request, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from .db import engine
from . import schema as s
from .security import (
    owner,
    trigger_auth,
    hasher,
    digest,
    put_secret,
    get_secret,
    VerifyMismatchError,
    InvalidHashError,
    issue_session,
)
from .services import (
    rows,
    config,
    setting,
    ingest,
    dashboard,
    academic_summary,
    progress,
    muscle_volume,
    reminders,
)
from .domain import sm2, next_task_date, normalize_body, calendar_occurrences
from .backup import coerce, export_data, archive, parse_backup, restore, dumps

from contextlib import asynccontextmanager
from .assistant_mcp import mcp
from .assistant import router as assistant_router
from .assistant_auth import router as assistant_auth_router
mcp_app = mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

app = FastAPI(title="Life OS", version="1.0.0", lifespan=lifespan)
app.include_router(assistant_router)
app.include_router(assistant_auth_router)
from .transfers import router as transfer_router
from .integrations.samsung import router as samsung_router

app.include_router(transfer_router)
app.include_router(samsung_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    if int(request.headers.get("content-length", "0")) > 25_000_000:
        return JSONResponse({"detail": "Request too large"}, 413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def record_bridge_failure(request, detail):
    if not request.url.path.startswith("/api/integrations/health/"):
        return
    # Only a bridge with the valid secret can create a diagnostic. No request
    # body, reading values, headers, or credentials are retained here.
    with engine.begin() as conn:
        expected = get_secret(conn, "health_webhook_token")
        provided = request.headers.get("authorization", "").removeprefix("Bearer ")
        if expected and random.compare_digest(expected, provided):
            conn.execute(sa.insert(s.integration_runs).values(provider="health-webhook", status="rejected", detail="Phone sync validation failed", cursor=detail))


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    if request.url.path.startswith("/api/integrations/health/"):
        detail = {"stage": "request", "error_types": sorted({e["type"] for e in exc.errors()})}
        record_bridge_failure(request, detail)
        return JSONResponse({"detail": "The phone bridge must send a valid JSON body", "diagnostic": detail}, 422)
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    # Validation messages from conversion libraries can contain input values.
    # Keep only known app-generated reasons in the durable diagnostic.
    reason = str(exc)
    known = ("Supply 1–25000 health records; shorten the phone sync range for larger imports", "Health text fields cannot be empty", "Health value must be finite and nonnegative", "Bridge source must identify the bridge")
    detail = getattr(exc, "bridge_detail", {"stage": "ingestion", "reason": reason if reason in known else "Invalid mapped field type or value"})
    record_bridge_failure(request, detail)
    return JSONResponse({"detail": str(exc)}, 422)


@app.exception_handler(IntegrityError)
async def constraint(request, exc):
    return JSONResponse(
        {
            "detail": "This change violates a data rule or a linked record still depends on it."
        },
        409,
    )


@app.exception_handler(DataError)
async def bad_data(request, exc):
    record_bridge_failure(request, {"stage": "database", "reason": "Mapped field has an invalid value"})
    return JSONResponse({"detail": "A field has an invalid value."}, 422)


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(sa.text("SELECT 1"))
    return {"status": "ok", "database": "postgresql"}


@app.post("/api/auth/login")
def login(request: Request, payload: dict = Body(...)):
    fingerprint = digest(
        (request.client.host if request.client else "unknown")
        + str(payload.get("username", ""))
    )
    valid = False
    with engine.begin() as conn:
        conn.execute(
            pg_insert(s.auth_attempts)
            .values(fingerprint=fingerprint)
            .on_conflict_do_nothing(index_elements=[s.auth_attempts.c.fingerprint])
        )
        attempt = (
            conn.execute(
                sa.select(s.auth_attempts)
                .where(s.auth_attempts.c.fingerprint == fingerprint)
                .with_for_update()
            )
            .mappings()
            .one()
        )
        fresh = s.now() - attempt["window_started_at"] > timedelta(minutes=15)
        if not fresh and attempt["failures"] >= 10:
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        user = (
            conn.execute(
                sa.select(s.owners).where(
                    s.owners.c.username == payload.get("username")
                )
            )
            .mappings()
            .first()
        )
        if user:
            try:
                valid = hasher.verify(
                    user["password_hash"], str(payload.get("password", ""))
                )
            except (VerifyMismatchError, InvalidHashError):
                pass
        else:
            # Match password-hashing work for unknown usernames.
            hasher.hash(str(payload.get("password", "")))
        conn.execute(
            sa.update(s.auth_attempts)
            .where(s.auth_attempts.c.id == attempt["id"])
            .values(
                failures=0 if valid else (1 if fresh else attempt["failures"] + 1),
                window_started_at=s.now() if fresh else attempt["window_started_at"],
                updated_at=s.now(),
            )
        )
        if valid:
            expires = s.now() + timedelta(hours=int(os.getenv("SESSION_HOURS", "12")))
            token = issue_session(user["id"], expires)
            conn.execute(sa.delete(s.sessions).where(s.sessions.c.expires_at < s.now()))
            conn.execute(
                sa.insert(s.sessions).values(
                    owner_id=user["id"], token_hash=digest(token), expires_at=expires
                )
            )
    if not valid:
        raise HTTPException(401, "Username or password is incorrect")
    return {"token": token, "username": user["username"]}


@app.get("/api/auth/me")
def me(identity=Depends(owner)):
    with engine.connect() as conn:
        name = conn.execute(
            sa.select(s.owners.c.username).where(s.owners.c.id == identity)
        ).scalar_one()
    return {"username": name}


@app.post("/api/auth/logout")
def logout(request: Request, identity=Depends(owner)):
    with engine.begin() as conn:
        conn.execute(
            sa.delete(s.sessions).where(
                s.sessions.c.token_hash
                == digest(request.headers["authorization"].removeprefix("Bearer "))
            )
        )
    return {"ok": True}


def get_table(name, write=False):
    if name not in s.TABLES or name in {
        "owners",
        "sessions",
        "secrets",
        "auth_attempts",
        "backup_transfers",
        "assistant_oauth",
        "assistant_batches",
    }:
        raise HTTPException(404, "Table is not available")
    if write and name in s.SYSTEM:
        raise HTTPException(405, "Use the dedicated action for this record")
    return s.TABLES[name]


@app.get("/api/schema", dependencies=[Depends(owner)])
def schema():
    result = {}
    for name, t in s.TABLES.items():
        if name in {
            "owners",
            "sessions",
            "secrets",
            "auth_attempts",
            "backup_transfers",
        "assistant_oauth",
        "assistant_batches",
        }:
            continue
        fields = []
        for c in t.c:
            if c.name in {"id", "created_at", "updated_at"}:
                continue
            kind = (
                "json"
                if isinstance(c.type, sa.JSON)
                else (
                    "boolean"
                    if isinstance(c.type, sa.Boolean)
                    else (
                        "number"
                        if isinstance(c.type, (sa.Integer, sa.Float))
                        else (
                            "datetime"
                            if isinstance(c.type, sa.DateTime)
                            else "date" if isinstance(c.type, sa.Date) else "text"
                        )
                    )
                )
            )
            ref = (
                next(iter(c.foreign_keys)).column.table.name if c.foreign_keys else None
            )
            default = c.default.arg if c.default and c.default.is_scalar else None
            fields.append(
                {
                    "name": c.name,
                    "type": kind,
                    "required": c.name in {"title", "name"}
                    or (not c.nullable and c.default is None),
                    "default": default,
                    "ref": ref,
                }
            )
        result[name] = {"fields": fields, "editable": name not in s.SYSTEM}
    return result


@app.get("/api/data/{name}", dependencies=[Depends(owner)])
def list_records(name: str, q: str = "", limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    t = get_table(name)
    with engine.connect() as conn:
        query = sa.select(t)
        if name == "journal_entries" and q:
            vector = sa.func.to_tsvector(
                sa.literal_column("'english'"),
                t.c.title + sa.literal_column("' '") + t.c.body,
            )
            query = query.where(
                vector.op("@@")(sa.func.websearch_to_tsquery("english", q))
            )
        query = query.order_by(t.c.created_at.desc(), t.c.id.desc())
        if name == "health_records":
            query = query.limit(limit).offset(offset)
        return [
            dict(r)
            for r in conn.execute(query).mappings()
        ]


def validate(conn, name, payload, existing=None):
    t = get_table(name, True)
    blocked = {"id", "created_at", "updated_at"}
    if name == "tasks":
        blocked |= {"series_id", "previous_id", "completed_at", "recurrence_anchor"}
    if name == "calendar_events":
        blocked |= {"google_event_id", "etag", "sync_state", "deleted_at"}
    if name == "concept_notes":
        blocked |= {"ease_factor", "repetitions", "interval_days"}
    if any(k in blocked for k in payload):
        raise ValueError("Server-managed fields cannot be edited")
    data = coerce(t, payload)
    merged = {**(existing or {}), **data}
    for key in {"title", "name"}.intersection(t.c.keys()):
        if not merged.get(key) or not str(merged[key]).strip():
            raise ValueError(key + " cannot be blank")
    for key, value in data.items():
        typ = t.c[key].type
        if (
            isinstance(typ, (sa.Float, sa.Integer))
            and value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            )
        ):
            raise ValueError(key + " must be a finite number")
        if isinstance(typ, sa.Integer) and value is not None and int(value) != value:
            raise ValueError(key + " must be a whole number")
        if isinstance(typ, sa.Boolean) and not isinstance(value, bool):
            raise ValueError(key + " must be true or false")
        if (
            isinstance(typ, sa.Text)
            and value is not None
            and not isinstance(value, str)
        ):
            raise ValueError(key + " must be text")
        if key in {"title", "name"} and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError(key + " cannot be blank")
    for key in ("tags", "hints", "walkthrough", "recurrence", "options"):
        if key in data and not isinstance(data[key], list):
            raise ValueError(key + " must be a list")
    if name == "settings":
        key = merged["key"]
        val = merged["value"]
        if key == "timezone":
            try:
                ZoneInfo(val)
            except (ZoneInfoNotFoundError, TypeError):
                raise ValueError("Choose a valid IANA timezone, such as Asia/Kolkata")
        elif key == "streaks":
            if (
                not isinstance(val, dict)
                or len(val) != 3
                or any(
                    not isinstance(k, list)
                    or not k
                    or any(
                        x not in {"journal", "attempt", "review", "workout"} for x in k
                    )
                    for k in val.values()
                )
            ):
                raise ValueError(
                    "Configure three streaks using journal, attempt, review, workout sources"
                )
        elif key == "accuracy_threshold" and (
            not isinstance(val, (int, float)) or not 0 <= val <= 1
        ):
            raise ValueError("Accuracy threshold is between 0 and 1")
        elif key == "water_source" and val not in ("manual", "samsung_health"):
            raise ValueError("Choose manual or samsung_health for water source")
        elif key == "body":
            if not isinstance(val, dict):
                raise ValueError("Body metrics must be an object")
            for k in ("weight_kg", "height_cm", "age", "activity_multiplier"):
                if val.get(k) is not None and (
                    not isinstance(val[k], (int, float)) or not 0 < val[k] < 1000
                ):
                    raise ValueError("Invalid body metric: " + k)
            if val.get("sex") not in (None, "male", "female"):
                raise ValueError("BMR equation sex must be male or female")
            if val.get("goal") not in {"maintain", "build", "reduce"}:
                raise ValueError("Choose maintain, build or reduce")
            rates = val.get("protein_g_per_kg", {})
            if any(
                not isinstance(rates.get(g), (int, float)) or not 0 < rates[g] <= 5
                for g in ("maintain", "build", "reduce")
            ):
                raise ValueError(
                    "Set a positive protein g/kg value up to 5 for each goal"
                )
        elif key in {"water_goal_ml", "steps_goal"} and (
            not isinstance(val, (int, float)) or val <= 0
        ):
            raise ValueError("Daily goal must be positive")
        elif key == "grading":
            if not isinstance(val, dict) or val.get("aggregation") not in (
                "credit_weighted",
                "equal_course",
            ):
                raise ValueError("Choose credit_weighted or equal_course GPA")
            for b in val.get("bands", []):
                if (
                    not isinstance(b.get("minimum"), (int, float))
                    or not isinstance(b.get("points"), (int, float))
                    or not b.get("label")
                ):
                    raise ValueError(
                        "Every grade band needs minimum, label and numeric points"
                    )
    if name == "tasks":
        if data.get("status") == "done" and (
            not existing or existing["status"] != "done"
        ):
            raise ValueError(
                "Use Complete to finish a task and generate its next occurrence"
            )
        if merged.get("rrule"):
            if not merged.get("due_at"):
                raise ValueError("Recurring tasks need a due date")
            from dateutil.rrule import rrulestr

            rrulestr(merged["rrule"], dtstart=merged["due_at"])
        if existing and merged.get("parent_id"):
            parent = merged["parent_id"]
            seen = {existing["id"]}
            while parent:
                if parent in seen:
                    raise ValueError("Subtasks cannot form a cycle")
                seen.add(parent)
                parent = conn.execute(
                    sa.select(s.tasks.c.parent_id).where(s.tasks.c.id == parent)
                ).scalar_one_or_none()
    if name == "exams" and not merged.get("import_key"):
        data["import_key"] = str(uuid.uuid4())
    if name == "calendar_events":
        ZoneInfo(merged.get("timezone", "UTC"))
        if merged.get("recurrence"):
            from dateutil.rrule import rrulestr

            rrulestr("\n".join(merged["recurrence"]), dtstart=merged["starts_at"])
        if merged.get("master_id") and not merged.get("original_start"):
            raise ValueError("A recurrence exception needs its original start time")
    if "custom_fields" in data:
        if not isinstance(data["custom_fields"], dict):
            raise ValueError("Custom fields must be an object")
        defs = {
            d["name"]: d
            for d in rows(conn, "custom_field_definitions")
            if d["entity"] == name
        }
        for key, value in data["custom_fields"].items():
            if key not in defs:
                raise ValueError("Define custom field first: " + key)
            kind = defs[key]["field_type"]
            if kind == "number" and (
                isinstance(value, bool) or not isinstance(value, (float, int))
            ):
                raise ValueError(key + " must be numeric")
            if kind == "boolean" and not isinstance(value, bool):
                raise ValueError(key + " must be boolean")
            if kind == "select" and value not in defs[key]["options"]:
                raise ValueError("Invalid option for " + key)
    return data


@app.post("/api/data/{name}", dependencies=[Depends(owner)])
def create_record(name: str, payload: dict = Body(...)):
    t = get_table(name, True)
    with engine.begin() as conn:
        data = validate(conn, name, payload)
        if name == "tasks":
            data["recurrence_anchor"] = data.get("due_at")
        if name == "concept_notes":
            data.setdefault(
                "due_on",
                s.now()
                .astimezone(ZoneInfo(config(conn).get("timezone", "UTC")))
                .date(),
            )
        return dict(
            conn.execute(sa.insert(t).values(**data).returning(t)).mappings().one()
        )


@app.patch("/api/data/{name}/{ident}", dependencies=[Depends(owner)])
def update_record(name: str, ident: uuid.UUID, payload: dict = Body(...)):
    t = get_table(name, True)
    with engine.begin() as conn:
        old = (
            conn.execute(sa.select(t).where(t.c.id == ident).with_for_update())
            .mappings()
            .first()
        )
        if not old:
            raise HTTPException(404, "Record not found")
        data = validate(conn, name, payload, dict(old))
        data["updated_at"] = s.now()
        if name == "calendar_events":
            data["sync_state"] = "dirty" if old["google_event_id"] else "local"
        return dict(
            conn.execute(
                sa.update(t).where(t.c.id == ident).values(**data).returning(t)
            )
            .mappings()
            .one()
        )


@app.delete("/api/data/{name}/{ident}", dependencies=[Depends(owner)])
def delete_record(name: str, ident: uuid.UUID):
    t = get_table(name, True)
    with engine.begin() as conn:
        if name == "calendar_events":
            conn.execute(
                sa.update(t)
                .where(sa.or_(t.c.id == ident, t.c.master_id == ident))
                .values(deleted_at=s.now(), updated_at=s.now(), sync_state="deleted")
            )
        else:
            if name == "journal_entries":
                from .assistant import purge_journal_history
                purge_journal_history(conn, ident)
            conn.execute(sa.delete(t).where(t.c.id == ident))
    return {"ok": True}


@app.get("/api/dashboard", dependencies=[Depends(owner)])
def get_dashboard():
    with engine.connect() as conn:
        return dashboard(conn)


@app.get("/api/academics/summary", dependencies=[Depends(owner)])
def academic():
    with engine.connect() as conn:
        return academic_summary(conn)


@app.get("/api/dsa/progress", dependencies=[Depends(owner)])
def dsa_progress():
    with engine.connect() as conn:
        return progress(conn)


@app.get("/api/physical/volume", dependencies=[Depends(owner)])
def volume(workout_id: uuid.UUID | None = None, week: bool = False):
    with engine.connect() as conn:
        return muscle_volume(conn, workout_id, week)


@app.get("/api/physical/readings", dependencies=[Depends(owner)])
def watch_readings():
    t = s.health_records
    with engine.connect() as conn:
        latest = [dict(r) for r in conn.execute(
            sa.select(t.c.metric, t.c.value, t.c.unit, t.c.recorded_at, t.c.created_at)
            .where(sa.or_(t.c.source.startswith("hc-webhook-samsung-"), t.c.source == "samsung-cloud"))
            .distinct(t.c.metric).order_by(t.c.metric, t.c.recorded_at.desc(), t.c.created_at.desc())
        ).mappings()]
        mapping = conn.execute(sa.select(s.ingestion_mappings.c.mapping).where(s.ingestion_mappings.c.name == "hc-webhook-samsung")).scalar_one_or_none()
        connected = bool(get_secret(conn, "samsung_master"))
        sync = conn.execute(sa.select(s.integration_runs.c.status, s.integration_runs.c.detail, s.integration_runs.c.cursor, s.integration_runs.c.created_at).where(s.integration_runs.c.provider == "health-webhook").order_by(s.integration_runs.c.created_at.desc()).limit(1)).mappings().first()
    fields = (mapping or {}).get("streams", [])
    supported = [{"metric": st["fields"]["metric"]["constant"], "unit": st["fields"]["unit"]["constant"]} for st in fields]
    return {"readings": latest, "supported": supported, "samsung_connected": connected, "phone_sync": dict(sync) if sync else None}


@app.get("/api/calendar/agenda", dependencies=[Depends(owner)])
def agenda(start: datetime, end: datetime):
    if (
        not start.tzinfo
        or not end.tzinfo
        or not timedelta(0) < end - start <= timedelta(days=93)
    ):
        raise ValueError("Choose an offset-aware window of 1–93 days")
    with engine.connect() as conn:
        result = calendar_occurrences(rows(conn, "calendar_events"), start, end)
        for name in ("tasks", "assignments"):
            result.extend(
                {**r, "kind": name, "starts_at": r["due_at"]}
                for r in rows(conn, name)
                if r["due_at"] and start <= r["due_at"] < end and r["status"] != "done"
            )
        return sorted(result, key=lambda r: r["starts_at"])


@app.post("/api/tasks/{ident}/complete", dependencies=[Depends(owner)])
def complete(ident: uuid.UUID):
    from .operations import complete_task
    with engine.begin() as conn:
        return complete_task(conn, ident)


@app.post("/api/reviews/{ident}", dependencies=[Depends(owner)])
def review(ident: uuid.UUID, payload: dict = Body(...)):
    from .operations import review_note
    with engine.begin() as conn:
        return review_note(conn, ident, payload.get("grade"))


@app.post("/api/ingest", dependencies=[Depends(owner)])
def manual_ingest(payload: list = Body(...)):
    with engine.begin() as conn:
        return ingest(conn, payload, manual=True)


@app.post("/api/integrations/health/{mapping_name}")
def webhook(mapping_name: str, request: Request, payload=Body(...)):
    with engine.begin() as conn:
        token = get_secret(conn, "health_webhook_token")
        provided = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not token or not random.compare_digest(token, provided):
            raise HTTPException(401, "Invalid bridge token")
        mapping = (
            conn.execute(
                sa.select(s.ingestion_mappings).where(
                    s.ingestion_mappings.c.name == mapping_name,
                    s.ingestion_mappings.c.enabled,
                )
            )
            .mappings()
            .first()
        )
        if not mapping:
            raise HTTPException(404, "Mapping not found")
        omitted = {}
        try:
            normalized = normalize_body(payload, mapping["mapping"], omitted)
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Mapping does not match payload: " + str(exc))
        if any(r.get("source") == "manual" for r in normalized):
            raise ValueError("Bridge source must identify the bridge")
        result = ingest(conn, normalized) if normalized else {"accepted": 0, "duplicates": 0}
        if omitted:
            result["skipped_unverified"] = [{"metric": metric, "field": field, "count": count} for (metric, field), count in omitted.items()]
        conn.execute(sa.insert(s.integration_runs).values(provider="health-webhook", status="partial" if omitted else "ok", detail="Some readings could not be verified and were left out" if omitted else "Phone sync received", cursor=result))
        return result


@app.post("/api/integrations/mapping-preview", dependencies=[Depends(owner)])
def mapping_preview(payload: dict = Body(...)):
    try:
        return normalize_body(payload["sample"], payload["mapping"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Mapping does not match payload: " + str(exc))


@app.post("/api/suggestions/{ident}/{action}", dependencies=[Depends(owner)])
def suggestion(ident: uuid.UUID, action: str):
    if action not in ("accept", "reject"):
        raise ValueError("Choose accept or reject")
    with engine.begin() as conn:
        row = (
            conn.execute(
                sa.select(s.metric_suggestions)
                .where(s.metric_suggestions.c.id == ident)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Suggestion not found")
        if row["status"] == "pending":
            if action == "accept":
                body = config(conn).get("body", {})
                body[row["setting_key"]] = row["proposed_value"]
                setting(conn, "body", body)
            conn.execute(
                sa.update(s.metric_suggestions)
                .where(s.metric_suggestions.c.id == ident)
                .values(status=action, updated_at=s.now())
            )
    return {"ok": True}


@app.get("/api/reminders", dependencies=[Depends(owner)])
def get_reminders():
    with engine.connect() as conn:
        return reminders(conn)


@app.post("/api/digest", dependencies=[Depends(trigger_auth)])
def digest_run():
    with engine.begin() as conn:
        # Only local or acknowledged tombstones are eligible for 30-day cleanup.
        conn.execute(
            sa.delete(s.calendar_events).where(
                s.calendar_events.c.deleted_at < s.now() - timedelta(days=30),
                sa.or_(
                    s.calendar_events.c.google_event_id.is_(None),
                    s.calendar_events.c.sync_state == "synced",
                ),
                s.calendar_events.c.id.not_in(
                    sa.select(s.calendar_events.c.master_id).where(
                        s.calendar_events.c.master_id.is_not(None)
                    )
                ),
            )
        )
        result = reminders(conn)
    from .integrations.samsung import pull
    return {"reminders": result, "calendar_sync": "deferred; use local calendar", "samsung": pull()}


@app.get("/api/backup", dependencies=[Depends(owner)])
def backup():
    with engine.begin() as conn:
        data = export_data(conn)
    return Response(
        archive(data),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=life-os-backup.zip"},
    )


@app.post("/api/restore", dependencies=[Depends(owner)])
async def restore_backup(request: Request, replace: bool = False):
    raw = await request.body()
    if len(raw) > 25_000_000:
        raise ValueError("Backup exceeds 25 MB")
    import zipfile

    try:
        with engine.begin() as conn:
            restore(conn, parse_backup(raw), replace)
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, TypeError):
        raise ValueError("Backup archive is invalid or missing required files")
    return {
        "ok": True,
        "message": "Restored. Sign in with the owner credentials from the backup.",
    }


@app.post("/api/secrets/{name}", dependencies=[Depends(owner)])
def save_secret(name: str, payload: dict = Body(...)):
    if name not in {
        "llm_api_key",
        "health_webhook_token",
        "digest_token",
        "google_refresh_token",
    }:
        raise ValueError("Unknown secret")
    with engine.begin() as conn:
        if payload.get("value"):
            put_secret(conn, name, str(payload["value"]))
        else:
            conn.execute(sa.delete(s.secrets).where(s.secrets.c.name == name))
    return {"ok": True}


@app.get("/api/integrations/status", dependencies=[Depends(owner)])
def integration_status():
    with engine.connect() as conn:
        names = set(conn.execute(sa.select(s.secrets.c.name)).scalars())
        usage = rows(conn, "ai_usage")
    return {
        "llm_configured": "llm_api_key" in names,
        "health_configured": "health_webhook_token" in names,
        "samsung_connected": "samsung_master" in names,
        "google": "Phase 2 scaffold; live sync is not implemented",
        "samsung": "Samsung account linked; private cloud import available" if "samsung_master" in names else "Samsung account sign-in needed for private cloud readings",
        "open_wearables": "Deferred; companion app not built",
        "input_tokens": sum(r["input_tokens"] for r in usage),
        "output_tokens": sum(r["output_tokens"] for r in usage),
    }


@app.post("/api/ai/{feature}/{ident}", dependencies=[Depends(owner)])
def ai(feature: str, ident: uuid.UUID, payload: dict = Body(default={})):
    from .integrations.llm import infer

    if feature not in {"journal", "tutor"}:
        raise ValueError("Unknown AI action")
    with engine.connect() as conn:
        key = get_secret(conn, "llm_api_key")
        cfg = config(conn).get("llm", {})
        if not key:
            raise HTTPException(
                409, "AI is not configured. Add a provider key in Settings."
            )
        table = s.journal_entries if feature == "journal" else s.lessons
        record = (
            conn.execute(sa.select(table).where(table.c.id == ident)).mappings().first()
        )
        if not record:
            raise HTTPException(404, "Entry or lesson not found")
    result = infer(key, cfg, feature, dict(record), payload.get("messages", []))
    with engine.begin() as conn:
        conn.execute(
            sa.insert(s.ai_usage).values(
                feature=feature,
                provider="openai",
                model=cfg.get("model", "gpt-4.1-mini"),
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            )
        )
        if feature == "journal":
            conn.execute(
                sa.insert(s.ai_feedback).values(
                    entry_id=ident, body=result["text"], provider="openai"
                )
            )
    return result


@app.delete("/api/feedback/{ident}", dependencies=[Depends(owner)])
def delete_feedback(ident: uuid.UUID):
    with engine.begin() as conn:
        from .assistant import purge_journal_history
        purge_journal_history(conn, ident, feedback_only=True)
        conn.execute(sa.delete(s.ai_feedback).where(s.ai_feedback.c.id == ident))
    return {"ok": True}

# Keep existing API routes ahead of the private MCP/OAuth routes.
app.mount("/", mcp_app)
