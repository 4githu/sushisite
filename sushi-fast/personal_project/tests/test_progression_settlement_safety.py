"""Synthetic-only regression for legacy progression and settlement protection."""
import os
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-progression-bootstrap-')) / 'bootstrap.sqlite'))

import pytest
from fastapi import HTTPException
from personal_project import db, repository as repo, schemas

USER = 601
START = datetime.fromisoformat('2026-09-01T09:00:00+09:00')
END = datetime.fromisoformat('2026-09-01T10:00:00+09:00')


def legacy_fixture(tmp_path, monkeypatch, versioned):
    path = tmp_path / 'legacy.sqlite'
    monkeypatch.setattr(db, 'DB_PATH', path)
    schema = db.SCHEMA.replace("    admission_year INTEGER NOT NULL DEFAULT 0,\n", "").replace(
        "    current_stage TEXT NOT NULL DEFAULT 'accepted',\n", "").replace(
        "    progress_stage TEXT NOT NULL DEFAULT 'accepted',\n", "")
    schema = schema.replace('UNIQUE(school_id, progress_stage, round_number, version)',
                            'UNIQUE(school_id, round_number, version)')
    schema = re.sub(r'CREATE INDEX IF NOT EXISTS idx_clinic_score_formats_round\s+ON clinic_report_score_formats\([^;]+;', '', schema)
    if not versioned:
        schema = schema.replace("    pricing_version INTEGER NOT NULL DEFAULT 2,\n", "")
    with sqlite3.connect(path) as conn:
        conn.executescript(schema)
        for user, school_id, name in [(601, 1, '26합성고 1-1 학기'), (601, 2, '26합성고 1-2 학기'), (602, 3, '26합성고 1-1 학기')]:
            conn.execute('INSERT INTO aura_schools(id,user_id,name) VALUES (?,?,?)', (school_id,user,name))
        for rid, user, school, rate, amount, status in [
            (11,601,1,0,0,'paid'), (12,601,2,12345,77777,'pending'),
            (13,601,2,30000,4242,'paid'), (14,602,3,90000,1,'pending')]:
            conn.execute('INSERT INTO events(id,user_id,title,start_time,end_time) VALUES (?,?,?,?,?)',
                         (rid,user,'synthetic',START.isoformat(),END.isoformat()))
            conn.execute('''INSERT INTO aura_clinic_rounds
                (id,user_id,school_id,event_id,round_number,hourly_rate,amount,payment_status)
                VALUES (?,?,?,?,?,?,?,?)''', (rid,user,school,rid,rid,rate,amount,status))
        if versioned:
            conn.execute('''INSERT INTO aura_settlement_snapshots
                (user_id,year,month,data_json,generated_at,pricing_version) VALUES (601,2026,9,?,?,?)''',
                ('{"totalAmount":12345, "items":[]}', '2025-01-02 03:04:05', 37))
        else:
            conn.execute('''INSERT INTO aura_settlement_snapshots
                (user_id,year,month,data_json,generated_at) VALUES (601,2026,9,?,?)''',
                ('{"totalAmount":12345, "items":[]}', '2025-01-02 03:04:05'))
        conn.commit()
    return path


def financial_rows(path):
    with sqlite3.connect(path) as conn:
        return conn.execute('SELECT id,hourly_rate,amount,payment_status FROM aura_clinic_rounds ORDER BY id').fetchall()


def snapshot_rows(path):
    with sqlite3.connect(path) as conn:
        return conn.execute('SELECT data_json,generated_at,pricing_version FROM aura_settlement_snapshots ORDER BY id').fetchall()


@pytest.mark.parametrize('versioned', [False, True])
def test_legacy_migration_preserves_each_round_and_snapshot(tmp_path, monkeypatch, versioned):
    path = legacy_fixture(tmp_path, monkeypatch, versioned)
    before = financial_rows(path)
    db.init_db()
    assert financial_rows(path) == before
    assert snapshot_rows(path) == [('{"totalAmount":12345, "items":[]}', '2025-01-02 03:04:05', 37 if versioned else 1)]
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_schools').fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM aura_clinic_rounds').fetchone()[0] == len(before)
    db.init_db()
    assert financial_rows(path) == before
    assert snapshot_rows(path) == [('{"totalAmount":12345, "items":[]}', '2025-01-02 03:04:05', 37 if versioned else 1)]


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    school = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='합성고'))
    other = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='다른 학교'))
    item = repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['가'], start_time=START, end_time=END))
    with db.connection() as conn:
        conn.execute('UPDATE aura_clinic_rounds SET hourly_rate=12345,amount=67890,payment_status=? WHERE id=?', ('paid', item['id']))
        conn.execute('''INSERT INTO aura_settlement_snapshots
            (user_id,year,month,data_json,generated_at,pricing_version) VALUES (?,?,?,?,?,?)''',
            (USER,2026,9,'{"totalAmount":67890,"items":[{"id":%d,"amount":67890}]}' % item['id'], '2025-01-02 03:04:05', 6))
        conn.commit()
    return item, other


