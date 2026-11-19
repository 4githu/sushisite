"""No desktop UI or outbound messages: exercise the queue and privacy boundary."""
import os,tempfile,json,uuid
import pytest
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'bridge.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace_router,kakao_bridge as bridge
from personal_project.router import native_kakao_user_id,current_user_id
from personal_project.db import connection

def test_mentions_only_attach_the_immediate_photo_from_same_sender():
    rows=[{'text':'@김지후 과제입니다','metadata':'3 오전 10:00','index':0}, {'text':'','photo':True,'newSender':False,'index':1}]
    matches=list(bridge.mentions(rows,'김지후'));assert len(matches)==1 and matches[0][2]['index']==1
    rows[1]['newSender']=True;assert list(bridge.mentions(rows,'김지후'))[0][2] is None
    rows.insert(1,{'text':'다른 글','index':1});assert list(bridge.mentions(rows,'김지후'))[0][2] is None
    assert not bridge.mention_matches('@김지후님 안녕하세요','김지후')
    assert bridge.mention_matches('자료 @김지후 확인','김지후')
    rows[0]['metadata']='1 오전 10:00';assert list(bridge.mentions(rows,'김지후'))[0][0]==matches[0][0]

def test_outbox_idempotency_unknown_delivery_never_replayed(monkeypatch):
    app=FastAPI();app.include_router(workspace_router.router)
    app.dependency_overrides[native_kakao_user_id]=lambda:98221
    app.dependency_overrides[current_user_id]=lambda:98221
    client=TestClient(app);headers={'origin':'https://chobab.app'}
    payload={'room':'2026 파인애플 (졸업생)','text':'unit fixture only','idempotency_key':'unit-fixture-one'}
    url='/api/personal/kakao-bridge/send'
    a=client.post(url,json=payload,headers=headers);assert a.status_code==200,a.text
    assert client.post(url,json=payload,headers=headers).json()['id']==a.json()['id']
    assert client.post(url,json={**payload,'text':'different'},headers=headers).status_code==409
    assert client.post(url,json=payload,headers={'origin':'https://example.com'}).status_code==403
    monkeypatch.setattr(bridge,'invoke',lambda *a,**kw:{'error':'lost acknowledgement','uncertain':True})
    with connection() as db:job=db.execute('SELECT * FROM kakao_bridge_outbox WHERE id=?',(a.json()['id'],)).fetchone()
    bridge.process_job(job)
    with connection() as db:assert db.execute('SELECT state FROM kakao_bridge_outbox WHERE id=?',(job['id'],)).fetchone()[0]=='unknown'
    monkeypatch.setattr(bridge,'invoke',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Must not replay')))
    bridge.process_job(job)

@pytest.mark.parametrize('search_result', [
    {'found':False,'room':'synthetic absent room','searchEvidence':'confirmed_absent'},
    {'opened':True,'room':'another room','searchEvidence':'unique_exact'},
    {'opened':True,'room':'synthetic absent room','searchEvidence':'unverified'},
    {'room':'synthetic absent room','searchEvidence':'unique_exact'},
])
def test_outbox_never_sends_when_recipient_not_verified(monkeypatch, search_result):
    app=FastAPI();app.include_router(workspace_router.router)
    app.dependency_overrides[native_kakao_user_id]=lambda:98221
    app.dependency_overrides[current_user_id]=lambda:98221
    client=TestClient(app)
    payload={'room':'synthetic absent room','text':'synthetic','idempotency_key':'absent-'+uuid.uuid4().hex}
    response=client.post('/api/personal/kakao-bridge/send',json=payload,headers={'origin':'https://chobab.app'})
    assert response.status_code==200
    calls=[]
    def invoke(command,**kwargs):
        calls.append(command)
        if command=='search':
            return search_result
        return {'sent':True}
    monkeypatch.setattr(bridge,'invoke',invoke)
    with connection() as db:job=db.execute('SELECT * FROM kakao_bridge_outbox WHERE id=?',(response.json()['id'],)).fetchone()
    bridge.process_job(job)
    with connection() as db:state=db.execute('SELECT state FROM kakao_bridge_outbox WHERE id=?',(job['id'],)).fetchone()[0]
    assert calls==['search']
    assert state=='failed'


def test_owner_auth_cannot_be_bypassed(monkeypatch):
    from personal_project.router import JMT
    monkeypatch.setattr(JMT,"check_jwt",lambda *a,**kw:{"data":{"id":98222,"email":"other@example.com"}})
    app=FastAPI();app.include_router(bridge.router);client=TestClient(app)
    assert client.get('/kakao-bridge').status_code in (401,403)


def test_redacted_bridge_log_preserves_safe_error_code_and_correlation(monkeypatch, tmp_path, caplog):
    from types import SimpleNamespace
    binary=tmp_path/'bridge';binary.write_text('fixture')
    monkeypatch.setattr(bridge,'BINARY',binary)
    payload={'error':'private student details','errorCode':'ax_action_failed','uncertain':True}
    monkeypatch.setattr(bridge.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(payload)))
    result=bridge.invoke('send',redact_errors=True,operation_id='synthetic-job-1',room='private room name',text='private report')
    assert result==payload
    assert 'error_code=ax_action_failed' in caplog.text
    assert 'operation=synthetic-job-1' in caplog.text
    assert 'at_utc=' in caplog.text
    assert 'private student' not in caplog.text
    assert 'private room' not in caplog.text
    assert 'private report' not in caplog.text


def test_search_error_logs_only_stage_and_fixed_menu_flags(monkeypatch, tmp_path, caplog):
    from types import SimpleNamespace
    binary=tmp_path/'bridge';binary.write_text('fixture')
    monkeypatch.setattr(bridge,'BINARY',binary)
    payload={
        'error':'private search query detail',
        'errorCode':'search_paste_menu_unavailable',
        'uncertain':False,
        'diagnostics':{
            'stage':'paste-menu',
            'menuActions':{
                'select-all':{'menuFound':True,'actionSucceeded':True,'title':'private menu label'},
                'paste':{'menuFound':True,'menuOpened':True,'actionItemFound':False,'actionItemEnabled':False,'actionAttempted':False,'actionSucceeded':False,'value':'private text'},
            },
            'searchText':'private query',
        },
    }
    monkeypatch.setattr(bridge.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(payload)))
    result=bridge.invoke('search',redact_errors=True,operation_id='synthetic-search-1',room='private room',query='private query')
    assert result==payload
    assert 'error_code=search_paste_menu_unavailable' in caplog.text
    assert 'stage":"paste-menu' in caplog.text
    assert '"actionItemFound":false' in caplog.text
    assert 'private' not in caplog.text
    assert 'title' not in caplog.text
    assert 'searchText' not in caplog.text


def test_search_diagnostics_keep_bounded_counters_without_labels():
    from personal_project.kakao_bridge import _safe_search_diagnostics
    result = _safe_search_diagnostics({'diagnostics': {'stage': 'settling', 'samples': 48, 'exactRows': 0, 'stableSamples': 0, 'budgetExceeded': False, 'room': 'private-room', 'query': 'private-query'}})
    assert result == {'stage': 'settling', 'samples': 48, 'exactRows': 0, 'stableSamples': 0, 'budgetExceeded': False}
    assert _safe_search_diagnostics({'diagnostics': {'samples': True, 'exactRows': -1, 'stableSamples': 10001}}) is None
