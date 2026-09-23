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
    with pytest.raises(HTTPException): w.update_event(1,item['id'],EventUpdate(title='앱 수정'))
    # Preserve legacy edits until explicitly resolved.
    with connection() as db:
        db.execute("UPDATE events SET title='앱 수정' WHERE id=?",(item['id'],)); db.commit()
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
    assert g.sync_account(1,1)['conflicts']==[]
    g.resolve_conflict(1,1,'cal','deleted','local')
    assert g.conflicts_for(1,1)==[]
    with connection() as db:link=db.execute('SELECT * FROM google_event_links WHERE event_id=?',(item['id'],)).fetchone()
    assert link['google_id']!='deleted'
    assert link['etag']=='restored'


def test_clinic_completion_requires_submission_and_exposes_generic_url():
    from personal_project import repository as repo
    from personal_project.schemas import SchoolCreate, ClinicRoundCreate
    school = repo.create_school(1, SchoolCreate(admission_year=2026, school_name='제출검증고'))
    clinic = repo.create_clinic_round(1, ClinicRoundCreate(school_id=school['id'], round_number=1, student_names=['학생'], start_time='2026-09-16T09:00:00+09:00', end_time='2026-09-16T10:00:00+09:00'))
    target = clinic['targets'][0]['id']
    repo.get_or_create_target_report(1, target)
    for state, expected in [('ready', 'todo'), ('submitted', 'done'), ('draft', 'todo')]:
        with connection() as db:
            db.execute('UPDATE aura_target_reports SET status=? WHERE target_id=?', (state,target)); db.commit()
        item = w.get_event(1, clinic['eventId'])
        assert item['status'] == expected
        assert item['webUrl'] == f"/personal-project/aura/schools/{school['id']}"
        assert item['completionSource'] == 'external'
        assert item['taskAvailableFrom'] == item['startTime']
        assert item['taskDueAt'] == '2026-09-19T00:00:00Z'
        with connection() as db:
            assert db.execute('SELECT status FROM events WHERE id=?',(item['id'],)).fetchone()[0] == expected
        assert any(e['id'] == item['id'] for e in w.list_events(1, tasks=True))


def test_daily_notes_are_date_and_user_scoped():
    from personal_project.workspace_router import router
    from personal_project.router import current_user_id
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: 901
    client = TestClient(app)
    path = '/api/personal/calendar/daily-notes/2026-09-17'
    drawing = 'data:image/png;base64,drawn'
    assert client.put(path, json={'content':'- [ ] 프로젝트 준비', 'drawing': drawing}).status_code == 200
    assert client.get(path).json()['content'] == '- [ ] 프로젝트 준비'
    assert client.get(path).json()['drawing'] == drawing
    carried = client.get(path.replace('09-17','09-18')).json()
    assert carried['content'] == '- [ ] 프로젝트 준비'
    assert carried['inheritedFrom'] == '2026-09-17'
    assert client.put(path.replace('09-17','09-18'), json={'content':'내일의 메모'}).status_code == 200
    assert client.get(path).json()['content'] == '- [ ] 프로젝트 준비'
    app.dependency_overrides[current_user_id] = lambda: 902
    assert client.get(path).json()['content'] == ''
    assert client.put(path, json={'content':'다른 사용자'}).status_code == 200
    app.dependency_overrides[current_user_id] = lambda: 901
    assert client.get(path).json()['content'] == '- [ ] 프로젝트 준비'
    assert client.put('/api/personal/calendar/daily-notes/invalid', json={'content':'x'}).status_code == 422


def test_generic_task_window_and_future_completion():
    item=w.create_event(1,event(task_available_from='2099-09-16T09:00:00+09:00',task_due_at='2099-09-19T09:00:00+09:00'))
    assert item['completionSource']=='manual'
    with pytest.raises(HTTPException): w.update_event(1,item['id'],EventUpdate(status='done'))
    with pytest.raises(HTTPException): w.update_event(1,item['id'],EventUpdate(task_due_at='2099-09-15T09:00:00+09:00'))


def test_backfill_and_attendance_do_not_override_submission():
    from personal_project import repository as repo
    from personal_project.schemas import SchoolCreate, ClinicRoundCreate, ClinicRoundUpdate
    school=repo.create_school(1,SchoolCreate(admission_year=2026,school_name='동기화고'))
    clinic=repo.create_clinic_round(1,ClinicRoundCreate(school_id=school['id'],round_number=1,student_names=['가','나'],start_time='2026-09-16T09:00:00+09:00',end_time='2026-09-16T10:00:00+09:00'))
    for target in clinic['targets']:
        repo.get_or_create_target_report(1,target['id'])
    with connection() as db:
        db.execute("UPDATE aura_target_reports SET status='submitted' WHERE target_id=?",(clinic['targets'][0]['id'],));db.commit()
    assert w.get_event(1,clinic['eventId'])['status']=='todo'
    repo.update_clinic_round(1,clinic['id'],ClinicRoundUpdate(attendance_status='completed'))
    assert w.get_event(1,clinic['eventId'])['status']=='todo'
    with connection() as db:
        db.execute("UPDATE aura_target_reports SET status='submitted' WHERE target_id=?",(clinic['targets'][1]['id'],))
        db.execute("UPDATE events SET status='todo' WHERE id=?",(clinic['eventId'],));db.commit()
    w.init_workspace()
    assert w.get_event(1,clinic['eventId'])['status']=='done'
    w.init_workspace()
    assert w.get_event(1,clinic['eventId'])['status']=='done'


