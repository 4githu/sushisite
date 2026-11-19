import sqlite3
from personal_project import clinic_scheduled_delivery as q


def setup_queue(monkeypatch, tmp_path):
    path = tmp_path / 'queue.sqlite'
    def connection():
        db = sqlite3.connect(path, timeout=5)
        db.row_factory = sqlite3.Row
        return db
    monkeypatch.setattr(q.repository, 'connection', connection)
    monkeypatch.setattr(q.repository, 'get_or_create_target_report', lambda u, t: {'id': 10, 'generatedReportJson': {'ok': True}})
    q.init()
    return connection


def test_durable_duplicate_and_ninety_minutes(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path)
    first = q.enqueue(1, 2, now=1000)
    again = q.enqueue(1, 2, now=1100)
    assert first['id'] == again['id']
    assert first['sendAfter'] == 6400
    assert q.run_once(now=6398)['state'] == 'ready'
    assert q.run_once(now=6399)['state'] == 'waiting'
    calls = []
    monkeypatch.setattr(q, '_deliver', lambda *args: calls.append(args) or {'sent': True, 'deliveryStatus': 'verified'})
    monkeypatch.setattr(q.repository, 'update_target_report', lambda *args, **kwargs: None)
    assert q.run_once(now=6400)['state'] == 'sent'
    assert len(calls) == 1
    assert q.enqueue(1, 2, now=7000)['id'] != first['id']


def test_new_requests_after_sent_keep_request_history(monkeypatch, tmp_path):
    import uuid
    setup_queue(monkeypatch, tmp_path)
    request = q.ScheduleRequest(clickedAt=100, requestId=uuid.uuid4())
    first = q.enqueue(1, 2, now=100, request=request)
    q.run_once(now=101)
    sent = []
    monkeypatch.setattr(q, '_deliver', lambda *args: sent.append(1) or {'sent': True, 'deliveryStatus': 'verified'})
    monkeypatch.setattr(q.repository, 'update_target_report', lambda *args, **kwargs: None)
    assert q.run_once(now=5500)['state'] == 'sent'
    assert q.enqueue(1, 2, now=7000, request=request)['id'] == first['id']
    new_request = q.ScheduleRequest(clickedAt=7000, requestId=uuid.uuid4())
    second = q.enqueue(1, 2, now=7000, request=new_request)
    assert second['id'] != first['id'] and second['state'] == 'queued'
    assert q.get(1, first['id'])['state'] == 'sent'
    assert sent == [1]


def test_immediate_new_request_after_sent_and_pending_completion(monkeypatch, tmp_path):
    import uuid
    setup_queue(monkeypatch, tmp_path)
    first_request = uuid.uuid4().hex
    first, _ = q.reserve_immediate(1, 2, first_request)
    q.finish_immediate(first, 'sent', 'completion_pending', {'deliveryFormat': 'text', 'sentCount': 1})
    job, result = q.reserve_immediate(1, 2, first_request)
    assert job is None and result is not None
    assert result['id'] == first and result['completionStatus'] == 'pending'
    second, result = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    assert second != first and result is None
    assert q.get(1, first)['errorCode'] == 'completion_pending'


def test_legacy_index_migrates_without_removing_sent_history(monkeypatch, tmp_path):
    db = setup_queue(monkeypatch, tmp_path)
    first, _ = q.reserve_immediate(1, 2, 'first')
    q.finish_immediate(first, 'sent')
    with db() as conn:
        conn.execute('DROP INDEX idx_clinic_delivery_dedup_v5')
        conn.execute("CREATE UNIQUE INDEX idx_clinic_delivery_dedup_v4 ON aura_clinic_delivery_queue(user_id,target_id) WHERE state NOT IN ('failed','cancelled','unknown','partial','acknowledged_unknown','acknowledged_partial')")
    second, _ = q.reserve_immediate(1, 2, 'second')
    assert second != first
    assert q.lookup_immediate(1, 2, 'first')['state'] == 'sent'
    with db() as conn:
        names = {row['name'] for row in conn.execute('PRAGMA index_list(aura_clinic_delivery_queue)')}
    assert 'idx_clinic_delivery_dedup_v4' not in names
    assert 'idx_clinic_delivery_dedup_v5' in names


