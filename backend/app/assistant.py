"""Bounded assistant operations shared by MCP and the owner's settings UI."""
import json
import uuid
from datetime import datetime, timedelta, time
from typing import Literal
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from . import schema as s
from .backup import dumps, coerce
from .db import engine
from .security import owner, digest
from .services import config
from .domain import calendar_occurrences
from .operations import complete_task, review_note

router = APIRouter(prefix='/api/assistant', dependencies=[Depends(owner)])
WRITE_TABLES = Literal['tasks', 'journal_entries', 'goals', 'calendar_events', 'learning_topics', 'learning_sessions', 'exams', 'concept_notes', 'problem_attempts', 'reflections']
READ_TABLES = {'tasks','journal_entries','ai_feedback','goals','calendar_events','learning_topics','learning_sessions','exams','concept_notes','problem_attempts','reflections','courses','terms','patterns','lessons','problems'}

class Operation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['create', 'update', 'complete_task', 'review_concept', 'journal_insight']
    table: WRITE_TABLES = 'tasks'
    record_id: uuid.UUID | None = None
    expected_updated_at: datetime | None = None
    # Creation IDs are deterministically derived from the request key + label.
    label: str = Field(default='', max_length=80)
    data: dict = Field(default_factory=dict)

class Batch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=8, max_length=150)
    summary: str = Field(min_length=1, max_length=250)
    chat_url: str | None = Field(default=None, max_length=500)
    operations: list[Operation] = Field(min_length=1, max_length=30)


def clean(value):
    return json.loads(dumps(value))


def record(conn, name, ident, lock=False):
    t = s.TABLES[name]
    q = sa.select(t).where(t.c.id == ident)
    row = conn.execute(q.with_for_update() if lock else q).mappings().first()
    return dict(row) if row else None


def remember(changes, name, before, after):
    changes.append({'table': name, 'id': str((after or before)['id']), 'before': clean(before), 'after': clean(after)})


def expire_undo(conn):
    conn.execute(sa.update(s.assistant_batches).where(s.assistant_batches.c.undo_until < s.now(), s.assistant_batches.c.status == 'applied').values(changes=[], status='expired'))


def check_version(op, old):
    if not old:
        raise ValueError('Record no longer exists; read current context again')
    if not op.expected_updated_at or not op.expected_updated_at.tzinfo or old['updated_at'] != op.expected_updated_at:
        raise ValueError('Record changed or its version is missing; read it again before updating')


def resolve_refs(value, ids):
    if isinstance(value, str) and value.startswith('$'):
        if value[1:] not in ids:
            raise ValueError('Unknown batch label')
        return str(ids[value[1:]])
    if isinstance(value, dict):
        return {k: resolve_refs(v, ids) for k,v in value.items()}
    if isinstance(value, list):
        return [resolve_refs(v, ids) for v in value]
    return value


def execute_batch(conn, batch):
    from .main import validate
    changes, receipts, ids = [], [], {}
    for op in batch.operations:
        if op.label:
            if op.label in ids: raise ValueError('Batch labels must be unique')
            ids[op.label] = uuid.uuid5(uuid.NAMESPACE_URL, 'life-os/'+batch.request_key+'/'+op.label)
    for index, op in enumerate(batch.operations):
        name = op.table
        data = resolve_refs(op.data, ids)
        if len(dumps(data)) > 20000: raise ValueError('Save a concise summary, not a transcript')
        ident = op.record_id
        if op.action == 'complete_task': name = 'tasks'
        if op.action == 'review_concept': name = 'concept_notes'
        old = record(conn, name, ident, True) if ident else None
        if op.action in {'update','complete_task','review_concept'}:
            check_version(op, old)
        if op.action == 'create':
            ident = ids.get(op.label) or uuid.uuid5(uuid.NAMESPACE_URL, f'life-os/{batch.request_key}/{index}')
            data = validate(conn, name, data)
            if name == 'tasks': data['recurrence_anchor'] = data.get('due_at')
            if name == 'concept_notes': data.setdefault('due_on', s.now().astimezone(ZoneInfo(config(conn).get('timezone','UTC'))).date())
            after = dict(conn.execute(sa.insert(s.TABLES[name]).values(id=ident, **data).returning(s.TABLES[name])).mappings().one())
            remember(changes, name, None, after)
        elif op.action == 'update':
            data = validate(conn, name, data, old)
            if name == 'calendar_events': data['sync_state'] = 'dirty' if old['google_event_id'] else 'local'
            conn.execute(sa.update(s.TABLES[name]).where(s.TABLES[name].c.id == ident).values(**data, updated_at=s.now()))
            remember(changes, name, old, record(conn,name,ident))
        elif op.action == 'complete_task':
            result = complete_task(conn, ident)
            remember(changes, name, old, record(conn,name,ident))
            if result['next']:
                remember(changes, name, None, record(conn,name,result['next']))
        elif op.action == 'review_concept':
            if set(data) != {'grade'}: raise ValueError('A concept review requires the owner\'s explicit grade, 0–5')
            review_note(conn, ident, data['grade'])
            remember(changes,name,old,record(conn,name,ident))
            new_review = dict(conn.execute(sa.select(s.reviews).where(s.reviews.c.note_id == ident).order_by(s.reviews.c.created_at.desc()).limit(1)).mappings().one())
            remember(changes,'reviews',None,new_review)
        elif op.action == 'journal_insight':
            if set(data) != {'entry_id','body'} or not isinstance(data['body'],str) or not data['body'].strip():
                raise ValueError('A journal insight needs entry_id and body')
            after = dict(conn.execute(sa.insert(s.ai_feedback).values(entry_id=uuid.UUID(data['entry_id']),body=data['body'],provider='ChatGPT insight').returning(s.ai_feedback)).mappings().one())
            remember(changes,'ai_feedback',None,after)
            ident = after['id']; name='ai_feedback'
        receipts.append({'table':name, 'id':str(ident), 'action':op.action})
    return changes, receipts


