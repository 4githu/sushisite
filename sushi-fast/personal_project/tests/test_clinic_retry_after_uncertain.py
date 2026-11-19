import sqlite3
import uuid
import pytest
from fastapi import HTTPException
from personal_project import clinic_scheduled_delivery as q


def setup(monkeypatch, tmp_path):
    def connect():
        conn = sqlite3.connect(tmp_path / 'test.sqlite', timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr(q.repository, 'connection', connect)
    monkeypatch.setattr(q.repository, 'get_or_create_target_report', lambda *_: {'id': 10})
    q.init()
    return connect


@pytest.mark.parametrize('state', ['unknown', 'partial', 'failed'])
def test_new_click_allows_new_request_without_changing_old(monkeypatch, tmp_path, state):
    setup(monkeypatch, tmp_path)
    old_request = uuid.uuid4().hex
    old, _ = q.reserve_immediate(1, 2, old_request)
    q.finish_immediate(old, state, 'old_error')
    same, old_result = q.reserve_immediate(1, 2, old_request)
    assert same is None and old_result['state'] == state
    new, result = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    assert new != old and result is None
    assert q.get(1, old)['state'] == state
    assert q.run_once(now=9999999999)['state'] == 'waiting'


@pytest.mark.parametrize('state', ['unknown', 'partial', 'failed'])
def test_new_schedule_does_not_reuse_uncertain_job(monkeypatch, tmp_path, state):
    setup(monkeypatch, tmp_path)
    old, _ = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    q.finish_immediate(old, state, 'old_error')
    new = q.enqueue(1, 2, now=100)
    assert new['id'] != old and new['state'] == 'queued'
    assert q.get(1, old)['state'] == state


def test_inflight_still_blocks_new_request(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    q.reserve_immediate(1, 2, uuid.uuid4().hex)
    with pytest.raises(HTTPException) as e:
        q.reserve_immediate(1, 2, uuid.uuid4().hex)
    assert e.value.status_code == 409


def test_concurrent_new_clicks_only_one_request_starts(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    setup(monkeypatch, tmp_path)
    old, _ = q.reserve_immediate(1, 2, uuid.uuid4().hex)
    q.finish_immediate(old, 'unknown', 'delivery_unknown')
    def attempt(_):
        try:
            job, _ = q.reserve_immediate(1, 2, uuid.uuid4().hex)
            return 'started' if job else 'replayed'
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count('started') == 1 and results.count(409) == 7
    assert q.get(1, old)['state'] == 'unknown'