def test_project_hierarchy_rejects_cycles_and_foreign_owners():
    parent=w.create_project(1,'동아리')[0]['id']
    child=next(p for p in w.create_project(1,'xreal',parent,True) if p['name']=='xreal')['id']
    assert next(p for p in w.projects(1) if p['id']==child)['isolate_tasks']==1
    with pytest.raises(HTTPException): w.update_project(1,parent,'동아리',child,False)
    with pytest.raises(HTTPException): w.create_project(2,'다른 소유자',parent)
    with pytest.raises(HTTPException): w.update_project(2,child,'수정',None,False)
    with pytest.raises(HTTPException): w.create_project(1,'   ')
    w.update_project(1,child,'apro',None,False)
    assert next(p for p in w.projects(1) if p['id']==child)['parent_id'] is None


def test_semester_holidays_and_idempotent_private_import():
    from personal_project import student_services as s
    term=s.Timetable(name='2026-2', starts_on='2026-09-21',ends_on='2026-10-12',
                     excluded_dates=['2026-10-05'],lessons=[{'title':'전공','weekday':0,'start':'09:00','end':'10:30'}])
    preview=s.preview(term)
    assert [e['startTime'][:10] for e in preview['events']]==['2026-09-21','2026-09-28','2026-10-12']
    with pytest.raises(HTTPException): s.import_timetable(9842,term)
    s.save_profile(9842,s.Profile(is_student=True,school='다른 대학교'))
    assert s.import_timetable(9842,term)['created']==3
    assert s.import_timetable(9842,term)['alreadyImported']
    assert all(e['status']=='passive' for e in w.list_events(9842))
    assert w.list_events(9843)==[]
    public_holiday=s.Timetable(name='휴일검증',starts_on='2026-03-02',ends_on='2026-03-02',lessons=[{'title':'휴강','weekday':0,'start':'09:00','end':'10:30'}])
    assert len(s.preview(public_holiday)['events'])==0
    assert len(s.preview(public_holiday)['skipped'])==1


def test_project_api_scope_idempotency_and_revocation():
    from personal_project import project_connectors as c
    p=w.create_project(1,'연동 프로젝트')[0]['id']
    with pytest.raises(HTTPException): c.create(2,p,'외부 서비스')
    connector=c.create(1,p,'외부 서비스')
    key=connector['token']
    result=c.upsert(key,'meeting-1',event(project_id=999,status='todo'))
    item=w.get_event(1,result['eventId'])
    assert item['projectId']==p and item['canEdit'] is False
    assert item['completionSource']=='external'
    again=c.upsert(key,'meeting-1',event(status='done'))
    assert again==result and w.get_event(1,result['eventId'])['status']=='done'
    with pytest.raises(HTTPException): w.update_event(1,result['eventId'],EventUpdate(title='원본 변조'))
    with pytest.raises(HTTPException): w.get_event(2,result['eventId'])
    assert 'token_hash' not in c.list_connectors(1,p)[0]
    c.revoke(1,p,connector['id'])
    with pytest.raises(HTTPException): c.upsert(key,'meeting-2',event())


def test_curriculum_revision_conflicts_and_department_calendar(monkeypatch):
    from personal_project import student_services as s, student_community as c
    for uid,school in [(901,'위키대'),(902,'위키대'),(903,'다른대')]:
        s.save_profile(uid,s.Profile(is_student=True,school=school,department='컴퓨터공학'))
    data=c.CurriculumEdit(cohort=2026,track='double',content='복수전공 참고 규정')
    assert c.revise(901,data)['versions'][0]['revision']==1
    with pytest.raises(HTTPException) as conflict: c.revise(902,data)
    assert conflict.value.status_code==409
    official=c.CurriculumEdit(cohort=2026,edition='official',content='검토 규정',source_url='https://example.ac.kr/rules')
    with pytest.raises(HTTPException): c.revise(901,official)
    monkeypatch.setenv('STUDENT_CURRICULUM_EDITORS','901')
    assert c.revise(901,official)['versions'][0]['edition']=='official'
    assert c.curriculum(903,2026,'double')['versions']==[]
    post=c.post(901,c.Post(title='학과 세미나',start='2026-09-25T10:00:00+09:00',end='2026-09-25T11:00:00+09:00'))[0]
    assert c.posts(902)[0]['id']==post['id']
    assert c.posts(903)==[]
    with pytest.raises(HTTPException): c.hide_post(902,post['id'])
    result=c.add_to_calendar(902,post['id'])
    assert not result['alreadyAdded']
    assert c.add_to_calendar(902,post['id'])['alreadyAdded']
    with pytest.raises(HTTPException): c.add_to_calendar(903,post['id'])
    c.hide_post(901,post['id'])
    assert c.posts(902)==[]


