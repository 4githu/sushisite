"""Run with PERSONAL_PROJECT_DB_PATH pointing to a temporary DB; never touch live schedules."""
import os
import tempfile
from pathlib import Path
os.environ['PERSONAL_PROJECT_DB_PATH'] = str(Path(tempfile.mkdtemp(prefix='calendar-tests-'))/'calendar.db')

import pytest
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace as w
from personal_project.db import connection
from personal_project.schemas import EventCreate, EventUpdate, EventScopeUpdate, EventSeriesCreate
from personal_project.google_calendar import fingerprint, google_body, fields
from auth import google_oauth as oauth

@pytest.fixture(autouse=True)
def clean():
    with connection() as db:
        db.execute('DELETE FROM events'); db.execute('DELETE FROM calendar_projects');db.execute('DELETE FROM google_accounts');db.execute('DELETE FROM google_oauth_states');db.commit()

def event(**kw):
    return EventCreate(**dict(title='세미나',start_time='2026-09-16T09:00:00+09:00',end_time='2026-09-16T10:00:00+09:00',**kw))

def test_invite_is_email_bound_and_completion_private():
    p=w.create_project(1,'스시과 일정')[0]['id']
    token=w.invite(1,p,'member@gmail.com')['token']
    with pytest.raises(HTTPException):w.accept(2,token,'attacker@gmail.com')
    w.accept(2,token,'member@gmail.com')
    with pytest.raises(HTTPException):w.accept(3,token,'member@gmail.com')
    item=w.create_event(1,event(project_id=p))
    w.update_event(2,item['id'],EventUpdate(status='done'))
    assert w.get_event(2,item['id'])['status']=='done'
    assert w.get_event(1,item['id'])['status']=='todo'
    with pytest.raises(HTTPException):w.get_event(3,item['id'])
    with pytest.raises(HTTPException):w.update_event(3,item['id'],EventUpdate(title='stolen'))
    with pytest.raises(HTTPException):w.delete_event(3,item['id'])
    w.update_event(2,item['id'],EventUpdate(title='공유 수정'))
    assert w.get_event(1,item['id'])['title']=='공유 수정'

def test_private_access_and_time_validation():
    item=w.create_event(1,event(location='301호',web_url='https://example.com'))
    assert w.list_events(2)==[]
    assert w.get_event(1,item['id'])['location']=='301호'
    with pytest.raises(HTTPException):w.update_event(1,item['id'],EventUpdate(end_time='2026-09-16T08:00:00+09:00'))
    assert w.get_event(1,item['id'])['endTime'].endswith('10:00:00+09:00')
    assert len(w.list_events(1,'2026-09-16T00:00:00Z','2026-09-16T02:00:00Z'))==1

def test_recurring_updates_preserve_offsets():
    data=EventSeriesCreate(**event().model_dump(),repeat_count=3)
    items=w.create_series(1,data)
    w.update_event(1,items[1]['id'],EventScopeUpdate(start_time='2026-09-23T10:00:00+09:00',end_time='2026-09-23T11:00:00+09:00',scope='following'))
    assert 'T09:00' in w.get_event(1,items[0]['id'])['startTime']
    assert '2026-09-30T10:00' in w.get_event(1,items[2]['id'])['startTime']
    w.delete_event(1,items[1]['id'],'following')
    assert len(w.list_events(1))==1

def test_google_all_day_and_completion_not_in_fingerprint():
    item=w.create_event(1,event())
    with connection() as db: row=dict(db.execute('SELECT * FROM events WHERE id=?',(item['id'],)).fetchone())
    before=fingerprint(row); row['status']='done';assert fingerprint(row)==before
    row.update(is_all_day=1,start_time='2026-09-16T00:00:00',end_time='2026-09-17T00:00:00')
    body=google_body(row)
    assert body['end']=={'date':'2026-09-17'}
    assert fields(body)['is_all_day'] is True

def test_oauth_state_browser_binding_and_replay(monkeypatch):
    monkeypatch.setenv('CALANDER_OATHID','test-client');monkeypatch.setenv('CLADNDER_OATHKEY','test-secret')
    app=FastAPI();app.include_router(oauth.router)
    c=TestClient(app,base_url='https://aura.chobab.app')
    res=c.get('/auth/google/start',follow_redirects=False)
    assert res.status_code==307
    from urllib.parse import parse_qs,urlsplit
    query=parse_qs(urlsplit(res.headers['location']).query)
    assert query['redirect_uri']==['https://aura.chobab.app/auth/google/callback']
    assert query['code_challenge_method']==['S256']
    state=query['state'][0]
    stranger=TestClient(app,base_url='https://aura.chobab.app')
    assert stranger.get('/auth/google/callback',params={'state':state,'error':'access_denied'}).status_code==400
    res=c.get('/auth/google/callback',params={'state':state,'error':'access_denied'},follow_redirects=False)
    assert res.status_code==303
    assert c.get('/auth/google/callback',params={'state':state,'error':'access_denied'}).status_code==400
    assert c.get('/auth/google/start?return_to=//evil.example').status_code==400

def test_rehear_google_oauth_is_disabled():
    app=FastAPI();app.include_router(oauth.router)
    client=TestClient(app,base_url='https://rehear.chobab.app')
    assert client.get('/auth/google/start?return_to=%2Fodi').status_code==410

def test_readonly_import_cannot_be_edited():
    item=w.create_event(1,event())
    with connection() as db:
        db.execute("UPDATE events SET type='google' WHERE id=?",(item['id'],))
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','공유 읽기전용',0,1)")
        db.execute("INSERT INTO google_event_links VALUES(1,'cal','remote',?,NULL,NULL,'google')",(item['id'],));db.commit()
    assert w.get_event(1,item['id'])['canEdit'] is False
    with pytest.raises(HTTPException):w.update_event(1,item['id'],EventUpdate(title='bad'))
    with pytest.raises(HTTPException):w.delete_event(1,item['id'])


