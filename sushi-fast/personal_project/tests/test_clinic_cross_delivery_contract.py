"""Synthetic HTTP tests; no native Kakao process or production database."""
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from personal_project import router
from personal_project.tests.test_scheduled_synthetic_regression import scenario


@pytest.mark.parametrize('prepared', [False, True])
def test_waiting_reservation_is_cancelled_atomically_by_immediate(scenario, monkeypatch, prepared):
    from personal_project import clinic_scheduled_delivery as schedule
    client, _, base, calls = scenario
    reservation = client.post(base + '/kakao-clinic/scheduled-deliveries').json()
    if prepared:
        assert schedule.run_once(now=reservation['requestedAt'] + 1)['state'] == 'ready'
    def deliver(*_):
        calls.append('synthetic-send')
        return {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'images', 'sentCount': 1}
    monkeypatch.setattr(router, '_send_immediate_clinic_report', deliver)
    response = client.post(base + '/kakao-clinic/send-report', headers={'X-Delivery-Request-Id': str(uuid.uuid4())})
    assert response.status_code == 200
    assert client.get(base + '/kakao-clinic/scheduled-deliveries/' + reservation['id']).json()['state'] == 'cancelled'
    assert schedule.run_once(now=reservation['sendAfter'] + 100)['state'] == 'waiting'
    assert calls == ['synthetic-send']


def test_due_scheduler_send_blocks_simultaneous_immediate(scenario, monkeypatch):
    from personal_project import clinic_scheduled_delivery as schedule
    client, _, base, calls = scenario
    reservation = client.post(base + '/kakao-clinic/scheduled-deliveries').json()
    assert schedule.run_once(now=reservation['requestedAt'] + 1)['state'] == 'ready'
    entered, release = Event(), Event()
    def scheduled(*_):
        calls.append('scheduled-send')
        entered.set()
        assert release.wait(5)
        return {'sent': True, 'deliveryStatus': 'verified'}
    monkeypatch.setattr(schedule, '_deliver', scheduled)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(schedule.run_once, reservation['sendAfter'])
        assert entered.wait(5)
        response = client.post(base + '/kakao-clinic/send-report', headers={'X-Delivery-Request-Id': str(uuid.uuid4())})
        assert response.status_code == 409
        release.set()
        assert pending.result()['state'] == 'sent'
    assert calls == ['scheduled-send']


def test_immediate_idempotency_and_scheduled_cross_race(scenario, monkeypatch):
    client, target, base, calls = scenario
    entered, release = Event(), Event()
    def fake_delivery(*args):
        calls.append('synthetic-send')
        entered.set()
        assert release.wait(5)
        return {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'image', 'sentCount': 1, 'destination': '합성 전송 대상'}
    monkeypatch.setattr(router, '_send_immediate_clinic_report', fake_delivery)
    request_id = str(uuid.uuid4())
    headers = {'X-Delivery-Request-Id': request_id}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.post, base + '/kakao-clinic/send-report', headers=headers)
        assert entered.wait(5)
        reserved = client.post(base + '/kakao-clinic/scheduled-deliveries')
        assert reserved.status_code == 409
        duplicate = client.post(base + '/kakao-clinic/send-report', headers=headers)
        assert duplicate.status_code == 409
        release.set()
        assert pending.result().status_code == 200
    lookup = client.get(base + '/kakao-clinic/delivery-requests/' + request_id)
    assert lookup.status_code == 200 and lookup.json()['state'] == 'sent'
    replay = client.post(base + '/kakao-clinic/send-report', headers=headers)
    assert replay.status_code == 200 and replay.json()['deliveryStatus'] == 'verified'
    assert calls == ['synthetic-send']


def test_lost_response_same_request_is_idempotent_new_request_can_proceed(scenario, monkeypatch):
    client, _, base, calls = scenario
    def lost_response(*_):
        calls.append('synthetic-send')
        raise TimeoutError('synthetic response loss')
    monkeypatch.setattr(router, '_send_immediate_clinic_report', lost_response)
    request_id = str(uuid.uuid4())
    headers = {'X-Delivery-Request-Id': request_id}
    assert client.post(base + '/kakao-clinic/send-report', headers=headers).status_code == 500
    assert client.get(base + '/kakao-clinic/delivery-requests/' + request_id).json()['state'] == 'unknown'
    assert client.post(base + '/kakao-clinic/send-report', headers=headers).status_code == 409
    assert calls == ['synthetic-send']
    assert client.post(base + '/kakao-clinic/send-report', headers={'X-Delivery-Request-Id': str(uuid.uuid4())}).status_code == 500
    assert client.post(base + '/kakao-clinic/scheduled-deliveries').status_code == 200
    assert calls == ['synthetic-send', 'synthetic-send']
    assert client.get(base + '/kakao-clinic/delivery-requests/' + request_id).json()['state'] == 'unknown'


def test_explicit_new_http_send_and_schedule_after_success(scenario, monkeypatch):
    client, _, base, calls = scenario
    def deliver(*args):
        calls.append('synthetic-send')
        return {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'text', 'sentCount': 1}
    monkeypatch.setattr(router, '_send_immediate_clinic_report', deliver)
    first = str(uuid.uuid4())
    second = str(uuid.uuid4())
    url = base + '/kakao-clinic/send-report'
    assert client.post(url, headers={'X-Delivery-Request-Id': first}).status_code == 200
    assert client.post(url, headers={'X-Delivery-Request-Id': first}).status_code == 200
    assert calls == ['synthetic-send']
    assert client.post(url, headers={'X-Delivery-Request-Id': second}).status_code == 200
    assert calls == ['synthetic-send', 'synthetic-send']
    assert client.get(base + '/kakao-clinic/delivery-requests/' + first).json()['state'] == 'sent'
    assert client.post(base + '/kakao-clinic/scheduled-deliveries').json()['state'] == 'queued'


def test_confirmed_pre_send_failure_allows_new_request(scenario, monkeypatch):
    from personal_project import native_kakao
    client, _, base, calls = scenario
    def not_started(*_):
        calls.append('preflight')
        raise native_kakao.NativeKakaoError(409, 'synthetic', 'recipient_missing', delivery_status='not_started')
    monkeypatch.setattr(router, '_send_immediate_clinic_report', not_started)
    first = str(uuid.uuid4())
    assert client.post(base + '/kakao-clinic/send-report', headers={'X-Delivery-Request-Id': first}).status_code == 409
    assert client.get(base + '/kakao-clinic/delivery-requests/' + first).json()['state'] == 'failed'
    assert client.post(base + '/kakao-clinic/scheduled-deliveries').status_code == 200
    assert calls == ['preflight']