def test_pending_completion_recovery_does_not_resend_or_unlock_new_send(monkeypatch, tmp_path):
    import pytest
    from fastapi import HTTPException
    setup_queue(monkeypatch, tmp_path)
    first, _ = q.reserve_immediate(1, 2, 'first')
    q.finish_immediate(first, 'sent', 'completion_pending')
    second, _ = q.reserve_immediate(1, 2, 'second')
    sent, completed = [], []
    monkeypatch.setattr(q, '_deliver', lambda *args: sent.append(args))
    monkeypatch.setattr(q.repository, 'update_target_report', lambda *args, **kwargs: completed.append(1))
    assert q.run_once(now=10**12)['state'] == 'completion_pending'
    assert q.get(1, first)['errorCode'] is None
    assert q.get(1, second)['state'] == 'sending'
    with pytest.raises(HTTPException) as exc:
        q.reserve_immediate(1, 2, 'third')
    assert exc.value.status_code == 409
    assert sent == [] and completed == [1]


def test_new_immediate_requests_after_sent_have_one_active_lock(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    setup_queue(monkeypatch, tmp_path)
    first, _ = q.reserve_immediate(1, 2, 'first')
    q.finish_immediate(first, 'sent')
    def reserve(i):
        try:
            return q.reserve_immediate(1, 2, f'new-{i}')[0]
        except HTTPException as error:
            assert error.status_code == 409
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(16)))
    assert len([job for job in results if job is not None]) == 1
    assert q.lookup_immediate(1, 2, 'first')['state'] == 'sent'


def test_generate_before_due_and_retry_busy(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path)
    generated = []
    monkeypatch.setattr(q.repository, 'get_or_create_target_report', lambda u, t: {'id': 10, 'generatedReportJson': None})
    monkeypatch.setattr(q.ai_report, 'generate', lambda *a, **k: {'results': [{'output': {'text': 'synthetic'}, 'model': 'test'}]})
    monkeypatch.setattr(q.report_generation_store, 'save_if_missing', lambda *a: generated.append(a))
    q.enqueue(1, 2, now=100)
    assert q.run_once(now=101)['state'] == 'ready'
    assert generated[0][2] == {'text': 'synthetic'}
    monkeypatch.setattr(q, '_deliver', lambda *a: (_ for _ in ()).throw(q.native_kakao.NativeKakaoError(409, 'busy', 'send_in_progress')))
    assert q.run_once(now=5500)['state'] == 'ready'
    assert q.run_once(now=5501)['state'] == 'waiting'


def test_unknown_and_restart_are_never_resent(monkeypatch, tmp_path):
    db = setup_queue(monkeypatch, tmp_path)
    one = q.enqueue(1, 2, now=100)
    assert q.run_once(now=101)['state'] == 'ready'
    monkeypatch.setattr(q, '_deliver', lambda *a: (_ for _ in ()).throw(q.native_kakao.NativeKakaoError(504, 'unknown', 'delivery_unknown')))
    assert q.run_once(now=5500)['state'] == 'unknown'
    assert q.run_once(now=7000)['state'] == 'waiting'
    assert q.get(1, one['id'])['state'] == 'unknown'
    two = q.enqueue(1, 3, now=100)
    with db() as conn:
        conn.execute("UPDATE aura_clinic_delivery_queue SET state='sending' WHERE id=?", (two['id'],))
    q.recover()
    assert q.get(1, two['id'])['state'] == 'unknown'
    assert q.run_once(now=8000)['state'] == 'waiting'


def test_http_contract_scope_and_origin(monkeypatch, tmp_path):
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.testclient import TestClient
    setup_queue(monkeypatch, tmp_path)
    def write_owner(request: Request):
        if request.headers.get('origin') != 'https://aura.chobab.app':
            raise HTTPException(403, 'origin')
        return int(request.headers['x-synthetic-owner'])
    def read_owner(request: Request):
        return int(request.headers['x-synthetic-owner'])
    app = FastAPI()
    app.include_router(q.build_router(write_owner, read_owner), prefix='/api/personal')
    client = TestClient(app)
    path = '/api/personal/aura/targets/2/kakao-clinic/scheduled-deliveries'
    headers = {'x-synthetic-owner': '1', 'origin': 'https://aura.chobab.app'}
    assert client.post(path, headers={'x-synthetic-owner': '1'}).status_code == 403
    first = client.post(path, headers=headers).json()
    assert first['state'] == 'queued' and first['sendAfter'] - first['requestedAt'] == 5400
    assert client.post(path, headers=headers).json()['id'] == first['id']
    assert client.get(path, headers={'x-synthetic-owner': '1'}).json()['id'] == first['id']
    assert client.get(path + '/' + first['id'], headers={'x-synthetic-owner': '2'}).status_code == 404
    assert client.delete(path + '/' + first['id'], headers={'x-synthetic-owner': '1'}).status_code == 403
    assert client.delete(path + '/' + first['id'], headers=headers).json()['state'] == 'cancelled'
    assert client.delete(path + '/' + first['id'], headers=headers).json()['state'] == 'cancelled'
    second = client.post(path, headers=headers).json()
    assert second['id'] != first['id'] and second['state'] == 'queued'
    with q.repository.connection() as conn:
        conn.execute("UPDATE aura_clinic_delivery_queue SET state='sending' WHERE id=?", (second['id'],))
    assert client.delete(path + '/' + second['id'], headers=headers).status_code == 409


