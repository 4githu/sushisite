import os,tempfile
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'upgrade.sqlite'))
os.environ['DISABLE_TREND_REFRESH']='1'
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace_router as r, student_services as student, snu_catalog
from personal_project.db import connection
app=FastAPI();app.include_router(r.router)
user=99101
app.dependency_overrides[r.current_user_id]=lambda:user
client=TestClient(app)
BASE='/api/personal'
TERM='2026_U000200002U000300001'

def test_calendar_reconciles_only_owned_occurrences_atomically():
    student.save_profile(user,student.Profile(is_student=True,school='서울대학교'))
    c=snu_catalog.search(TERM,'자료구조 강유')['courses'][0]
    data={'course_ids':[c['id']],'starts_on':'2026-09-07','ends_on':'2026-09-21','revision':0,'sync_calendar':True}
    with connection() as db:
        db.execute('DELETE FROM events WHERE user_id=?',(user,));db.execute('DELETE FROM student_timetable_drafts WHERE user_id=?',(user,));db.commit()
    result=client.put(BASE+'/student/timetable/draft',params={'term':TERM},json=data);assert result.status_code==200,result.text
    with connection() as db:
        ids=[r[0] for r in db.execute('SELECT id FROM events WHERE user_id=?',(user,))];assert len(ids)==5
        personal=db.execute("INSERT INTO events(user_id,title,start_time,status) VALUES(?,'자료구조','2026-09-07T09:30:00+09:00','passive')",(user,)).lastrowid;db.commit()
    assert client.put(BASE+'/student/timetable/draft',params={'term':TERM},json=data).status_code==409
    assert client.put(BASE+'/student/timetable/draft',params={'term':TERM},json={**data,'revision':1}).status_code==200
    with connection() as db:assert [r[0] for r in db.execute('SELECT event_id FROM student_timetable_events WHERE user_id=? ORDER BY event_id',(user,))]==ids
    assert client.put(BASE+'/student/timetable/draft',params={'term':TERM},json={**data,'course_ids':[],'revision':2}).status_code==200
    with connection() as db:assert [r[0] for r in db.execute('SELECT id FROM events WHERE user_id=?',(user,))]==[personal]

def test_exploration_never_changes_calendar():
    data={'course_ids':[],'manual_lessons':[{'title':'초안','weekday':1,'start':'10:00','end':'11:00'}],'starts_on':'2026-09-01','ends_on':'2026-09-14','revision':0,'sync_calendar':True}
    result=client.put(BASE+'/student/timetable/draft',params={'term':TERM,'slot':'explore-test'},json=data)
    assert result.status_code==200 and not result.json()['calendarSynced']

def test_note_revision_conflict_preserves_content():
    day='/calendar/daily-notes/2040-01-01';result=client.put(BASE+day,json={'content':'최초','revision':0});assert result.status_code==200
    assert client.put(BASE+day,json={'content':'덮어쓰기','revision':0}).status_code==409
    assert client.get(BASE+day).json()['content']=='최초'

def test_board_threads_acl_and_resource_protection(monkeypatch):
    global user
    monkeypatch.setenv('COMMUNITY_ADMINS',str(user))
    b=client.post(BASE+'/boards',json={'name':'테스트 자료방'}).json()['id']
    f=client.post(BASE+'/resources',params={'name':'example.txt','board_id':b},content=b'private',headers={'content-type':'text/plain'}).json()
    p=client.post(BASE+f'/boards/{b}/posts',json={'title':'자료','document':{'blocks':[{'children':[{'text':'내용'}]}]}}).json()['id']
    c=client.post(BASE+f'/boards/posts/{p}/comments',json={'content':'첫 댓글'});assert c.status_code==200,c.text
    cid=c.json()['comments'][0]['id'];assert client.post(BASE+f'/boards/posts/{p}/comments',json={'content':'답글','parent_id':cid}).status_code==200
    client.put(BASE+'/boards/permissions',json={'user_id':99102,'scope':f'board:{b}','action':'read','allowed':False})
    original=user;user=99102
    assert client.get(BASE+f'/boards/posts/{p}').status_code==403
    assert client.get(f['url']).status_code==403
    user=original
    assert client.patch(BASE+f'/boards/posts/{p}',json={'deleted':True}).status_code==200
    assert client.get(BASE+f'/boards/posts/{p}').status_code==404
    assert client.patch(BASE+f'/boards/posts/{p}',json={'deleted':False}).status_code==200
    assert client.get(BASE+f'/boards/posts/{p}').status_code==200

