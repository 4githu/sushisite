"""User-requested recovery contract; fixed fixtures, no real Kakao or production DB."""
import importlib.util
from pathlib import Path
from personal_project import kakao_bridge as bridge

def test_receipt_diagnostics_are_logged_without_private_data(monkeypatch,tmp_path,caplog):
    import json
    from types import SimpleNamespace
    binary=tmp_path/'bridge';binary.write_text('synthetic')
    monkeypatch.setattr(bridge,'BINARY',binary)
    monkeypatch.setattr(bridge,'_notify_failure',lambda *a,**k:None)
    payload={'error':'private','errorCode':'delivery_not_observed','uncertain':True,'diagnostics':{'stage':'image-receipt','newRows':1,'newUnknown':1,'newHasImage':1,'newHasClock':0,'samples':2,'budgetExceeded':False,'text':'PRIVATE_TEXT'}}
    monkeypatch.setattr(bridge.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(payload)))
    bridge.invoke('send',room='synthetic',files=['file'],redact_errors=True)
    assert '"newUnknown":1' in caplog.text and '"newHasClock":0' in caplog.text
    assert 'PRIVATE_TEXT' not in caplog.text and 'private' not in caplog.text


def test_failure_notice_is_plain_text_to_self_and_rate_limited(monkeypatch):
    calls=[]
    def invoke(command,**args):
        calls.append((command,args))
        return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'} if command=='search' else {'sent':True}
    monkeypatch.setattr(bridge,'invoke',invoke);bridge._notice_last.clear()
    failure={'errorCode':'delivery_not_observed','uncertain':True}
    bridge._notify_failure('send',failure,'synthetic-operation')
    bridge._notify_failure('send',failure,'synthetic-operation')
    assert [c[0] for c in calls]==['search','send']
    sent=calls[1][1]
    assert sent['room']=='본계정' and sent['files']==[] and sent['_notice'] is True
    assert '불명확' in sent['text'] and '재전송하지 않았습니다' in sent['text']


def test_classroom_notice_identifies_target_action_and_observed_reason(monkeypatch):
    from personal_project.aura_classroom_outbox import PRIMARY_ROOM
    calls=[]
    def invoke(command, **args):
        calls.append((command,args))
        return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'} if command=='search' else {'sent':True}
    monkeypatch.setattr(bridge,'invoke',invoke);bridge._notice_last.clear()
    bridge._notify_failure('send',{'errorCode':'delivery_not_observed','uncertain':True},'classroom_request')
    text=calls[1][1]['text']
    assert PRIMARY_ROOM in text
    assert '강의실 배정 요청' in text
    assert '전송 버튼' in text and '확인하지 못' in text
    assert '불명확' in text and '재전송하지 않았습니다' in text


