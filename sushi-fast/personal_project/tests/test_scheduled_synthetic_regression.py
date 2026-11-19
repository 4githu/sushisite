"""Isolated HTTP/SQLite scheduled delivery regressions. No real provider or Kakao.

Run from sushi-fast: python -m pytest -q personal_project/tests/test_scheduled_synthetic_regression.py
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_project import clinic_scheduled_delivery as queue, db, kakao_bridge, router


@pytest.fixture
def scenario(tmp_path, monkeypatch):
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
        'end_time': '2026-11-08T11:00:00+09:00', 'repeat_count': 1,
        'interval_weeks': 1, 'allow_overlap': True}).json()
    target = rounds[0]['targets'][0]['id']
    base = f'/api/personal/aura/targets/{target}'
    calls = []
    def bridge(command, **kwargs):
        calls.append(command)
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', bridge)
    monkeypatch.setattr(queue.ai_report, 'generate', lambda *a, **k: {
        'results': [{'model': 'synthetic', 'output': {'learningContent': {'text': '합성 학습 내용'}}}]})
    yield client, target, base, calls
    client.close()


def test_real_pdf_and_scheduled_generation(scenario):
    client, target, base, calls = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    assert job['sendAfter'] - job['requestedAt'] == 5400
    assert queue.run_once(now=job['requestedAt'] + 5)['state'] == 'ready'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    pdf = router._target_report_pdf(81234, target)
    with fitz.open(stream=pdf, filetype='pdf') as document:
        text = ''.join(page.get_text() for page in document)
    assert '1학년 2학기 기말고사' in text
    assert 'grade1_semester2_final' not in text and 'grade1_semestar2_final' not in text
    assert '합성 학습 내용' in text
    assert queue.run_once(now=job['sendAfter'] - 0.01)['state'] == 'waiting'
    assert calls == []
    assert queue.run_once(now=job['sendAfter'])['state'] == 'sent'
    assert client.get(path).json()['state'] == 'sent'
    assert client.get(base + '/report').json()['status'] == 'submitted'
    assert calls == ['search', 'search', 'send', 'send']


def test_atomic_duplicate_http_and_cancel(scenario):
    client, _, base, calls = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: client.post(path), range(16)))
    assert all(r.status_code == 200 for r in results)
    ids = {r.json()['id'] for r in results}
    assert len(ids) == 1
    job_id = ids.pop()
    assert client.get(path + '/' + job_id).json()['state'] == 'queued'
    assert client.delete(path + '/' + job_id).json()['state'] == 'cancelled'
    assert client.get(path).json()['state'] == 'cancelled'
    assert client.post(path).json()['id'] != job_id
    assert not calls


@pytest.mark.parametrize('result', ['unknown', 'partial', 'exception'])
def test_uncertain_outcomes_never_submit_or_auto_resend(scenario, monkeypatch, result):
    client, _, base, calls = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    assert queue.run_once(now=job['requestedAt'] + 1)['state'] == 'ready'
    attempts = []
    def fake_delivery(*args):
        attempts.append(1)
        if result == 'exception':
            raise RuntimeError('synthetic failure')
        return {'sent': True, 'deliveryStatus': result}
    monkeypatch.setattr(queue, '_deliver', fake_delivery)
    assert queue.run_once(now=job['sendAfter'])['state'] == 'unknown'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    queue.recover()
    assert queue.run_once(now=job['sendAfter'] + 600)['state'] == 'waiting'
    assert client.get(path).json()['state'] == 'unknown'
    assert len(attempts) == 1 and not calls


def test_note_bridge_exception_after_image_is_partial_without_replay(scenario, monkeypatch):
    client, _, base, _ = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    assert queue.run_once(now=job['requestedAt'] + 1)['state'] == 'ready'
    sends = []
    def bridge(command, **kwargs):
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        sends.append(bool(kwargs['files']))
        if kwargs['files']:
            return {'sent': True}
        raise RuntimeError('synthetic malformed bridge response')
    monkeypatch.setattr(kakao_bridge, 'invoke', bridge)
    assert queue.run_once(now=job['sendAfter'])['state'] == 'partial'
    assert client.get(path).json()['errorCode'] == 'partial_delivery'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    queue.recover()
    assert queue.run_once(now=job['sendAfter'] + 600)['state'] == 'waiting'
    assert sends == [True, False]


def test_restart_during_generation_and_send(scenario):
    client, _, base, calls = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    with queue.repository.connection() as conn:
        conn.execute("UPDATE aura_clinic_delivery_queue SET state='generating' WHERE id=?", (job['id'],))
        conn.commit()
    queue.recover()
    assert client.get(path).json()['state'] == 'queued'
    assert queue.run_once(now=job['requestedAt'] + 1)['state'] == 'ready'
    with queue.repository.connection() as conn:
        conn.execute("UPDATE aura_clinic_delivery_queue SET state='sending' WHERE id=?", (job['id'],))
        conn.commit()
    queue.recover()
    assert client.get(path).json()['state'] == 'unknown'
    assert queue.run_once(now=job['sendAfter'] + 1)['state'] == 'waiting'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    assert calls == []


def test_definite_send_failure_is_not_automatically_retried(scenario, monkeypatch):
    client, _, base, calls = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    assert queue.run_once(now=job['requestedAt'] + 1)['state'] == 'ready'
    attempts = []
    def fail(*args):
        attempts.append(1)
        raise queue.native_kakao.NativeKakaoError(409, 'synthetic', 'recipient_unverified')
    monkeypatch.setattr(queue, '_deliver', fail)
    assert queue.run_once(now=job['sendAfter'])['state'] == 'failed'
    queue.recover()
    assert queue.run_once(now=job['sendAfter'] + 3600)['state'] == 'waiting'
    assert client.get(path).json()['state'] == 'failed'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    assert len(attempts) == 1 and not calls


def test_report_is_not_completed_while_send_in_progress(scenario, monkeypatch):
    client, _, base, _ = scenario
    path = base + '/kakao-clinic/scheduled-deliveries'
    job = client.post(path).json()
    assert queue.run_once(now=job['requestedAt'] + 1)['state'] == 'ready'
    entered, release = Event(), Event()
    def fake_delivery(*args):
        entered.set()
        assert release.wait(10)
        return {'sent': True, 'deliveryStatus': 'verified'}
    monkeypatch.setattr(queue, '_deliver', fake_delivery)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(queue.run_once, job['sendAfter'])
        try:
            assert entered.wait(10)
            assert client.get(path).json()['state'] == 'sending'
            assert client.get(base + '/report').json()['status'] != 'submitted'
            assert client.delete(path + '/' + job['id']).status_code == 409
        finally:
            release.set()
        assert future.result(timeout=10)['state'] == 'sent'
    assert client.get(base + '/report').json()['status'] == 'submitted'