def test_google_transfer_preview_ownership_changes_and_retry(monkeypatch):
    import httpx, json
    from datetime import date
    from personal_project import google_calendar as g, google_transfer as transfer
    own=w.create_event(1,event())
    w.create_event(2,event())
    with connection() as db:
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','내 캘린더',1,1)");db.commit()
    remotes={}; writes=[]
    def handler(req):
        key=req.url.path.split('/')[-1]
        if req.method=='GET':
            if key=='events': return httpx.Response(200,json={'items':list(remotes.values())})
            return httpx.Response(200,json=remotes[key]) if key in remotes else httpx.Response(404,json={})
        body=json.loads(req.content);writes.append(req.method)
        if req.method=='POST': key=body['id']
        else: assert req.headers['If-Match']==remotes[key]['etag']
        remotes[key]={**body,'id':key,'etag':str(len(writes))}
        return httpx.Response(200,json=remotes[key])
    monkeypatch.setattr(g,'client',lambda _:httpx.Client(base_url=g.ROOT,transport=httpx.MockTransport(handler)))
    args=(1,1,'cal',date(2026,9,1),date(2026,9,30))
    with pytest.raises(HTTPException): transfer.transfer(2,*args[1:])
    plan=transfer.transfer(*args)
    assert plan['create']==1 and writes==[]
    w.update_event(1,own['id'],EventUpdate(title='변경된 제목'))
    with pytest.raises(HTTPException) as exc: transfer.transfer(*args,plan['preview_token'])
    assert exc.value.status_code==409 and writes==[]
    plan=transfer.transfer(*args);assert transfer.transfer(*args,plan['preview_token'])['exported']==1
    assert writes==['POST']
    plan=transfer.transfer(*args);assert plan['unchanged']==1
    transfer.transfer(*args,plan['preview_token']);assert writes==['POST']
    w.update_event(1,own['id'],EventUpdate(title='앱 최종'))
    g.sync_account(1,1);assert writes==['POST']
    assert w.get_event(1,own['id'])['title']=='앱 최종'
    plan=transfer.transfer(*args);assert plan['update']==1
    next(iter(remotes.values()))['etag']='remote-change'
    with pytest.raises(HTTPException):transfer.transfer(*args,plan['preview_token'])
    plan=transfer.transfer(*args);transfer.transfer(*args,plan['preview_token'])
    assert writes==['POST','PATCH']
    assert next(iter(remotes.values()))['summary']=='앱 최종'


def test_google_transfer_partial_failure_is_retryable_without_duplicates(monkeypatch):
    import httpx,json
    from datetime import date
    from personal_project import google_calendar as g, google_transfer as transfer
    w.create_event(1,event());w.create_event(1,event())
    with connection() as db:
        db.execute("INSERT INTO google_accounts VALUES(1,1,'sub','a@gmail.com','calendar','encrypted','scope',NULL,NULL)")
        db.execute("INSERT INTO google_calendars VALUES(1,'cal','내 캘린더',1,0)");db.commit()
    remotes={}; fail=[True]; writes=[]
    def handler(req):
        key=req.url.path.split('/')[-1]
        if req.method=='GET': return httpx.Response(200,json=remotes[key]) if key in remotes else httpx.Response(404,json={})
        assert req.method=='POST' and req.url.params['sendUpdates']=='none'
        if len(remotes)==1 and fail[0]: return httpx.Response(503,json={})
        body=json.loads(req.content);remotes[body['id']]={**body,'etag':'one'};writes.append(body['id'])
        return httpx.Response(200,json=remotes[body['id']])
    monkeypatch.setattr(g,'client',lambda _:httpx.Client(base_url=g.ROOT,transport=httpx.MockTransport(handler)))
    args=(1,1,'cal',date(2026,9,1),date(2026,9,30))
    plan=transfer.transfer(*args)
    with pytest.raises(HTTPException) as exc:transfer.transfer(*args,plan['preview_token'])
    assert '1건 처리 후' in exc.value.detail
    fail[0]=False;plan=transfer.transfer(*args)
    assert plan['unchanged']==1 and plan['create']==1
    transfer.transfer(*args,plan['preview_token'])
    assert len(writes)==len(set(writes))==2
    with connection() as db:assert db.execute('SELECT enabled FROM google_calendars').fetchone()[0]==0
