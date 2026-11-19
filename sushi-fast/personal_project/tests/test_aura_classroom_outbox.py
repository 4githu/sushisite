"""Synthetic-only classroom scheduling; never touches a real Kakao session."""
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from personal_project import aura_classroom_outbox as classroom

KST = ZoneInfo('Asia/Seoul')


def round_(id, start, end, modality='in_person', status='scheduled'):
    return {'id': id, 'schoolId': 10, 'schoolName': '가상고', 'startTime': start,
            'endTime': end, 'attendanceStatus': status, 'modality': modality,
            'targets': [{'id': id + 100, 'studentName': '가학생'}]}


def fixture_db(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(tmp_path / 'synthetic-outbox.db')
    db.row_factory = sqlite3.Row
    classroom.init(db)
    return db


def test_next_day_selection_includes_near_remote_but_not_exact_hour():
    p = round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    near = round_(2, '2026-10-29T11:59:59+09:00', '2026-10-29T12:30:00+09:00', 'remote')
    exact = round_(3, '2026-10-29T12:00:00+09:00', '2026-10-29T13:00:00+09:00', 'remote')
    prior = round_(4, '2026-10-28T23:00:00+09:00', '2026-10-29T00:00:00+09:00')
    selection = classroom.compose(datetime(2026, 10, 28, 9, tzinfo=KST), [p, near, exact, prior])
    assert selection['roundIds'] == [1, 2]
    assert selection['nearbyRemoteRounds'] == [{'remoteRoundId': 2, 'nearbyInPersonRoundIds': [1], 'gapSeconds': 3599}]
    assert 'warnings' not in selection
    assert selection['text'] == ('10/29(목)\n10:00-11:00 가상고 가학생\n'
                                 '11:59-12:30 가상고 가학생 (비대면)\n\n'
                                 '위 일정의 강의실 배정 부탁드립니다.')
    assert '강의실 불필요' not in selection['text']
    assert '12:00-13:00' not in selection['text']


def test_remote_only_skips_and_unknown_modality_blocks():
    r = round_(1, '2026-10-29T09:00:00', '2026-10-29T10:00:00', 'remote')
    assert classroom.compose(datetime(2026, 10, 28, 9, tzinfo=KST), [r])['reason'] == 'skip_no_in_person'
    r.pop('modality')
    assert classroom.compose(datetime(2026, 10, 28, 9, tzinfo=KST), [r])['reason'] == 'unverified_round'


def test_duplicate_and_invalid_next_day_rounds_fail_closed():
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    onsite = round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    remote = round_(2, '2026-10-29T11:59:00+09:00', '2026-10-29T12:30:00+09:00', 'remote')
    assert classroom.compose(now, [onsite, remote, dict(remote)])['reason'] == 'unverified_round'
    invalid = dict(remote, endTime='2026-10-29T11:00:00+09:00')
    assert classroom.compose(now, [onsite, invalid])['reason'] == 'invalid_round'
    unverified = dict(remote, modality='unverified')
    assert classroom.compose(now, [onsite, unverified])['reason'] == 'unverified_round'


def test_tick_is_unique_by_local_date_and_never_sends_without_approval(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    calls = []
    def bridge(*args, **kwargs):
        calls.append((args, kwargs))
        return {'sent': True}
    first = classroom.tick(db, 7, now, lambda uid: rounds, bridge)
    again = classroom.tick(db, 7, now + timedelta(seconds=30), lambda uid: rounds, bridge)
    assert first['state'] == again['state'] == 'blocked'
    assert first['id'] == again['id']
    assert calls == []
    assert classroom.status(db, 7, '2026-10-28')['state'] == 'blocked'
    assert classroom.tick(db, 7, now - timedelta(seconds=1), lambda uid: rounds, bridge)['state'] == 'too_early'


def test_approved_synthetic_send_rechecks_identity_and_freezes_on_unknown(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    def bridge(command, **kw):
        if command == 'search': return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        raise TimeoutError('ack lost')
    result = classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)
    assert result['state'] == 'unknown'
    assert result['selectedRoom'] == classroom.PRIMARY_ROOM
    assert classroom.tick(db, 7, now, lambda uid: rounds, lambda *a, **kw: pytest.fail('replayed'), approved=True)['state'] == 'unknown'


def test_changed_schedule_and_unverified_room_do_not_send(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    fetches = 0
    def fetch(uid):
        nonlocal fetches
        fetches += 1
        return rounds if fetches == 1 else []
    assert classroom.tick(db, 7, now, fetch, lambda *a, **kw: pytest.fail('sent'), approved=True)['state'] == 'failed'
    db = fixture_db(tmp_path / 'second')
    def bridge(command, **kw):
        return {'found': False, 'room': kw['room'], 'searchEvidence': 'confirmed_absent'}
    assert classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)['state'] == 'blocked'


def test_crash_running_becomes_unknown_no_replay(tmp_path):
    db = fixture_db(tmp_path)
    db.execute("INSERT INTO aura_classroom_outbox(user_id, run_date, target_date, purpose, state, detail) VALUES(7,'2026-10-28','2026-10-29','classroom_request','running','{}')")
    db.commit()
    classroom.init(db)
    assert classroom.status(db, 7, '2026-10-28')['state'] == 'unknown'


def test_schedule_mutates_during_search_and_cannot_send(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    def bridge(command, **kw):
        if command == 'search':
            rounds[0]['attendanceStatus'] = 'cancelled'
            return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        pytest.fail('must not send stale schedule')
    assert classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)['state'] == 'failed'


def test_late_wakeup_does_not_silently_send(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 10, tzinfo=KST)
    result = classroom.tick(db, 7, now, lambda uid: pytest.fail('late fetch'), lambda *a, **kw: pytest.fail('late send'), approved=True)
    assert result['state'] == 'missed_window'


def test_remote_before_and_overlap_and_offset_dates():
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    p = round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')
    before = round_(2, '2026-10-29T08:01:00+09:00', '2026-10-29T09:01:00+09:00', 'remote')
    overlap = round_(3, '2026-10-29T01:30:00Z', '2026-10-29T02:30:00Z', 'remote')
    far = round_(4, '2026-10-29T08:00:00+09:00', '2026-10-29T09:00:00+09:00', 'remote')
    result = classroom.compose(now, [p, before, overlap, far])
    assert result['roundIds'] == [2, 1, 3]
    assert [entry['gapSeconds'] for entry in result['nearbyRemoteRounds']] == [3540, 0]
    assert result['text'].count(' (비대면)') == 2
    assert '08:00-09:00' not in result['text']
    assert classroom.compose(now, [round_(5, '2026-10-29T00:30:00+09:00', '2026-10-29T01:30:00+09:00')])['roundIds'] == [5]


def test_near_remote_is_in_single_classroom_request_and_no_separate_warning(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00'),
              round_(2, '2026-10-29T11:59:00+09:00', '2026-10-29T12:30:00+09:00', 'remote'),
              round_(3, '2026-10-29T12:00:00+09:00', '2026-10-29T13:00:00+09:00', 'remote')]
    calls = []
    def bridge(command, **kw):
        calls.append((command, kw))
        return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'} if command == 'search' else {'sent': True}
    result = classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)
    assert result['state'] == 'succeeded'
    assert result['roundIds'] == [1, 2]
    assert 'warnings' not in result
    assert [command for command, _ in calls] == ['search', 'send']
    sent = calls[1][1]['text']
    assert '11:59-12:30 가상고 가학생 (비대면)' in sent
    assert '12:00-13:00' not in sent
    assert sent.endswith('위 일정의 강의실 배정 부탁드립니다.')
    assert '강의실 불필요' not in sent
    assert classroom.tick(db, 7, now, lambda uid: pytest.fail('duplicate fetch'), bridge, approved=True)['id'] == result['id']
    assert len(calls) == 2


def test_partial_result_is_frozen_and_disclosed(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    def bridge(command, **kw):
        if command == 'search': return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        return {'sent': False, 'partial': True}
    result = classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)
    assert result['state'] == 'unknown'
    assert result['deliveryStatus'] == 'partial'
    assert classroom.tick(db, 7, now, lambda uid: rounds, lambda *a, **kw: pytest.fail('replay'), approved=True)['id'] == result['id']


def test_second_connection_observes_durable_once_only(tmp_path):
    first_db = fixture_db(tmp_path)
    second_db = sqlite3.connect(tmp_path / 'synthetic-outbox.db')
    second_db.row_factory = sqlite3.Row
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    first = classroom.tick(first_db, 7, now, lambda uid: rounds, lambda *a, **kw: pytest.fail('send'))
    second = classroom.tick(second_db, 7, now, lambda uid: pytest.fail('duplicate fetch'), lambda *a, **kw: pytest.fail('duplicate send'))
    assert first['id'] == second['id']
    assert second_db.execute('SELECT COUNT(*) FROM aura_classroom_outbox').fetchone()[0] == 1


def test_locked_search_never_falls_back(tmp_path):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    calls = []
    def bridge(command, **kw):
        calls.append(command)
        return {'error': 'screen locked', 'room': kw['room']}
    result = classroom.tick(db, 7, now, lambda uid: rounds, bridge, approved=True)
    assert result['state'] == 'blocked'
    assert result['selectedRoom'] is None
    assert calls == ['search']

@pytest.mark.parametrize('search_result', [
    {'error': 'main window missing'},
    {'error': 'screen locked'},
    {'found': False, 'room': '다른 방', 'searchEvidence': 'confirmed_absent'},
])
def test_unverified_search_never_marks_primary_absent(tmp_path, search_result):
    db = fixture_db(tmp_path)
    now = datetime(2026, 10, 28, 9, tzinfo=KST)
    rounds = [round_(1, '2026-10-29T10:00:00+09:00', '2026-10-29T11:00:00+09:00')]
    commands = []
    def bridge(command, **kw):
        commands.append(command)
        assert command == 'search'
        return search_result
    result = classroom.tick(db, 7, now, lambda _: rounds, bridge, approved=True)
    assert result['state'] == 'blocked'
    assert result['reason'] == 'recipient_unverified'
    assert result['selectedRoom'] is None
    assert result['fallbackReason'] is None
    assert commands == ['search']


def test_recipient_failure_keeps_error_stage_without_sending(tmp_path):
    db=fixture_db(tmp_path)
    now=datetime(2026,10,28,9,tzinfo=KST)
    rounds=[round_(1,'2026-10-29T10:00:00+09:00','2026-10-29T11:00:00+09:00')]
    def bridge(command,**kw):
        assert command=='search'
        return {'errorCode':'search_unsettled','error':'synthetic search failure'}
    result=classroom.tick(db,7,now,lambda uid:rounds,bridge,approved=True)
    assert result['state']=='blocked'
    assert result['deliveryStatus']=='not_started'
    assert result['bridgeErrorCode']=='search_unsettled'
