"""Relay boundaries and school isolation; never uses the real Mac UI."""
import os,tempfile,json,time
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'netaq.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import pytest
from personal_project import workspace_router as w,student_services as student,campuses,kakao_board_sync as relay,kakao_bridge as bridge,community_v2 as community
from personal_project.db import connection
UID=99661

def row(i,text='',**kw):return dict(index=i,text=text,mentions=['김지후'],direction='incoming',date='2026. 10. 2.',metadata='5 오후 1:00',**kw)

def test_packet_title_body_and_sender_boundary():
    rows=[row(0,'@김지후 강의 자료\n설명'),row(1,photo=True),row(2,file=True,fileName='notes.pdf'),row(3,'다른 사람',newSender=True),row(4,photo=True)]
    fp,p=list(relay.packets(rows,'김지후'))[0]
    assert p['title']=='강의 자료' and p['body']=='설명' and len(p['assets'])==2
    rows[1]['direction']='outgoing'
    assert list(relay.packets(rows,'김지후'))[0][1]['assets']==[]
    rows[0]['metadata']='1 오후 1:00'
    assert list(relay.packets(rows,'김지후'))[0][0]==fp
    assert not list(relay.packets([row(0,'@김지후님 안녕')],'김지후'))
    assert not list(relay.packets([row(0,relay.PREFIX+' @김지후 자료')],'김지후'))
    plain=row(0,'@김지후 일반 문자열');plain['mentions']=[]
    assert not list(relay.packets([plain],'김지후'))
    assert list(relay.packets([row(0,'@김지후 자료\n본문'),row(1,'평소 대화')],'김지후'))[0][1]['body']=='본문'

def setup_route(monkeypatch):
    monkeypatch.setenv('COMMUNITY_ADMINS',str(UID))
    bid=community.create_board(community.BoardCreate(name='Relay fixture'),UID)['id']
    monkeypatch.setattr(bridge,'invoke',lambda *a,**kw:{'opened':True,'rows':[row(0,'@김지후 이전 자료')]})
    return relay.configure(UID,bid,relay.ROOM,'김지후',True)[-1] | {'started_at':0}

def test_baseline_quiet_period_loop_and_idempotence(monkeypatch):
    route=setup_route(monkeypatch)
    rows=[row(0,'@김지후 이전 자료'),row(1,'@김지후 새 자료\n본문')]
    relay.observe(route,rows,now=100);relay.observe(route,rows,now=120)
    with connection() as db:assert db.execute('SELECT count(*) FROM kakao_board_origins WHERE route_id=?',(route['id'],)).fetchone()[0]==0
    relay.observe(route,rows,now=161);relay.observe(route,rows,now=200)
    with connection() as db:
        assert db.execute('SELECT count(*) FROM kakao_board_origins WHERE route_id=?',(route['id'],)).fetchone()[0]==1
        p=db.execute('SELECT * FROM community_posts WHERE board_id=?',(route['board_id'],)).fetchone();assert p['title']=='새 자료'
    relay.export_posts(route)
    with connection() as db:
        jobs=[dict(j) for j in db.execute('SELECT * FROM kakao_bridge_outbox WHERE idempotency_key LIKE ?',(f'relay:{route["id"]}:%',))]
        assert len(jobs)==1 and ':ack:' in jobs[0]['idempotency_key']
        payload=json.loads(jobs[0]['payload']);assert relay.validate_job(db,jobs[0],payload)==route['board_id']
        db.execute('UPDATE kakao_board_routes SET enabled=0 WHERE id=?',(route['id'],));db.commit()
        with pytest.raises(ValueError):relay.validate_job(db,jobs[0],payload)

def test_capture_failure_does_not_publish(monkeypatch):
    # Independent route; exact room is unique, so remove only test routes.
    with connection() as db:db.execute('DELETE FROM kakao_board_routes WHERE user_id=?',(UID,));db.commit()
    route=setup_route(monkeypatch)
    monkeypatch.setattr(bridge,'invoke',lambda *a,**kw:{'error':'download unavailable'})
    rows=[row(0,'@김지후 첨부 시험'),row(1,file=True,fileName='notes.pdf')]
    relay.observe(route,rows,now=100);relay.observe(route,rows,now=161)
    with connection() as db:
        assert not db.execute('SELECT 1 FROM community_posts WHERE board_id=?',(route['board_id'],)).fetchone()
        assert db.execute("SELECT error FROM kakao_board_messages WHERE route_id=? AND state='pending'",(route['id'],)).fetchone()[0]=='download unavailable'

def test_campus_manual_terms_and_links():
    student.save_profile(UID,student.Profile(is_student=True,school='카이스트',department='전산학부',admission_year=2026))
    assert campuses.school(UID)=='KAIST'
    assert '전산학부' in next(s['departments'] for s in campuses.schools(UID) if s['name']=='KAIST')
    meta=campuses.metadata(UID);assert not meta['supported'] and len(meta['terms'])>=24
    term=meta['terms'][0]['id'];assert campuses.courses(UID,term)==[]
    with pytest.raises(HTTPException):campuses.courses(UID,'2026_U000200001U000300001')
    assert w.course_history.__name__=='course_history'
    for url in ('javascript:alert(1)','https://user:secret@site.test','http://site.test'):
        with pytest.raises(ValueError):campuses.ServiceLink(label='bad',url=url,kind='portal')
    data=campuses.add_service(campuses.ServiceLink(label='포털',url='https://example.test',kind='portal'),UID)
    lid=data['links'][0]['id']
    with pytest.raises(HTTPException):campuses.remove_service(lid,UID+1)
    campuses.remove_service(lid,UID)
    student.save_profile(UID,student.Profile(is_student=True,school='새로운 대학교',department='새 학과'))
    assert any(s['name']=='새로운 대학교' for s in campuses.schools(UID))