def test_document_conflict_private_history_and_public_rule_versions():
    global user
    result=client.put(BASE+'/documents/private-test',json={'data':{'text':'mine'},'revision':0});assert result.status_code==200
    assert client.put(BASE+'/documents/private-test',json={'data':{'text':'stale'},'revision':0}).status_code==409
    original=user;user=99103;assert client.get(BASE+'/documents/private-test').json()['data'] is None;user=original
    v=client.get(BASE+'/student/rules/cse_2026/versions').json();data=v['official'];data['tracks'][0]['major_min_credits']=62
    result=client.put(BASE+'/student/rules/cse_2026/versions',json={'data':data,'revision':v['revision']});assert result.status_code==200,result.text
    assert snu_catalog.curriculum('cse_2026')['tracks'][0]['major_min_credits']==63

def test_trend_scalar_and_change_points():
    from personal_project.course_trends import read
    d=read(TERM,'M1522.000900','001');assert d['points'];assert 'live' in d['windows'];assert all(isinstance(p['time'],int) for p in d['points'])

def test_migration_preserves_distinct_legacy_drafts():
    uid=99200
    with connection() as db:
        for slot,ids in [('1-1',[1]),('2-1',[2]),('3-1',[2])]:
            db.execute('INSERT INTO student_timetable_drafts VALUES(?,?,?,?)',(uid,TERM+'::'+slot,__import__('json').dumps({'course_ids':ids,'manual_lessons':[]}),1))
        db.commit()
    student.migrate_legacy_drafts();student.migrate_legacy_drafts()
    with connection() as db:
        rows=db.execute('SELECT term FROM student_timetable_drafts WHERE user_id=?',(uid,)).fetchall()
        assert len(rows)==2 and all('explore-legacy-' in r[0] for r in rows)
        assert db.execute('SELECT count(*) FROM student_draft_migration_backup WHERE user_id=?',(uid,)).fetchone()[0]==3

def test_general_rule_keeps_machine_keys_and_cleans_collection_errors():
    rule=snu_catalog.curriculum('cse_2026');assert rule['general_key']=='eng_cse_2025'
    data=client.get(BASE+'/student/general/eng_cse_2025').json()
    assert any('math' in bucket['areas'] for bucket in data['buckets'])
    from personal_project.curriculum_display import text
    assert 'frameset' not in text('철학과 frameset/JS 게이트(euc-kr) SPA-blocked hum.md 미확보')

def test_transcript_uses_finished_canonical_semesters_not_manual_checks_or_exploration():
    uid=99188
    c=snu_catalog.search(TERM,'자료구조 강유')['courses'][0]
    with connection() as db:db.execute('DELETE FROM student_timetable_drafts WHERE user_id=?',(uid,));db.commit()
    past=student.TimetableDraft(course_ids=[c['id']],starts_on='2020-03-01',ends_on='2020-06-30')
    student.save_draft(uid,TERM,past)
    student.save_draft(uid,TERM,past,'explore-test')
    history=student.course_history(uid)
    assert len(history['semesters'])==1
    assert len(history['completed'])==1 and not history['planned']
    assert student.course_progress(uid)['completed']==[c['sbjt_cd']]
    future=student.TimetableDraft(course_ids=[c['id']],starts_on='2090-03-01',ends_on='2090-06-30',revision=1)
    student.save_draft(uid,TERM,future)
    assert student.course_progress(uid)['completed']==[]
    assert student.course_progress(uid)['planned']==[c['sbjt_cd']]

def test_transcript_exclusion_is_private_and_can_be_reversed():
    global user
    previous=user;user=99189
    try:
        c=snu_catalog.search(TERM,'자료구조 강유')['courses'][0]
        student.save_draft(user,TERM,student.TimetableDraft(course_ids=[c['id']],starts_on='2020-03-01',ends_on='2020-06-30'))
        endpoint=BASE+'/student/transcript/exclusions/'+c['sbjt_cd']
        assert client.put(endpoint,json={'excluded':True},headers={'Origin':'https://evil.example'}).status_code==403
        response=client.put(endpoint,json={'excluded':True});assert response.status_code==200,response.text
        assert response.json()['completed']==[]
        assert c['sbjt_cd'] in client.get(BASE+'/student/course-history').json()['excluded']
        assert c['sbjt_cd'] in client.put(endpoint,json={'excluded':False}).json()['completed']
        assert student.course_history(999999)['excluded']==[]
    finally:user=previous
