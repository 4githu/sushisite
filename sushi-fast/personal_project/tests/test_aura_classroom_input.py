"""Synthetic Aura DB only; no production connection, GUI or network."""
import os
import sqlite3
import tempfile
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-input-bootstrap-')) / 'bootstrap.sqlite'))

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from personal_project import db, repository as repo, schemas
from personal_project import aura_classroom_outbox as outbox
from personal_project.aura_classroom_input import read_owner_rounds

KST = ZoneInfo('Asia/Seoul')
NOW = datetime(2026, 10, 28, 9, tzinfo=KST)

@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'isolated.sqlite')
    db.init_db()
    return lambda uid, name: repo.create_school(uid, schemas.SchoolCreate(admission_year=2026, school_name=name))['id']

def add(uid, sid, number, start, end, modality='in_person', names=None):
    created = repo.create_clinic_round(uid, schemas.ClinicRoundCreate(
        school_id=sid, round_number=number, progress_stage='grade1_semester1',
        student_names=names or [f'합성{number}'], start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end), modality=modality, allow_overlap=True))
    return created['id']

def test_owner_instant_selection_and_ids(synthetic):
    sid = synthetic(301, '합성검증고')
    foreign_sid = synthetic(302, '타인학교')
    onsite = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    near = add(301, sid, 2, '2026-10-29T11:59:59+09:00', '2026-10-29T12:29:59+09:00', 'remote')
    far = add(301, sid, 3, '2026-10-29T12:00:00+09:00', '2026-10-29T12:30:00+09:00', 'remote')
    midnight = add(301, sid, 4, '2026-10-28T15:00:00Z', '2026-10-28T16:00:00Z')
    naive = add(301, sid, 5, '2026-10-29T08:00:00', '2026-10-29T09:00:00')
    add(301, sid, 6, '2026-10-29T00:00:00+14:00', '2026-10-29T01:00:00+14:00')
    add(302, foreign_sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    rows = read_owner_rounds(301, NOW)
    assert {r['id'] for r in rows} == {onsite, near, far, midnight, naive}
    assert all(r['schoolId'] == sid and r['targets'] and all(t['id'] for t in r['targets']) for r in rows)
    plan = outbox.compose(NOW, rows)
    assert plan['roundIds'] == [midnight, naive, onsite, near]
    assert plan['nearbyRemoteRounds'][0]['gapSeconds'] == 3599
    assert '합성3' not in plan['text']
    assert '합성1' in plan['text']

def test_unverified_and_zero_onsite_are_closed(synthetic):
    sid = synthetic(301, '합성검증고')
    rid = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00', 'remote')
    assert outbox.compose(NOW, read_owner_rounds(301, NOW))['reason'] == 'skip_no_in_person'
    with db.connection() as conn:
        conn.execute('UPDATE aura_clinic_rounds SET modality=? WHERE id=?', ('unverified', rid))
        conn.commit()
    assert outbox.compose(NOW, read_owner_rounds(301, NOW))['reason'] == 'unverified_round'

def test_snapshot_change_same_text_blocks_send(synthetic, tmp_path):
    sid = synthetic(301, '합성검증고')
    rid = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    conn = sqlite3.connect(tmp_path / 'outbox.sqlite')
    conn.row_factory = sqlite3.Row
    outbox.init(conn)
    def bridge(command, **kw):
        if command == 'search':
            with db.connection() as writer:
                writer.execute('UPDATE aura_round_targets SET id=id+10000 WHERE round_id=?', (rid,))
                writer.commit()
            return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        pytest.fail('changed snapshot must not send')
    result = outbox.tick(conn, 301, NOW, lambda owner: read_owner_rounds(owner, NOW), bridge, approved=True)
    assert result['state'] == 'failed'
    assert result['reason'] == 'schedule_changed_after_search'
    assert 'snapshot' not in result

def test_change_between_final_reread_and_mock_click_is_not_verified(synthetic, tmp_path):
    sid = synthetic(301, '합성검증고')
    rid = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    conn = sqlite3.connect(tmp_path / 'race-outbox.sqlite')
    conn.row_factory = sqlite3.Row
    outbox.init(conn)
    calls = []
    def bridge(command, **kw):
        calls.append(command)
        if command == 'search':
            return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        # Simulate an independent writer committing after the final read but
        # before the mock GUI click. A successful GUI ack cannot prove freshness.
        with db.connection() as writer:
            writer.execute('UPDATE aura_clinic_rounds SET modality=? WHERE id=?', ('remote', rid))
            writer.commit()
        return {'sent': True}
    result = outbox.tick(conn, 301, NOW, lambda owner: read_owner_rounds(owner, NOW), bridge, approved=True)
    assert calls == ['search', 'send']  # stale click occurred: not a preventive gate
    assert result['state'] == 'unknown'
    assert result['reason'] == 'schedule_changed_during_send'
    assert result['deliveryStatus'] == 'unknown'
    assert outbox.tick(conn, 301, NOW, lambda _: pytest.fail('replayed'), bridge, approved=True)['state'] == 'unknown'

def test_cross_owner_school_reference_blocks_instead_of_leaking(synthetic):
    sid = synthetic(301, '합성검증고')
    other = synthetic(302, '타인학교')
    rid = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    with db.connection() as writer:
        writer.execute('UPDATE aura_clinic_rounds SET school_id=? WHERE id=?', (other, rid))
        writer.commit()
    with pytest.raises(ValueError, match='cross_owner_reference'):
        read_owner_rounds(301, NOW)

def test_adapter_rejects_untrusted_owner_and_naive_clock(synthetic):
    with pytest.raises(ValueError, match='owner ID'):
        read_owner_rounds(0, NOW)
    with pytest.raises(ValueError, match='timezone-aware'):
        read_owner_rounds(301, NOW.replace(tzinfo=None))

def test_missing_target_name_blocks_instead_of_generating_blank_request(synthetic):
    sid = synthetic(301, '합성검증고')
    rid = add(301, sid, 1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    with db.connection() as writer:
        writer.execute('UPDATE aura_round_targets SET student_name=? WHERE round_id=?', ('', rid))
        writer.commit()
    assert outbox.compose(NOW, read_owner_rounds(301, NOW))['reason'] == 'invalid_round'
