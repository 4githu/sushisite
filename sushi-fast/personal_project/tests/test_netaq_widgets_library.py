import hashlib
import json
import pytest
from datetime import timedelta
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from personal_project import drive, drive_library as lib, workspace
from personal_project import drive_router, workspace_router, community_v2
from personal_project.router import current_user_id
from personal_project.db import connection, DB_PATH
from personal_project.schemas import EventCreate, EventSeriesCreate, EventScopeUpdate, EventUpdate


@pytest.fixture
def client(tmp_path,monkeypatch):
    # Refuse every destructive fixture statement unless collection selected the isolated test DB.
    assert 'personal-pytest-' in str(DB_PATH) and str(DB_PATH).endswith('/test.sqlite'), DB_PATH
    monkeypatch.setattr(drive,'ROOT',tmp_path/'files')
    with connection() as db:
        for name in ['drive_folders','drive_file_folders','drive_share_links','personal_drive_items','widget_pairs','widget_devices','personal_documents','personal_document_history','calendar_daily_notes','events']:
            db.execute(f'DELETE FROM {name}')
        db.commit()
    app=FastAPI();app.include_router(workspace_router.router);app.include_router(drive_router.router)
    def user(request:Request):return int(request.headers.get('x-user','1'))
    app.dependency_overrides[current_user_id]=user
    return TestClient(app)


def file(tmp_path,uid=1,bucket='archive'):
    source=tmp_path/'upload.txt';source.write_text('private file')
    return drive.store(uid,source,'자료.txt','text/plain',bucket,'local',None,12)['id']


def headers(client,uid=1):
    pair=client.post('/api/personal/calendar/widget/pair',headers={'x-user':str(uid)}).json()
    claimed=client.post('/api/personal/calendar/widget/claim',json={'token':pair['code'],'platform':'Windows'})
    assert claimed.status_code==200
    assert client.post('/api/personal/calendar/widget/claim',json={'token':pair['code']}).status_code==400
    return {'Authorization':'Bearer '+claimed.json()['token']}


def test_folder_organization_is_private_and_nonempty_folder_is_protected(client,tmp_path):
    fid=lib.create_folder(1,'실험','archive')['id'];nested=lib.create_folder(1,'자료','archive',fid)['id']
    item=file(tmp_path)
    assert client.put(f'/api/personal/drive/items/{item}/organization',json={'name':'실험.txt','folder_id':nested}).status_code==200
    assert lib.library(1,'archive',nested)['placements'][item]==nested
    assert [f['id'] for f in lib.library(1,'archive',nested)['trail']]==[fid,nested]
    assert client.get(f'/api/personal/drive/library?folder_id={fid}',headers={'x-user':'2'}).status_code==404
    assert client.delete(f'/api/personal/drive/folders/{nested}').status_code==409
    assert client.put(f'/api/personal/drive/items/{item}/organization',headers={'x-user':'2'},json={'name':'도용','folder_id':None}).status_code==404
    client.put(f'/api/personal/drive/items/{item}/organization',json={'name':'실험.txt','folder_id':None})
    assert client.delete(f'/api/personal/drive/folders/{nested}').status_code==204


def test_share_links_expire_revoke_and_never_grant_other_file_access(client,tmp_path):
    item=file(tmp_path);other=file(tmp_path,2)
    link=client.post(f'/api/personal/drive/items/{item}/share',json={'days':7}).json()['token']
    url=f'/api/personal/drive/shared/{link}'
    assert client.get(url).json()['name']=='자료.txt'
    response=client.get(url+'/content');assert response.status_code==200 and response.content==b'private file'
    assert 'attachment' in response.headers['content-disposition']
    assert client.get(f'/api/personal/drive/items/{other}/content').status_code==404
    assert client.post(f'/api/personal/drive/items/{item}/share',headers={'x-user':'2'},json={}).status_code==404
    with connection() as db:
        assert db.execute('SELECT token_hash FROM drive_share_links').fetchone()[0]!=link
    client.delete(f'/api/personal/drive/items/{item}/share')
    assert client.get(url+'/content').status_code==404
    expired=lib.share(1,item,1)['token']
    with connection() as db:
        db.execute('UPDATE drive_share_links SET expires_at=?',((drive.now()-timedelta(seconds=1)).isoformat(),));db.commit()
    assert client.get('/api/personal/drive/shared/'+expired).status_code==404


