"""User contract: schedule edits determine price; overlap is allowed; scopes agree."""
import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db
from personal_project.router import router,current_user_id

OWNER=81234
@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'schedule.sqlite');db.init_db()
    app=FastAPI();app.include_router(router);app.dependency_overrides[current_user_id]=lambda:OWNER
    client=TestClient(app)
    school=client.post('/api/personal/aura/schools',json={'admission_year':2026,'school_name':'합성'}).json()
    return client,school['id'],app

def series(api):
    client,sid,_=api
    result=client.post('/api/personal/aura/rounds/series',json={'school_id':sid,'progress_stage':'grade1_semester1_midterm','round_number':1,'student_names':['합성학생'], 'start_time':'2026-11-08T10:00:00+09:00','end_time':'2026-11-08T11:00:00+09:00','repeat_count':3,'interval_weeks':1,'allow_overlap':True})
    assert result.status_code==201,result.text
    return result.json()

@pytest.mark.parametrize('scope,expected', [('this',[1]),('following',[1,2]),('all',[0,1,2])])
def test_scope_edit_and_delete_are_consistent_and_keep_series_identity(api,scope,expected):
    client,_,app=api;rows=series(api);url=f"/api/personal/aura/rounds/{rows[1]['id']}"
    response=client.patch(url,json={'scope':scope,'start_time':'2026-11-15T10:30:00+09:00','end_time':'2026-11-15T12:30:00+09:00', 'modality':'remote',**({} if scope=='this' else {'expected_round_ids':[rows[i]['id'] for i in expected],'expected_round_state':client.get(url+f'/modality-preview?scope={scope}').json()['roundState']})})
    assert response.status_code==200,response.text
    assert response.json()['affectedRoundIds']==[rows[i]['id'] for i in expected]
    for i,r in enumerate(rows):
        saved=client.get(f"/api/personal/aura/rounds/{r['id']}").json()
        assert saved['seriesGroupId']==r['seriesGroupId']
        assert saved['amount']==r['amount']  # Calculated only on explicit request.
    app.dependency_overrides[current_user_id]=lambda:OWNER+1
    assert client.delete(url+f'?scope={scope}').status_code==404
    app.dependency_overrides[current_user_id]=lambda:OWNER
    assert client.delete(url+f'?scope={scope}').status_code==204
    remaining=client.get('/api/personal/aura/rounds').json()
    assert {r['id'] for r in remaining}=={r['id'] for i,r in enumerate(rows) if i not in expected}


def test_overlapping_paid_snapshot_schedule_can_change_duration_without_price_approval(api):
    client,sid,_=api;rows=series(api);rid=rows[0]['id'];url=f'/api/personal/aura/rounds/{rid}'
    with db.connection() as c:
        c.execute("UPDATE aura_clinic_rounds SET payment_status='paid' WHERE id=?",(rid,))
        c.execute("INSERT INTO aura_settlement_snapshots(user_id,year,month,data_json,pricing_version) VALUES(?,?,?,?,6)",(OWNER,2026,11,'{"items":[],"totalAmount":30000}'))
        c.execute("INSERT INTO events(user_id,title,type,start_time,end_time) VALUES(?,?,'aura',?,?)",(OWNER,'겹침 허용','2026-11-08T10:00:00+09:00','2026-11-08T13:00:00+09:00'));c.commit()
    result=client.patch(url,json={'start_time':'2026-11-08T10:30:00+09:00','end_time':'2026-11-08T12:30:00+09:00'})
    assert result.status_code==200,result.text
    saved=client.get(url).json();assert saved['amount']==rows[0]['amount'] and saved['paymentStatus']=='paid'
    assert saved['seriesGroupId']==rows[0]['seriesGroupId']
    with db.connection() as c:
        assert c.execute('SELECT data_json FROM aura_settlement_snapshots WHERE user_id=?',(OWNER,)).fetchone()[0]=='{"items":[],"totalAmount":30000}'


def test_series_translation_preserves_existing_different_durations(api):
    client,_,_=api;rows=series(api)
    with db.connection() as c:
        c.execute('UPDATE events SET end_time=? WHERE id=?',('2026-11-22T12:00:00+09:00',rows[2]['eventId']));c.commit()
    url=f"/api/personal/aura/rounds/{rows[1]['id']}"
    preview=client.get(url+'/modality-preview?scope=following').json()
    result=client.patch(url,json={'scope':'following','modality':'remote','start_time':'2026-11-15T10:30:00+09:00','end_time':'2026-11-15T11:30:00+09:00','expected_round_ids':[r['id'] for r in preview['rounds']],'expected_round_state':preview['roundState']})
    assert result.status_code==200,result.text
    last=client.get(f"/api/personal/aura/rounds/{rows[2]['id']}").json()
    assert (datetime.fromisoformat(last['endTime'])-datetime.fromisoformat(last['startTime'])).total_seconds()==7200