def test_sync_idempotent_import_conflict_and_remote_resolution(monkeypatch):
    import httpx
    from personal_project import google_calendar as g
    with connection() as db:
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','내 캘린더',1,1)");db.commit()
    remote={'id':'g1','etag':'one','summary':'구글 일정','start':{'dateTime':'2026-09-16T09:00:00+09:00'},'end':{'dateTime':'2026-09-16T10:00:00+09:00'}}
    def handler(req):
        if req.method=='PATCH':return httpx.Response(412,json={})
        if req.url.path.endswith('/g1'):return httpx.Response(200,json=remote)
        return httpx.Response(200,json={'items':[remote]})
    monkeypatch.setattr(g,'client',lambda _:httpx.Client(base_url=g.ROOT,transport=httpx.MockTransport(handler)))
    assert g.sync_account(1,1)['updated']==1
    assert g.sync_account(1,1)['updated']==0
    assert len(w.list_events(1))==1
    item=w.list_events(1)[0]
    w.update_event(1,item['id'],EventUpdate(title='앱 수정'))
    remote.update(summary='구글 동시 수정',etag='two')
    assert g.sync_account(1,1)['conflicts']==['앱 수정']
    assert w.get_event(1,item['id'])['title']=='앱 수정'
    assert len(g.conflicts_for(1,1))==1
    g.resolve_conflict(1,1,'cal','g1','google')
    assert w.get_event(1,item['id'])['title']=='구글 동시 수정'
    assert g.conflicts_for(1,1)==[]
    remote['status']='cancelled'
    g.sync_account(1,1)
    assert w.list_events(1)==[]


def test_export_is_idempotent_and_accounts_are_owned(monkeypatch):
    import httpx,json
    from personal_project import google_calendar as g
    item=w.create_event(1,event())
    with connection() as db:
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','내 캘린더',1,1)");db.commit()
    calls=[]
    def handler(req):
        calls.append(req.method);body=json.loads(req.content);return httpx.Response(200,json={**body,'etag':'v1'})
    monkeypatch.setattr(g,'client',lambda _:httpx.Client(base_url=g.ROOT,transport=httpx.MockTransport(handler)))
    with pytest.raises(HTTPException):g.export_event(2,1,'cal',item['id'])
    assert g.export_event(1,1,'cal',item['id'])['exported']
    assert not g.export_event(1,1,'cal',item['id'])['exported']
    assert calls==['POST']


def test_widget_pair_one_use_feed_scoped_and_revocable():
    from personal_project import workspace_router as r
    app=FastAPI();app.include_router(r.router);app.dependency_overrides[r.current_user_id]=lambda:1
    c=TestClient(app)
    w.create_event(1,event());w.create_event(2,event())
    code=c.post('/api/personal/calendar/widget/pair').json()['code']
    res=c.post('/api/personal/calendar/widget/claim',json={'token':code})
    assert res.status_code==200
    token=res.json()['token']
    assert c.post('/api/personal/calendar/widget/claim',json={'token':code}).status_code==400
    assert c.get('/api/personal/calendar/widget/feed',headers={'Authorization':'Bearer '+token}).status_code==200
    c.delete('/api/personal/calendar/widget/devices')
    assert c.get('/api/personal/calendar/widget/feed',headers={'Authorization':'Bearer '+token}).status_code==401


def test_aura_edit_uses_clinic_rules_and_delete_cascades():
    from personal_project import repository as repo
    from personal_project.schemas import SchoolCreate,ClinicRoundCreate
    school=repo.create_school(1,SchoolCreate(admission_year=2026,school_name='검증고'))
    clinic=repo.create_clinic_round(1,ClinicRoundCreate(school_id=school['id'],round_number=1,student_names=['검증학생'],start_time='2026-09-16T09:00:00+09:00',end_time='2026-09-16T10:00:00+09:00'))
    w.update_event(1,clinic['eventId'],EventUpdate(start_time='2026-09-16T10:00:00+09:00',end_time='2026-09-16T12:00:00+09:00',location='302호'))
    updated=repo.get_clinic_round(1,clinic['id'])
    assert 'T10:00' in updated['startTime']
    assert updated['amount']>clinic['amount']
    assert w.get_event(1,clinic['eventId'])['location']=='302호'
    w.delete_event(1,clinic['eventId'])
    with pytest.raises(HTTPException):repo.get_clinic_round(1,clinic['id'])


def test_deleted_google_event_conflict_can_restore_app_copy(monkeypatch):
    import httpx,json
    from personal_project import google_calendar as g
    item=w.create_event(1,event())
    with connection() as db:
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','내 캘린더',1,1)")
        db.execute("INSERT INTO google_event_links VALUES(1,'cal','deleted',?,'old','old','local')",(item['id'],));db.commit()
    def handler(req):
        if req.method=='POST':return httpx.Response(200,json={**json.loads(req.content),'etag':'restored'})
        if req.url.path.endswith('/events'):return httpx.Response(200,json={'items':[]})
        return httpx.Response(410,json={})
    monkeypatch.setattr(g,'client',lambda _:httpx.Client(base_url=g.ROOT,transport=httpx.MockTransport(handler)))
    assert g.sync_account(1,1)['conflicts']==['세미나']
    g.resolve_conflict(1,1,'cal','deleted','local')
    assert g.conflicts_for(1,1)==[]
    with connection() as db:link=db.execute('SELECT * FROM google_event_links WHERE event_id=?',(item['id'],)).fetchone()
    assert link['google_id']!='deleted'
    assert link['etag']=='restored'