def test_nonpricing_patches_and_reads_preserve_paid_and_snapshot(synthetic):
    item, other = synthetic
    path = db.DB_PATH
    before = financial_rows(path)
    snap = snapshot_rows(path)
    for patch in [dict(school_id=other['id']), dict(round_number=2), dict(description='메모'),
                  dict(progress_stage=item['progressStage']), dict(start_time=START,end_time=END),
                  dict(targets=[{'id':item['targets'][0]['id'],'student_name':'가'}])]:
        repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(**patch))
        assert financial_rows(path) == before
        assert snapshot_rows(path) == snap
    repo.get_clinic_round(USER,item['id'])
    repo.school_settlements(USER,2026,9)
    db.init_db()
    assert financial_rows(path) == before
    assert snapshot_rows(path) == snap


def test_paid_schedule_edit_defers_price_calculation_and_preserves_payment_history(synthetic):
    item, _ = synthetic
    snap = snapshot_rows(db.DB_PATH)
    repo.update_clinic_round(USER,item['id'],schemas.ClinicRoundUpdate(
        end_time=datetime.fromisoformat('2026-09-01T11:00:00+09:00')))
    saved=repo.get_clinic_round(USER,item['id'])
    assert saved['amount']==67890 and saved['paymentStatus']=='paid'
    assert snapshot_rows(db.DB_PATH)==snap


def test_following_scope_reprices_only_actual_input_changes(synthetic):
    item, other = synthetic
    second = repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=other['id'], round_number=2, student_names=['나'],
        start_time=datetime.fromisoformat('2026-09-02T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-02T11:00:00+09:00')))
    with db.connection() as conn:
        conn.execute('UPDATE aura_clinic_rounds SET series_group_id=?,series_index=0 WHERE id=?', ('synthetic-group',item['id']))
        conn.execute('UPDATE aura_clinic_rounds SET series_group_id=?,series_index=1 WHERE id=?', ('synthetic-group',second['id']))
        conn.commit()
    before = financial_rows(db.DB_PATH)
    repo.update_clinic_round(USER,item['id'],schemas.ClinicRoundUpdate(scope='following',end_time=END))
    assert financial_rows(db.DB_PATH) == before
    saved=repo.get_clinic_round(USER,second['id'])
    assert (datetime.fromisoformat(saved['endTime'])-datetime.fromisoformat(saved['startTime'])).total_seconds()==7200


def test_delete_round_keeps_existing_month_snapshot(synthetic):
    item, _ = synthetic
    snap = snapshot_rows(db.DB_PATH)
    repo.delete_clinic_round(USER, item['id'])
    assert snapshot_rows(db.DB_PATH) == snap


def test_new_round_does_not_delete_existing_month_snapshot(synthetic):
    item, other = synthetic
    snap = snapshot_rows(db.DB_PATH)
    repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=other['id'], round_number=2, student_names=['나'],
        start_time=datetime.fromisoformat('2026-09-02T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-02T10:00:00+09:00')))
    assert snapshot_rows(db.DB_PATH) == snap


def test_target_count_edit_defers_calculation_and_preserves_existing_values(synthetic):
    item,_=synthetic
    before=financial_rows(db.DB_PATH);snapshot=snapshot_rows(db.DB_PATH)
    added=repo.add_round_target(USER,item['id'],schemas.RoundTargetCreate(student_name='나'))
    assert len(repo.get_clinic_round(USER,item['id'])['targets'])==2
    assert financial_rows(db.DB_PATH)==before and snapshot_rows(db.DB_PATH)==snapshot
    repo.delete_round_target(USER,added['id'],confirm=True)
    assert len(repo.get_clinic_round(USER,item['id'])['targets'])==1
    assert financial_rows(db.DB_PATH)==before and snapshot_rows(db.DB_PATH)==snapshot


