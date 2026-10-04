import io, zipfile
from test_acceptance import database, client, create
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import engine
from app.services import setting
from app.backup import export_data, restore, archive, parse_backup

def test_experiments_dates_persistence_and_backup(client):
    with engine.begin() as conn: setting(conn,'timezone','Asia/Kolkata')
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    exp=create(client,'experiments',title='Walk first',action='Walk ten minutes',starts_on=str(today-timedelta(days=2)),ends_on=str(today+timedelta(days=11)))
    payload=dict(experiment_id=exp['id'],on_date=str(today),tried=True,feeling=4,note='Easier to begin')
    log=create(client,'experiment_checkins',**payload)
    assert client.post('/api/data/experiment_checkins',json=payload).status_code==409
    assert client.patch('/api/data/experiment_checkins/'+log['id'],json={'feeling':5}).status_code==200
    for delta in (1,-4):
        assert client.post('/api/data/experiment_checkins',json={**payload,'on_date':str(today+timedelta(days=delta))}).status_code==422
    assert client.patch('/api/data/experiments/'+exp['id'],json={'starts_on':str(today+timedelta(days=1))}).status_code==422
    assert client.patch('/api/data/experiments/'+exp['id'],json={'status':'keep'}).status_code==422
    assert client.patch('/api/data/experiments/'+exp['id'],json={'status':'keep','conclusion':'Worth keeping'}).status_code==200
    engine.dispose()
    assert client.get('/api/data/experiment_checkins').json()[0]['feeling']==5
    with engine.begin() as conn: data=export_data(conn)
    with engine.begin() as conn: restore(conn,parse_backup(archive(data)),replace=True)
    assert client.get('/api/data/experiments').json()[0]['conclusion']=='Worth keeping'
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(archive(data))) as source, zipfile.ZipFile(out,'w') as target:
        for name in source.namelist():
            if name.startswith('csv/') or name=='manifest.json': target.writestr(name,source.read(name))
    with engine.begin() as conn: restore(conn,parse_backup(out.getvalue()),replace=True)
    assert client.get('/api/data/experiment_checkins').json()[0]['feeling']==5

def test_reset_atomic_preview_retry_undo_and_conflict(client):
    today=datetime.now(ZoneInfo('UTC')).date()
    tasks=[create(client,'tasks',title=t,due_at='2020-01-01T10:00:00Z') for t in ['Resume','Later','Archive']]
    changes=[dict(focus_after=None,archived=False),dict(focus_after=str(today+timedelta(days=5)),archived=False),dict(archived=True,focus_after=None)]
    body={'request_key':'reset-proof-001','summary':'Intentional reset','operations':[{'action':'update','table':'tasks','record_id':t['id'],'expected_updated_at':t['updated_at'],'data':d} for t,d in zip(tasks,changes)]}
    assert client.post('/api/assistant/preview',json=body).status_code==200
    assert len(client.get('/api/dashboard').json()['tasks'])==3
    result=client.post('/api/assistant/apply',json=body)
    assert result.status_code==200,result.text
    assert client.post('/api/assistant/apply',json=body).json()['duplicate'] is True
    for path in ('/api/dashboard','/api/assistant/morning'):
        assert [t['title'] for t in client.get(path).json()['tasks']]==['Resume']
    agenda=client.get('/api/calendar/agenda?start=2020-01-01T00:00:00Z&end=2020-01-02T00:00:00Z').json()
    assert sorted(r['title'] for r in agenda)==['Later','Resume']
    assert all(t['due_at']==tasks[0]['due_at'] and t['status']=='open' for t in client.get('/api/data/tasks').json())
    assert client.post('/api/tasks/'+tasks[2]['id']+'/complete').status_code==422
    assert client.post('/api/assistant/undo/'+result.json()['batch_id']).status_code==200
    assert len(client.get('/api/dashboard').json()['tasks'])==3
    body['request_key']='reset-conflict-002'
    client.patch('/api/data/tasks/'+tasks[1]['id'],json={'title':'Changed elsewhere'})
    assert client.post('/api/assistant/apply',json=body).status_code==422
    assert all(not t['archived'] and t['focus_after'] is None for t in client.get('/api/data/tasks').json())

def test_return_day_and_old_backup(client):
    with engine.begin() as conn: setting(conn,'timezone','Asia/Kolkata')
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    task=create(client,'tasks',title='Return today',focus_after=str(today),due_at='2020-01-01T10:00:00Z')
    assert len(client.get('/api/dashboard').json()['tasks'])==1
    with engine.begin() as conn: data=export_data(conn)
    data['schema']='0004';data['tables']['alembic_version']=[{'version_num':'0004'}]
    for name in ('experiments','experiment_checkins'): del data['tables'][name]
    for row in data['tables']['tasks']:
        del row['focus_after'];del row['archived']
    with engine.begin() as conn: restore(conn,data,replace=True)
    saved=client.get('/api/data/tasks').json()[0]
    assert saved['id']==task['id'] and saved['focus_after'] is None and saved['archived'] is False
