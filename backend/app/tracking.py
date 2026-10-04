"""Saved-session timing, derived personal records, and timezone-aware activity."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from . import schema as s
from .db import engine
from .security import owner
from .services import config

router = APIRouter(prefix='/api', dependencies=[Depends(owner)])

class StartWorkout(BaseModel):
    title: str = Field(min_length=1, max_length=200)

@router.post('/physical/sessions/start')
def start_workout(body: StartWorkout):
    if not body.title.strip():
        raise HTTPException(422, 'Give your workout a name.')
    with engine.begin() as conn:
        # Serialize starts for the single owner. Retrying returns the same active session.
        conn.execute(sa.select(s.owners.c.id).with_for_update()).all()
        active = conn.execute(sa.select(s.workouts).where(
            s.workouts.c.started_at.isnot(None), s.workouts.c.ended_at.is_(None))).mappings().first()
        if active:
            return dict(active)
        now = s.now()
        return dict(conn.execute(sa.insert(s.workouts).values(
            title=body.title.strip(), performed_at=now, started_at=now
        ).returning(s.workouts)).mappings().one())

@router.post('/physical/sessions/{ident}/finish')
def finish_workout(ident: UUID):
    with engine.begin() as conn:
        row = conn.execute(sa.select(s.workouts).where(s.workouts.c.id == ident).with_for_update()).mappings().first()
        if not row:
            raise HTTPException(404, 'Workout not found.')
        if not row['started_at']:
            raise HTTPException(422, 'This workout has no start time. Edit its timing instead.')
        if row['ended_at']:
            return dict(row)
        now = s.now()
        if row['started_at'] > now:
            raise HTTPException(422, 'Start time is in the future. Correct it before finishing.')
        return dict(conn.execute(sa.update(s.workouts).where(s.workouts.c.id == ident).values(
            ended_at=now, updated_at=now).returning(s.workouts)).mappings().one())

@router.get('/physical/records')
def personal_records():
    # Derived on read: edits/deletes/backdated sessions rebuild the history correctly.
    with engine.connect() as conn:
        records = conn.execute(sa.select(
            s.workout_sets, s.exercises.c.name.label('exercise'),
            s.workouts.c.performed_at, s.workouts.c.title.label('workout')
        ).join(s.workouts, s.workout_sets.c.workout_id == s.workouts.c.id)
         .join(s.exercises, s.workout_sets.c.exercise_id == s.exercises.c.id)
         .where(s.workouts.c.performed_at <= s.now())
         .order_by(s.workouts.c.performed_at, s.workout_sets.c.created_at, s.workout_sets.c.id)).mappings()
        groups = {}
        for r in records:
            key = str(r['exercise_id'])
            group = groups.setdefault(key, {'exercise_id': key, 'exercise': r['exercise'],
                'heaviest': None, 'rep_bests': {}, 'history': [], 'sets': 0})
            entry = {k: r[k] for k in ('id', 'workout_id', 'workout', 'performed_at', 'weight_kg', 'reps')}
            group['sets'] += 1
            reasons = []
            if r['weight_kg'] > 0 and (group['heaviest'] is None or r['weight_kg'] > group['heaviest']['weight_kg']):
                group['heaviest'] = entry
                reasons.append('Heaviest weight')
            weight = r['weight_kg']
            best = group['rep_bests'].get(weight)
            if best is None or r['reps'] > best['reps']:
                group['rep_bests'][weight] = entry
                reasons.append('First record at this weight' if best is None else 'Rep record at this weight')
            if reasons:
                group['history'].append({**entry, 'reasons': reasons})
        for group in groups.values():
            group['rep_bests'] = [group['rep_bests'][w] for w in sorted(group['rep_bests'], reverse=True)]
            group['history'].reverse()
        return sorted(groups.values(), key=lambda x: x['exercise'].casefold())

@router.get('/activity/{kind}')
def activity(kind: Literal['physical', 'academics', 'dsa'], year: int = Query(ge=1900, le=2200)):
    with engine.connect() as conn:
        tz = ZoneInfo(config(conn).get('timezone', 'UTC'))
        now = s.now()
        today = now.astimezone(tz).date()
        start = datetime(year, 1, 1, tzinfo=tz)
        end = min(datetime(year + 1, 1, 1, tzinfo=tz), now)
        days = defaultdict(lambda: {'count': 0, 'minutes': 0, 'timed_entries': 0, 'entries': []})
        def add(at, label, ident, minutes=None):
            day = at.astimezone(tz).date().isoformat()
            bucket = days[day]
            bucket['count'] += 1
            if minutes is not None:
                bucket['minutes'] += minutes
                bucket['timed_entries'] += 1
            bucket['entries'].append({'id': str(ident), 'label': label, 'at': at, 'minutes': minutes})
        def during(column):
            return sa.and_(column >= start, column < end)
        if kind == 'physical':
            for r in conn.execute(sa.select(s.workouts).where(during(s.workouts.c.performed_at))).mappings():
                minutes = (r['ended_at'] - r['started_at']).total_seconds() / 60 if r['ended_at'] and r['started_at'] else None
                add(r['performed_at'], r['title'], r['id'], minutes)
        else:
            link = s.learning_topics.c.course_id if kind == 'academics' else s.learning_topics.c.pattern_id
            query = sa.select(s.learning_sessions, s.learning_topics.c.title).join(
                s.learning_topics, s.learning_sessions.c.topic_id == s.learning_topics.c.id
            ).where(link.isnot(None), during(s.learning_sessions.c.studied_at))
            for r in conn.execute(query).mappings():
                add(r['studied_at'], r['title'] + ' · ' + r['kind'], r['id'], r['minutes'])
            if kind == 'dsa':
                for r in conn.execute(sa.select(s.problem_attempts, s.problems.c.title).join(
                    s.problems, s.problem_attempts.c.problem_id == s.problems.c.id
                ).where(during(s.problem_attempts.c.attempted_at))).mappings():
                    add(r['attempted_at'], r['title'] + (' · solved' if r['solved'] else ' · attempted'), r['id'], r['minutes'])
                for r in conn.execute(sa.select(s.reviews, s.concept_notes.c.title).join(
                    s.concept_notes, s.reviews.c.note_id == s.concept_notes.c.id
                ).where(during(s.reviews.c.reviewed_at))).mappings():
                    add(r['reviewed_at'], r['title'] + ' · review', r['id'])
        for bucket in days.values():
            bucket['minutes'] = round(bucket['minutes'], 1)
            bucket['entries'].sort(key=lambda x: x['at'])
        return {'year': year, 'timezone': str(tz), 'today': today, 'days': dict(days),
                'active_days': len(days), 'total': sum(d['count'] for d in days.values())}
