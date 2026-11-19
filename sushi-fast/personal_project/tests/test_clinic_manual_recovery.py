import sqlite3
import uuid

import pytest
from fastapi import HTTPException
from personal_project import clinic_scheduled_delivery as q


def setup_db(monkeypatch, tmp_path):
    path = tmp_path / 'recovery.sqlite'
    def connection():
        db = sqlite3.connect(path, timeout=5)
        db.row_factory = sqlite3.Row
        return db
    monkeypatch.setattr(q.repository, 'connection', connection)
    monkeypatch.setattr(q.repository, 'get_or_create_target_report', lambda u, t: {'id': 9})
    q.init()
    return connection


def test_acknowledging_unknown_never_sends_but_permits_new_request(monkeypatch, tmp_path):
    setup_db(monkeypatch, tmp_path)
    request_id = uuid.uuid4().hex
    job, _ = q.reserve_immediate(1, 2, request_id)
    q.finish_immediate(job, 'unknown', 'delivery_unknown')
    called = []
    monkeypatch.setattr(q, '_deliver', lambda *a: called.append(1))
    result = q.acknowledge_uncertainty(1, 2, job)
    assert result['state'] == 'acknowledged_unknown'
    assert q.acknowledge_uncertainty(1, 2, job)['state'] == 'acknowledged_unknown'
    previous_job, previous = q.reserve_immediate(1, 2, request_id)
    assert previous_job is None and previous['deliveryStatus'] == 'unknown'
    new_job, previous = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    assert new_job != job and previous is None
    assert called == []


def test_recovery_rejects_sending_other_owner_and_other_target(monkeypatch, tmp_path):
    setup_db(monkeypatch, tmp_path)
    job, _ = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    for owner, target, expected in [(1, 2, 409), (2, 2, 404), (1, 3, 404)]:
        with pytest.raises(HTTPException) as e:
            q.acknowledge_uncertainty(owner, target, job)
        assert e.value.status_code == expected
    assert q.get(1, job)['state'] == 'sending'


def test_partial_http_acknowledgement_is_scoped_and_does_not_schedule(monkeypatch, tmp_path):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    setup_db(monkeypatch, tmp_path)
    job, _ = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    q.finish_immediate(job, 'partial', 'partial_delivery', {'sentCount': 1})
    def owner(request: Request):
        if request.headers.get('origin') != 'https://aura.chobab.app':
            raise HTTPException(403, 'origin')
        return int(request.headers['x-owner'])
    def read_owner(request: Request):
        return int(request.headers['x-owner'])
    app = FastAPI()
    app.include_router(q.build_router(owner, read_owner))
    client = TestClient(app)
    url = f'/aura/targets/2/kakao-clinic/scheduled-deliveries/{job}/acknowledge-uncertainty'
    assert client.post(url, headers={'x-owner':'1'}).status_code == 403
    assert client.post(url, headers={'x-owner':'2','origin':'https://aura.chobab.app'}).status_code == 404
    result = client.post(url, headers={'x-owner':'1','origin':'https://aura.chobab.app'})
    assert result.status_code == 200 and result.json()['state'] == 'acknowledged_partial'
    assert q.run_once(now=9999999999)['state'] == 'waiting'
    assert q.get(1, job)['errorCode'] == 'partial_delivery'
    assert q.enqueue(1, 2, now=100)['id'] != job
