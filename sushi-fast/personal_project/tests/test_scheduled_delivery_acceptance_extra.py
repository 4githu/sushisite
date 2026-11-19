"""Safety acceptance tests for the scheduled clinic delivery outbox."""
import sqlite3
from personal_project import clinic_scheduled_delivery as queue


def isolated(monkeypatch, tmp_path):
    path = tmp_path / 'queue.sqlite3'
    def connection():
        conn = sqlite3.connect(path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr(queue.repository, 'connection', connection)
    monkeypatch.setattr(queue.repository, 'get_or_create_target_report',
                        lambda user, target: {'id': 123, 'generatedReportJson': {'ok': True}})
    queue.init()


def test_unverified_sent_does_not_mark_sent_or_submit(monkeypatch, tmp_path):
    isolated(monkeypatch, tmp_path)
    submitted = []
    monkeypatch.setattr(queue.repository, 'update_target_report', lambda *a, **k: submitted.append((a, k)))
    monkeypatch.setattr(queue, '_deliver', lambda *a: {'sent': True, 'deliveryStatus': 'unknown'})
    item = queue.enqueue(1, 2, now=100)
    queue.run_once(now=101)
    assert queue.run_once(now=5500)['state'] == 'unknown'
    assert submitted == []
    assert queue.get(1, item['id'])['state'] == 'unknown'


def test_verified_send_submits_existing_report(monkeypatch, tmp_path):
    isolated(monkeypatch, tmp_path)
    submitted = []
    monkeypatch.setattr(queue.repository, 'update_target_report', lambda *a, **k: submitted.append((a, k)))
    monkeypatch.setattr(queue, '_deliver', lambda *a: {'sent': True, 'deliveryStatus': 'verified'})
    queue.enqueue(1, 2, now=100)
    queue.run_once(now=101)
    assert queue.run_once(now=5500)['state'] == 'sent'
    assert submitted == [((1, 123, None), {'submit': True})]