def test_widget_capture_is_idempotent_and_owner_scoped_and_revocable(client):
    auth=headers(client);foreign=headers(client,2)
    payload={'id':'stable-id','text':'날짜 없는 기록'}
    for _ in range(2):assert client.post('/api/personal/calendar/widget/capture',headers=auth,json=payload).status_code==200
    doc=community_v2.document('netaq-captures-v1',1)
    assert len(doc['data']['items'])==1
    assert community_v2.document('netaq-captures-v1',2)['data'] is None
    doc['data']['items'][0].update(kind='task',today=drive.now().astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul')).date().isoformat())
    community_v2.save_document('netaq-captures-v1',community_v2.DocumentWrite(**doc),1)
    assert client.post('/api/personal/calendar/widget/task',headers=foreign,json={'source':'capture','id':'stable-id','done':True}).status_code==404
    for _ in range(2):assert client.post('/api/personal/calendar/widget/task',headers=auth,json={'source':'capture','id':'stable-id','done':True}).status_code==200
    assert community_v2.document('netaq-captures-v1',1)['data']['items'][0]['done'] is True
    assert client.delete('/api/personal/calendar/widget/device',headers=auth).status_code==204
    assert client.get('/api/personal/calendar/widget/feed',headers=auth).status_code==401


def test_widget_completion_respects_event_access_and_note_inheritance(client):
    auth=headers(client)
    event=workspace.create_event(2,EventCreate(title='다른 계정',start_time='2026-11-16T10:00:00+09:00',end_time='2026-11-16T11:00:00+09:00',status='todo'))
    assert client.post('/api/personal/calendar/widget/task',headers=auth,json={'source':'event','id':str(event['id']),'done':True}).status_code in (403,404)
    with connection() as db:
        db.execute("INSERT INTO calendar_daily_notes(user_id,day,content,drawing) VALUES(1,'2026-11-10','- [x] 원본 체크','')");db.commit()
    response=client.get('/api/personal/calendar/widget/feed?view=day&anchor=2026-11-16',headers=auth)
    assert response.status_code==200 and response.json()['note']=='- [x] 원본 체크'
    assert response.json()['noteDate']=='2026-11-10'
    with connection() as db:assert db.execute("SELECT count(*) FROM calendar_daily_notes WHERE day='2026-11-16'").fetchone()[0]==0


def test_monthly_and_daily_recurrence_keeps_calendar_intent(client):
    data=EventSeriesCreate(title='월말 정리',start_time='2028-01-31T09:00:00+09:00',end_time='2028-01-31T10:00:00+09:00',repeat_count=3,repeat_unit='month',repeat_interval=1)
    events=workspace.create_series(1,data)
    assert [e['startTime'][:10] for e in events]==['2028-01-31','2028-02-29','2028-03-31']
    data=data.model_copy(update={'repeat_unit':'day','repeat_interval':2})
    assert [e['startTime'][:10] for e in workspace.create_series(1,data)]==['2028-01-31','2028-02-02','2028-02-04']


def test_multidate_batch_is_deduplicated_and_all_scope_preserves_durations(client):
    data=EventSeriesCreate(title='여러 날짜',start_time='2026-11-16T09:00:00+09:00',end_time='2026-11-16T10:00:00+09:00',selected_dates=['2026-11-16','2026-11-20','2026-11-20','2026-11-23'])
    events=workspace.create_series(1,data)
    assert len(events)==3
    workspace.update_event(1,events[0]['id'],EventUpdate(end_time='2026-11-16T11:00:00+09:00'))
    workspace.update_event(1,events[1]['id'],EventScopeUpdate(start_time='2026-11-20T10:00:00+09:00',end_time='2026-11-20T11:00:00+09:00',scope='all'))
    first=workspace.get_event(1,events[0]['id'])
    assert first['startTime'].startswith('2026-11-16T10:00') and first['endTime'].startswith('2026-11-16T12:00')
    with pytest.raises(Exception):workspace.delete_event(2,events[1]['id'],'all')
    assert len(workspace.list_events(1))==3
    workspace.delete_event(1,events[1]['id'],'all')
    assert workspace.list_events(1)==[]


def test_unspecified_time_round_trips_and_is_distinct_from_all_day(client):
    event=workspace.create_event(1,EventCreate(title='시간 나중에 정하기',start_time='2026-11-16T00:00:00',end_time='2026-11-16T23:59:59',is_all_day=True,time_unspecified=True,status='passive'))
    assert workspace.get_event(1,event['id'])['timeUnspecified'] is True
    workspace.update_event(1,event['id'],EventUpdate(time_unspecified=False))
    assert workspace.get_event(1,event['id'])['timeUnspecified'] is False


def test_series_changes_preserve_per_day_deadlines_and_private_completion(client):
    project=workspace.create_project(1,'공유 검사')[0]['id']
    invitation=workspace.invite(1,project,'member@example.com')['token']
    workspace.accept(2,invitation,'member@example.com')
    events=workspace.create_series(1,EventSeriesCreate(title='주간 업무',start_time='2026-01-05T09:00:00+09:00',end_time='2026-01-05T10:00:00+09:00',task_due_at='2026-01-05T11:00:00+09:00',repeat_count=2,project_id=project))
    workspace.update_event(2,events[0]['id'],EventScopeUpdate(status='done',scope='all'))
    assert all(workspace.get_event(2,e['id'])['status']=='done' for e in events)
    dates=workspace.create_series(1,EventSeriesCreate(title='종일 업무',start_time='2026-01-05T00:00:00',end_time='2026-01-05T23:59:59',is_all_day=True,repeat_count=2))
    workspace.update_event(1,dates[0]['id'],EventScopeUpdate(task_due_at='2026-01-05T18:00:00+09:00',scope='all'))
    assert workspace.get_event(1,dates[1]['id'])['taskDueAt'].startswith('2026-01-12T18:00')
    assert all(workspace.get_event(1,e['id'])['status']=='todo' for e in events)
    workspace.update_event(1,events[0]['id'],EventScopeUpdate(title='이름 수정',task_due_at='2026-01-05T12:00:00+09:00',scope='all'))
    assert workspace.get_event(1,events[1]['id'])['taskDueAt'].startswith('2026-01-12T12:00')
    assert all(workspace.get_event(2,e['id'])['status']=='done' for e in events)


def test_widget_planning_and_recent_notes_are_owner_scoped(client):
    auth=headers(client); foreign=headers(client,2)
    catalog={'version':1,'notebooks':[{'title':'수업','sections':[{'notes':[{'id':'mine','title':'필기'},{'id':'deleted','title':'삭제','deleted':True}]}]}]}
    community_v2.save_document('notes:library:v1',community_v2.DocumentWrite(revision=0,data=catalog),1)
    for name in ('mine','deleted'):
        community_v2.save_document(f'note:{name}:v2',community_v2.DocumentWrite(revision=0,data={'pages':[]}),1)
    assert [n['id'] for n in client.get('/api/personal/calendar/widget/recent-notes',headers=auth).json()['notes']]==['mine']
    assert client.get('/api/personal/calendar/widget/recent-notes',headers=foreign).json()['notes']==[]
    assert client.get('/api/personal/calendar/widget/recent-notes').status_code==401
    result=client.get('/api/personal/calendar/widget/feed?view=planning&anchor=2026-11-16',headers=auth)
    assert result.status_code==200 and 'image' not in result.json() and 'tasks' in result.json()


def test_widget_meals_requires_token_and_returns_selected_school_data(client,monkeypatch):
    from personal_project import campuses, student_meals
    auth=headers(client)
    monkeypatch.setattr(campuses,'is_snu',lambda uid:True)
    monkeypatch.setattr(student_meals,'menus',lambda day:{'date':str(day),'restaurants':[{'title':'학생회관','lunch':'비빔밥'}]})
    assert client.get('/api/personal/calendar/widget/meals?day=2026-11-16').status_code==401
    result=client.get('/api/personal/calendar/widget/meals?day=2026-11-16',headers=auth)
    assert result.json()['restaurants'][0]['lunch']=='비빔밥' and result.json()['supported'] is True
