"""Shared transactional task and concept-review operations."""
import json
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException
from . import schema as s
from .services import config
from .domain import next_task_date, sm2
from .backup import dumps

def complete_task(conn, ident):
    task = (
        conn.execute(
            sa.select(s.tasks).where(s.tasks.c.id == ident).with_for_update()
        )
        .mappings()
        .first()
    )
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] == "done":
        return {"ok": True, "next": None}
    unfinished = conn.execute(
        sa.select(sa.func.count())
        .select_from(s.tasks)
        .where(s.tasks.c.parent_id == ident, s.tasks.c.status != "done")
    ).scalar()
    if unfinished:
        raise ValueError("Complete the subtasks first")
    at = s.now()
    conn.execute(
        sa.update(s.tasks)
        .where(s.tasks.c.id == ident)
        .values(status="done", completed_at=at, updated_at=at)
    )
    next_id = None
    if task["rrule"]:
        nxt = next_task_date(
            task["rrule"],
            task["recurrence_anchor"] or task["due_at"],
            at,
            config(conn).get("timezone", "UTC"),
        )
        if nxt:
            data = {
                k: v
                for k, v in task.items()
                if k not in {"id", "created_at", "updated_at", "completed_at"}
            }
            # A completed parent's historical subtasks must not acquire future children.
            # A recurring subtask's next instance is independent and can be re-parented.
            data.update(
                status="open", due_at=nxt, previous_id=ident, parent_id=None
            )
            next_id = conn.execute(
                pg_insert(s.tasks)
                .values(**data)
                .on_conflict_do_nothing(index_elements=[s.tasks.c.previous_id])
                .returning(s.tasks.c.id)
            ).scalar_one_or_none()
    return {"ok": True, "next": next_id}


def review_note(conn, ident, grade):
    note = (
        conn.execute(
            sa.select(s.concept_notes)
            .where(s.concept_notes.c.id == ident)
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not note:
        raise HTTPException(404, "Concept note not found")
    state = {
        k: note[k]
        for k in ("ease_factor", "repetitions", "interval_days", "due_on")
    }
    at = s.now()
    today = at.astimezone(ZoneInfo(config(conn).get("timezone", "UTC"))).date()
    nxt = sm2(state, grade, today)
    conn.execute(
        sa.update(s.concept_notes)
        .where(s.concept_notes.c.id == ident)
        .values(**nxt, updated_at=at)
    )
    conn.execute(
        sa.insert(s.reviews).values(
            note_id=ident,
            grade=grade,
            reviewed_at=at,
            previous_state=json.loads(dumps(state)),
            next_state=json.loads(dumps(nxt)),
        )
    )
    return nxt