def test_partial_migration_backup_restore_and_retry(tmp_path, monkeypatch):
    path = legacy_fixture(tmp_path, monkeypatch, True)
    backup = tmp_path / 'backup.sqlite'
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    original_rounds = financial_rows(path)
    original_snapshot = snapshot_rows(path)
    original = db._migrate_school_progression
    def fail_after_metadata(conn):
        original(conn)
        raise RuntimeError('synthetic interrupted migration')
    monkeypatch.setattr(db, '_migrate_school_progression', fail_after_metadata)
    with pytest.raises(RuntimeError, match='synthetic interrupted migration'):
        db.init_db()
    # DDL/executescript may commit. Fail closed: restore the consistent backup,
    # rather than assuming rollback of a partially upgraded database.
    with sqlite3.connect(backup) as source, sqlite3.connect(path) as destination:
        source.backup(destination)
    assert financial_rows(path) == original_rounds
    assert snapshot_rows(path) == original_snapshot
    monkeypatch.setattr(db, '_migrate_school_progression', original)
    db.init_db()
    once = financial_rows(path), snapshot_rows(path)
    db.init_db()
    assert (financial_rows(path), snapshot_rows(path)) == once
    assert financial_rows(path) == original_rounds
    assert snapshot_rows(path) == original_snapshot






def test_paid_schedule_edit_reads_after_write_lock(synthetic, monkeypatch):
    item, _ = synthetic
    original = repo._owned_row
    seen = []
    def checked(conn, table, row_id, user_id):
        if table == 'aura_clinic_rounds':
            seen.append(conn.in_transaction)
        return original(conn, table, row_id, user_id)
    monkeypatch.setattr(repo, '_owned_row', checked)
    repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(
        end_time=datetime.fromisoformat('2026-09-01T11:00:00+09:00')))
    assert seen and all(seen)

def test_target_approval_reads_after_write_lock(synthetic, monkeypatch):
    item, _ = synthetic
    original = repo._check_price_change
    seen = []
    def checked(conn, *args):
        seen.append(conn.in_transaction)
        return original(conn, *args)
    monkeypatch.setattr(repo, '_check_price_change', checked)
    repo.add_round_target(USER, item['id'], schemas.RoundTargetCreate(student_name='나'))
    assert seen == []  # Editing does not enter a price-approval path.

def test_stale_paid_patch_preview_after_competing_writer(synthetic, monkeypatch):
    item, _ = synthetic
    original = repo._owned_row
    attempted = []
    def concurrent_writer(conn, table, row_id, user_id):
        if table == 'aura_clinic_rounds' and not attempted:
            with sqlite3.connect(db.DB_PATH, timeout=0.01) as writer:
                try:
                    writer.execute('UPDATE aura_clinic_rounds SET amount=99999 WHERE id=?', (row_id,))
                except sqlite3.OperationalError as exc:
                    assert 'locked' in str(exc)
                    attempted.append(True)
                else:
                    pytest.fail('concurrent write passed approval transaction')
        return original(conn, table, row_id, user_id)
    monkeypatch.setattr(repo, '_owned_row', concurrent_writer)
    repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(
        end_time=datetime.fromisoformat('2026-09-01T11:00:00+09:00'),
        approved_price_changes={item['id']: (67890, 60000)}))
    assert attempted
    assert financial_rows(db.DB_PATH)[0][2] == 67890

def test_delete_target_approval_reads_after_write_lock(synthetic, monkeypatch):
    item, _ = synthetic
    with db.connection() as conn:
        conn.execute('INSERT INTO aura_round_targets(round_id, student_name, sort_order) VALUES (?,?,?)',
                     (item['id'], '나', 1))
        target_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.commit()
    original = repo._check_price_change
    seen = []
    def checked(conn, *args):
        seen.append(conn.in_transaction)
        return original(conn, *args)
    monkeypatch.setattr(repo, '_check_price_change', checked)
    repo.delete_round_target(USER, target_id, confirm=True)
    assert seen == []  # Editing does not enter a price-approval path.


def _settlement_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project.router import router, current_user_id
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: USER
    return TestClient(app)