def apply_batch(batch: Batch, preview=False):
    if batch.chat_url:
        from urllib.parse import urlsplit
        u=urlsplit(batch.chat_url)
        if u.scheme!='https' or u.hostname!='chatgpt.com' or not u.path.startswith('/c/') or u.query or u.fragment:
            raise ValueError('Provide an actual ChatGPT conversation URL or omit it')
    fingerprint = digest(batch.model_dump_json())
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            # Serialize duplicate request keys across cold starts, including preview.
            conn.execute(sa.text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key':'assistant/'+batch.request_key})
            previous=conn.execute(sa.select(s.assistant_batches).where(s.assistant_batches.c.request_key==batch.request_key)).mappings().first()
            if previous:
                if previous['request_hash'] != fingerprint: raise ValueError('Request key already used for different changes')
                tx.rollback()
                return {'batch_id':str(previous['id']), 'status':previous['status'], 'duplicate':True, 'summary':previous['summary']}
            changes, receipts=execute_batch(conn,batch)
            if preview:
                tx.rollback()
                return {'preview':True,'summary':batch.summary,'changes':changes,'receipts':receipts}
            expire_undo(conn)
            ident=conn.execute(sa.insert(s.assistant_batches).values(request_key=batch.request_key,request_hash=fingerprint,summary=batch.summary,chat_url=batch.chat_url,changes=changes,undo_until=s.now()+timedelta(days=30)).returning(s.assistant_batches.c.id)).scalar_one()
            tx.commit()
            return {'batch_id':str(ident),'status':'applied','summary':batch.summary,'receipts':receipts}
        except Exception:
            if tx.is_active: tx.rollback()
            raise


def undo_batch(ident):
    with engine.begin() as conn:
        batch=record(conn,'assistant_batches',ident,True)
        if not batch: raise ValueError('Change receipt not found')
        if batch['status']=='undone': return {'status':'undone','duplicate':True}
        if batch['status']!='applied' or batch['undo_until'] < s.now(): raise ValueError('This change can no longer be undone')
        # Reverse sequentially, allowing multiple edits to the same row in a batch.
        # Compare complete snapshots, so later owner/Google/assistant edits are preserved.
        for change in reversed(batch['changes']):
            name=change['table']; t=s.TABLES[name]; row_id=uuid.UUID(change['id'])
            current=record(conn,name,row_id,True)
            if clean(current)!=change['after']: raise ValueError('A record changed after this batch; undo would overwrite a later edit')
            if change['before'] is None:
                # Never cascade-delete data created by a later operation outside this batch.
                for child in s.metadata.tables.values():
                    for c in child.c:
                        if any(f.column is t.c.id for f in c.foreign_keys):
                            if conn.execute(sa.select(sa.func.count()).select_from(child).where(c==row_id)).scalar_one():
                                raise ValueError('A later linked record depends on this change')
                conn.execute(sa.delete(t).where(t.c.id==row_id))
            else:
                before=coerce(t,change['before'])
                conn.execute(sa.update(t).where(t.c.id==row_id).values(**before))
        conn.execute(sa.update(s.assistant_batches).where(s.assistant_batches.c.id==ident).values(status='undone',changes=[],updated_at=s.now()))
        return {'status':'undone'}


def search_context(query='', table='tasks', limit=20):
    if table not in READ_TABLES: raise ValueError('This information is not exposed to the assistant')
    limit=max(1,min(limit,50)); t=s.TABLES[table]
    q=sa.select(t)
    if query:
        fields=[c for c in t.c if isinstance(c.type,sa.Text) and c.name in {'title','name','body','summary','next_step','notes'}]
        if not fields: raise ValueError('This table supports listing but not text search')
        term=query[:150].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        q=q.where(sa.or_(*(c.ilike('%'+term+'%',escape='\\') for c in fields)))
    if table=='calendar_events': q=q.where(t.c.deleted_at.is_(None))
    with engine.connect() as conn:
        found=[dict(r) for r in conn.execute(q.order_by(t.c.updated_at.desc()).limit(limit+1)).mappings()]
    return clean({'records':found[:limit],'has_more':len(found)>limit})


def morning_context():
    with engine.connect() as conn:
        tz=ZoneInfo(config(conn).get('timezone','Asia/Kolkata'))
        at=s.now(); today=at.astimezone(tz).date()
        start=datetime.combine(today,time.min,tzinfo=tz); end=start+timedelta(days=1); yesterday=start-timedelta(days=1)
        def fetch(q): return [dict(r) for r in conn.execute(q).mappings()]
        tasks=fetch(sa.select(s.tasks).where(s.tasks.c.status!='done').order_by(s.tasks.c.due_at.asc().nullslast(),s.tasks.c.priority.desc()).limit(40))
        assignments=fetch(sa.select(s.assignments).where(s.assignments.c.status!='done',s.assignments.c.due_at<end+timedelta(days=7)).order_by(s.assignments.c.due_at).limit(30))
        event_rows=fetch(sa.select(s.calendar_events).where(s.calendar_events.c.deleted_at.is_(None),s.calendar_events.c.starts_at<end,sa.or_(s.calendar_events.c.ends_at>start,s.calendar_events.c.recurrence!=[],s.calendar_events.c.master_id.is_not(None))).limit(501))
        events=calendar_occurrences(event_rows[:500],start,end)
        h=s.health_records
        # Summaries stay separated by metric, unit and source: adding multiple providers
        # would double count overlapping records. Latest point readings aren't daily totals.
        activity=fetch(sa.select(h.c.metric,h.c.unit,h.c.source,sa.func.sum(h.c.value).label('sum'),sa.func.min(h.c.recorded_at).label('first_at'),sa.func.max(h.c.recorded_at).label('last_at')).where(h.c.recorded_at>=yesterday,h.c.recorded_at<start,h.c.metric.in_(['steps','water','distance','active_calories','total_calories'])).group_by(h.c.metric,h.c.unit,h.c.source))
        sleep=fetch(sa.select(h.c.metric,h.c.value,h.c.unit,h.c.source,h.c.recorded_at).where(h.c.metric=='sleep',h.c.recorded_at>=yesterday+timedelta(hours=12),h.c.recorded_at<end).order_by(h.c.recorded_at.desc()).limit(30))
        latest=fetch(sa.select(h.c.metric,h.c.value,h.c.unit,h.c.source,h.c.recorded_at).where(~h.c.metric.startswith('samsung_raw/')).distinct(h.c.metric).order_by(h.c.metric,h.c.recorded_at.desc()).limit(50))
        synced=conn.execute(sa.select(sa.func.max(s.integration_runs.c.created_at)).where(s.integration_runs.c.provider=='health-webhook',s.integration_runs.c.status.in_(['ok','partial']))).scalar_one()
        goals=fetch(sa.select(s.goals).where(s.goals.c.status=='active').order_by(s.goals.c.target_date.asc().nullslast()).limit(20))
        topics=fetch(sa.select(s.learning_topics).where(s.learning_topics.c.status!='retired').order_by(s.learning_topics.c.updated_at.desc()).limit(15))
        return clean({'generated_at':at,'timezone':str(tz),'date':today,'tasks':tasks,'assignments':assignments,'calendar':events,'calendar_truncated':len(event_rows)>500,'goals':goals,'learning_topics':topics,'yesterday_activity_by_source':activity,'sleep_records_since_yesterday_noon':sleep,'latest_metric_readings':latest,'last_successful_phone_delivery':synced,'instructions':'Use only dated evidence. Do not combine overlapping sources, call latest samples daily totals, infer sleep from missing records, or invent unavailable stress/water readings. The activity sums describe received records, not guaranteed complete days. Label stale or missing data. Priorities are suggestions; this read does not change tasks.'})


@router.get('/morning')
def morning_api(): return morning_context()

@router.post('/preview')
def preview_api(batch:Batch): return apply_batch(batch,True)

@router.post('/apply')
def apply_api(batch:Batch): return apply_batch(batch)

@router.post('/undo/{ident}')
def undo_api(ident:uuid.UUID): return undo_batch(ident)

@router.get('/changes')
def changes_api():
    with engine.begin() as conn:
        expire_undo(conn)
        b=s.assistant_batches
        return [dict(r) for r in conn.execute(sa.select(b.c.id,b.c.created_at,b.c.summary,b.c.source,b.c.chat_url,b.c.status,b.c.undo_until).order_by(b.c.created_at.desc()).limit(50)).mappings()]


def purge_journal_history(conn, ident, feedback_only=False):
    # A journal deletion must also remove copies retained solely for assistant undo.
    b = s.assistant_batches
    candidates = conn.execute(sa.select(b).where(b.c.changes != []).with_for_update()).mappings()
    for batch in candidates:
        related = any((c['table']=='journal_entries' and c['id']==str(ident)) or
                      (c['table']=='ai_feedback' and any((c.get(side) or {}).get('entry_id')==str(ident) for side in ('before','after')))
                      for c in batch['changes'])
        if feedback_only:
            related = any(c['table']=='ai_feedback' and c['id']==str(ident) for c in batch['changes'])
        if related:
            conn.execute(sa.update(b).where(b.c.id==batch['id']).values(changes=[],summary='Journal content deleted',status='purged',chat_url=None,updated_at=s.now()))