def test_concurrent_dedup(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    setup_queue(monkeypatch, tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda _: q.enqueue(1, 2, now=100), range(24)))
    assert len({job['id'] for job in jobs}) == 1


def test_verified_completion_retry_never_resends(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path)
    job = q.enqueue(1, 2, now=100)
    q.run_once(now=101)
    sent = []
    monkeypatch.setattr(q, '_deliver', lambda *args: sent.append(1) or {'sent': True, 'deliveryStatus': 'verified'})
    completions = []
    def complete(*args, **kwargs):
        completions.append(1)
        if len(completions) == 1:
            raise RuntimeError('synthetic DB failure')
    monkeypatch.setattr(q.repository, 'update_target_report', complete)
    assert q.run_once(now=5500)['state'] == 'sent'
    assert q.get(1, job['id'])['errorCode'] == 'completion_pending'
    assert q.run_once(now=5530)['state'] == 'completion_pending'
    assert q.get(1, job['id'])['errorCode'] is None
    assert len(sent) == 1 and len(completions) == 2


def test_busy_queue_preserves_due_order(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path)
    first = q.enqueue(1, 2, now=100)
    second = q.enqueue(1, 3, now=101)
    q.run_once(now=102)
    q.run_once(now=103)
    calls = []
    def deliver(user, target):
        calls.append(target)
        if len(calls) == 1:
            raise q.native_kakao.NativeKakaoError(409, 'busy', 'send_in_progress')
        return {'sent': True, 'deliveryStatus': 'verified'}
    monkeypatch.setattr(q, '_deliver', deliver)
    monkeypatch.setattr(q.repository, 'update_target_report', lambda *a, **k: None)
    assert q.run_once(now=5501)['id'] == first['id']
    assert q.run_once(now=5510)['state'] == 'waiting'
    assert q.run_once(now=5531)['id'] == first['id']
    assert q.run_once(now=5532)['id'] == second['id']
    assert calls == [2, 2, 3]


def test_synthetic_http_real_database_report_and_native_path(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project import db, router, kakao_bridge
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 81234
    app.dependency_overrides[router.native_kakao_user_id] = lambda: 81234
    app.dependency_overrides[router.settlement_request_owner] = lambda: 81234
    client = TestClient(app, headers={'origin': 'https://aura.chobab.app'})
    school = client.post('/api/personal/aura/schools', json={'admission_year': 2026, 'school_name': '합성학교'}).json()
    rounds = client.post('/api/personal/aura/rounds/series', json={
        'school_id': school['id'], 'progress_stage': 'grade1_semester2_final', 'round_number': 1,
        'student_names': ['가상학생'], 'start_time': '2026-11-08T10:00:00+09:00',
        'end_time': '2026-11-08T11:00:00+09:00', 'repeat_count': 1, 'interval_weeks': 1,
        'allow_overlap': True}).json()
    target = rounds[0]['targets'][0]['id']
    base = f'/api/personal/aura/targets/{target}'
    monkeypatch.setattr(q.ai_report, 'generate', lambda *a, **k: {'results': [{'model': 'synthetic', 'output': {'learningContent': {'text': '합성 내용'}}}]})
    calls = []
    def fake_bridge(command, **kwargs):
        calls.append(command)
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', fake_bridge)
    path = base + '/kakao-clinic/scheduled-deliveries'
    reservation = client.post(path).json()
    assert q.run_once(now=reservation['requestedAt'] + 1)['state'] == 'ready'
    assert client.get(base + '/report').json()['generatedReportJson']['learningContent']['text'] == '합성 내용'
    assert q.run_once(now=reservation['sendAfter'] - 1)['state'] == 'waiting'
    assert calls == []
    assert q.run_once(now=reservation['sendAfter'])['state'] == 'sent'
    assert client.get(path).json()['state'] == 'sent'
    assert client.get(base + '/report').json()['status'] == 'submitted'
    assert calls == ['search', 'search', 'send', 'send']