def test_classroom_bridge_error_routes_notice_without_original_resend(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from personal_project.aura_classroom_outbox import PRIMARY_ROOM
    binary=tmp_path/'bridge'; binary.write_text('synthetic')
    monkeypatch.setattr(bridge,'BINARY',binary); bridge._notice_last.clear()
    requests=[]
    def run(*args, **kwargs):
        request=json.loads(kwargs['input']); requests.append(request)
        if len(requests)==1:
            payload={'error':'private synthetic details','errorCode':'delivery_not_observed','uncertain':True}
        elif request['command']=='search':
            payload={'opened':True,'room':'본계정','searchEvidence':'unique_exact'}
        else:
            payload={'sent':True}
        return SimpleNamespace(stdout=json.dumps(payload))
    monkeypatch.setattr(bridge.subprocess,'run',run)
    result=bridge.invoke('send',room=PRIMARY_ROOM,text='synthetic private body',files=[],operation_id='classroom_request',redact_errors=True)
    assert result['uncertain'] is True
    assert [r['command'] for r in requests]==['send','search','send']
    notice=requests[-1]
    assert notice['room']=='본계정' and PRIMARY_ROOM in notice['text']
    assert '강의실 배정 요청' in notice['text'] and 'delivery_not_observed' not in notice['text']
    assert 'synthetic private' not in notice['text']


def test_distinct_report_errors_identify_target_and_stage(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    binary=tmp_path/'bridge'; binary.write_text('synthetic')
    monkeypatch.setattr(bridge,'BINARY',binary); bridge._notice_last.clear()
    requests=[]
    def run(*args, **kwargs):
        request=json.loads(kwargs['input']); requests.append(request)
        if request.get('room') == '테스트 학생방':
            payload={'error':'private detail','errorCode':'delivery_not_observed','uncertain':True}
        elif request['command']=='search':
            payload={'opened':True,'room':'본계정','searchEvidence':'unique_exact'}
        else: payload={'sent':True}
        return SimpleNamespace(stdout=json.dumps(payload))
    monkeypatch.setattr(bridge.subprocess,'run',run)
    for op in ('one', 'two'):
        bridge.invoke('send',room='테스트 학생방',files=['image.png'],operation_id=op,redact_errors=True)
    notices=[r for r in requests if r.get('room')=='본계정' and r['command']=='send']
    assert len(notices)==2
    for notice in notices:
        assert '테스트 학생방' in notice['text'] and '이미지' in notice['text']
        assert '불명확' in notice['text'] and 'private detail' not in notice['text']


def test_notice_does_not_send_when_self_chat_is_ambiguous(monkeypatch):
    calls=[]
    def invoke(command,**args):
        calls.append(command);return {'error':'duplicate room','searchEvidence':'ambiguous'}
    monkeypatch.setattr(bridge,'invoke',invoke);bridge._notice_last.clear()
    bridge._notify_failure('search',{'errorCode':'search_unsettled'},'synthetic-operation')
    assert calls==['search']


def test_background_read_failure_and_ui_busy_do_not_generate_notices(monkeypatch):
    monkeypatch.setattr(bridge,'invoke',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No send')))
    bridge._notify_failure('read-latest',{'errorCode':'ax_read_budget_exceeded'},'synthetic')
    bridge._notify_failure('search',{'errorCode':'ui_busy'},'synthetic')


def test_renamed_self_room_uses_product_path_and_cleanup(tmp_path):
    path=Path(__file__).resolve().parents[3]/'ops/kakao_live_check.py'
    spec=importlib.util.spec_from_file_location('recovery_live_check',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'sushi-fast/.runtime').mkdir(parents=True)
    calls=[]
    def invoke(command,**args):
        calls.append(command)
        if command=='status':return {'trusted':True,'running':True,'locked':False}
        if command=='search':return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'}
        return {'sent':True,'cleanup':{'searchCleared':True,'roomClosed':True}}
    result=module.check('본계정','text','recovery-synthetic',root=tmp_path,invoke=invoke)
    assert result['state']=='succeeded' and result['cleanup_verified'] is True
    assert calls==['status','search','send']
    assert '김지후' not in module.ROOMS


def test_background_scan_skips_cross_process_ui_busy(monkeypatch):
    monkeypatch.setattr(bridge,'invoke',lambda *a,**k:{'error':'another UI operation','errorCode':'ui_busy'})
    monkeypatch.setattr(bridge,'connection',lambda:(_ for _ in ()).throw(AssertionError('Skipped scan must not update DB')))
    assert bridge.scan(0,'synthetic room','synthetic mention') is False
    assert not bridge.native_kakao._send_lock.locked()


def test_board_busy_does_not_record_failure_or_success(monkeypatch):
    from contextlib import contextmanager
    from personal_project import kakao_board_sync as sync
    sql=[]
    class DB:
        def execute(self,query,args=()):
            sql.append(query)
            return [{'id':1,'user_id':0,'room':'synthetic room'}] if query.startswith('SELECT * FROM kakao_board_routes') else []
        def commit(self):pass
    @contextmanager
    def connection():yield DB()
    monkeypatch.setattr(sync,'connection',connection)
    monkeypatch.setattr(sync.community,'admin',lambda uid:True)
    monkeypatch.setattr(sync,'export_posts',lambda route:None)
    monkeypatch.setattr(bridge,'invoke',lambda *a,**k:{'error':'another UI operation','errorCode':'ui_busy'})
    sync.tick()
    assert len(sql)==2 and 'last_attempt' in sql[1]
    assert not bridge.native_kakao._send_lock.locked()
