"""Isolated SQLite and synthetic sender contract; no real delivery."""
import uuid
from personal_project import router, native_kakao
from personal_project.tests.test_scheduled_synthetic_regression import scenario


def test_success_replay_and_lookup_preserve_receipt(scenario, monkeypatch):
    client, _, base, calls = scenario
    receipt = {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'text', 'sentCount': 1,
               'destination': '본계정', 'selectedRoom': '본계정', 'fallbackReason': 'both_rooms_confirmed_absent',
               'stages': {'recipient': 'verified', 'text': 'verified'}}
    monkeypatch.setattr(router, '_send_immediate_clinic_report', lambda *_: calls.append('send') or receipt)
    request_id = str(uuid.uuid4())
    url = base + '/kakao-clinic/send-report'
    headers = {'X-Delivery-Request-Id': request_id}
    first = client.post(url, headers=headers).json()
    replay = client.post(url, headers=headers).json()
    lookup = client.get(base + '/kakao-clinic/delivery-requests/' + request_id).json()
    for result in (first, replay, lookup):
        for key, value in receipt.items(): assert result[key] == value
        assert result['completionStatus'] == 'completed'
    assert calls == ['send']


def test_partial_and_completion_failure_are_persisted(scenario, monkeypatch):
    client, _, base, calls = scenario
    def partial(*_):
        calls.append('send')
        err = native_kakao.NativeKakaoError(409, 'synthetic', 'partial_delivery', selected_room='합성 방', delivery_status='partial')
        err.delivery_result = {'destination': '합성 방', 'selectedRoom': '합성 방', 'deliveryFormat': 'images',
                               'sentCount': 2, 'stages': {'recipient': 'verified', 'images': 'verified', 'text': 'unknown'}}
        raise err
    monkeypatch.setattr(router, '_send_immediate_clinic_report', partial)
    request_id = str(uuid.uuid4())
    headers = {'X-Delivery-Request-Id': request_id}
    response = client.post(base + '/kakao-clinic/send-report', headers=headers)
    assert response.json()['detail']['state'] == 'partial'
    result = client.get(base + '/kakao-clinic/delivery-requests/' + request_id).json()
    assert result['stages']['images'] == 'verified' and result['sentCount'] == 2
    assert client.post(base + '/kakao-clinic/send-report', headers=headers).status_code == 409
    assert calls == ['send']


def test_completion_pending_is_verified_send(scenario, monkeypatch):
    client, _, base, calls = scenario
    monkeypatch.setattr(router, '_send_immediate_clinic_report', lambda *_: calls.append('send') or {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'text', 'sentCount': 1})
    monkeypatch.setattr(router.repository, 'update_target_report', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('synthetic')))
    request_id = str(uuid.uuid4())
    headers = {'X-Delivery-Request-Id': request_id}
    response = client.post(base + '/kakao-clinic/send-report', headers=headers)
    assert response.json()['detail']['completionStatus'] == 'pending'
    replay = client.post(base + '/kakao-clinic/send-report', headers=headers).json()
    assert replay['sent'] is True and replay['completionStatus'] == 'pending'
    assert calls == ['send']


def test_confirmed_failure_then_concurrent_retry_sends_once(scenario, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    client, _, base, calls = scenario
    def fail(*_):
        raise native_kakao.NativeKakaoError(409, 'synthetic', 'recipient_missing')
    monkeypatch.setattr(router, '_send_immediate_clinic_report', fail)
    url = base + '/kakao-clinic/send-report'
    first = client.post(url, headers={'X-Delivery-Request-Id': str(uuid.uuid4())})
    assert first.json()['detail']['retryable'] is True
    entered, release = Event(), Event()
    def send(*_):
        calls.append('send')
        entered.set()
        assert release.wait(5)
        return {'sent': True, 'deliveryStatus': 'verified'}
    monkeypatch.setattr(router, '_send_immediate_clinic_report', send)
    headers = {'X-Delivery-Request-Id': str(uuid.uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.post, url, headers=headers)
        assert entered.wait(5)
        try:
            lookup = client.get(base + '/kakao-clinic/delivery-requests/' + headers['X-Delivery-Request-Id'])
            duplicate = client.post(url, headers=headers)
            assert lookup.status_code == 200
            assert duplicate.status_code == 409
            for result in (lookup.json(), duplicate.json()['detail']):
                assert result['state'] == 'sending'
                assert result['deliveryStatus'] == 'unknown'
                assert result['retryable'] is False
            assert calls == ['send']
        finally:
            release.set()
        assert pending.result().status_code == 200
    assert calls == ['send']


def test_native_image_success_text_failure_reports_stages(monkeypatch):
    import pytest
    from personal_project import kakao_bridge
    count = []
    def bridge(command, **kwargs):
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        count.append(1)
        return {'sent': True} if len(count) == 1 else {'sent': False}
    monkeypatch.setattr(kakao_bridge, 'invoke', bridge)
    report = {'schoolName': '합성학교', 'studentName': '합성학생'}
    job = native_kakao.create_clinic_job(1, 2, report)
    native_kakao.store_page(job['jobId'], 1, 2, 1, 'image/png', b'\x89PNG\r\n\x1a\nsynthetic')
    with pytest.raises(native_kakao.NativeKakaoError) as caught:
        native_kakao.send_clinic_job(job['jobId'], 1, 2)
    error = caught.value
    assert error.delivery_status == 'partial'
    assert error.delivery_result['sentCount'] == 1
    assert error.delivery_result['stages'] == {'recipient': 'verified', 'images': 'verified', 'text': 'unknown'}
    assert len(count) == 2
