"""Aura classroom outbox; production scheduling is bound by classroom_delivery.

Caller must supply an authorized user's rounds and a verified GUI bridge. This module
never infers modality from a memo/name; a real user or Kakao identity is not configured.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
PRIMARY_ROOM = '[아우라] 생명 클리닉 조교방'
PURPOSE = 'classroom_request'


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS aura_classroom_outbox (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, run_date TEXT NOT NULL,
        target_date TEXT NOT NULL, purpose TEXT NOT NULL, state TEXT NOT NULL,
        detail TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, run_date, purpose))''')
    # Running may have crossed the send boundary; never retry after restart.
    db.execute("UPDATE aura_classroom_outbox SET state='unknown', updated_at=CURRENT_TIMESTAMP WHERE state='running'")
    db.commit()


def _instant(value):
    if not value:
        raise ValueError('missing_time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return (parsed.replace(tzinfo=KST) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)


def compose(now, rounds):
    if now.tzinfo is None:
        raise ValueError('now must have a timezone')
    target = (now.astimezone(KST).date() + timedelta(days=1))
    selected = []
    seen = set()
    snapshot_rows = []
    for row in rounds:
        start = _instant(row['startTime'])
        if start.astimezone(KST).date() != target:
            continue
        # IDs are part of the pre-send snapshot even when the rendered text
        # remains unchanged (e.g. replacing a target with the same name).
        snapshot_rows.append({key: row.get(key) for key in (
            'id', 'schoolId', 'schoolName', 'startTime', 'endTime',
            'attendanceStatus', 'modality', 'targets')})
        if row['attendanceStatus'] == 'cancelled':
            continue
        end = _instant(row['endTime'])
        if start >= end or not row.get('id') or not row.get('schoolId') or not row.get('schoolName') or not row.get('targets') or any(not t.get('id') or not t.get('studentName') for t in row['targets']):
            return {'reason': 'invalid_round', 'targetDate': target.isoformat()}
        if row['id'] in seen or row.get('modality') not in ('in_person', 'remote'):
            return {'reason': 'unverified_round', 'targetDate': target.isoformat()}
        seen.add(row['id'])
        selected.append((start, end, row))
    selected.sort(key=lambda item: (item[0], item[2]['id']))
    onsite = [item for item in selected if item[2]['modality'] == 'in_person']
    if not onsite:
        return {'reason': 'skip_no_in_person', 'targetDate': target.isoformat()}
    included = list(onsite)
    nearby_remote_rounds = []
    for remote in (item for item in selected if item[2]['modality'] == 'remote'):
        gaps = [(int(max(0, (p[0]-remote[1]).total_seconds(), (remote[0]-p[1]).total_seconds())), p[2]['id']) for p in onsite]
        near = [(seconds, rid) for seconds, rid in gaps if seconds < 3600]
        if near:
            included.append(remote)
            nearby_remote_rounds.append({'remoteRoundId': remote[2]['id'], 'nearbyInPersonRoundIds': sorted(rid for _, rid in near), 'gapSeconds': min(seconds for seconds, _ in near)})
    included.sort(key=lambda item: (item[0], item[2]['id']))
    labels = '일월화수목금토'
    lines = [f'{target.month}/{target.day}({labels[(target.weekday()+1)%7]})']
    for start, end, row in included:
        start_local, end_local = start.astimezone(KST), end.astimezone(KST)
        names = ', '.join(t['studentName'] for t in row['targets'])
        suffix = ' (비대면)' if row['modality'] == 'remote' else ''
        lines.append(f'{start_local:%H:%M}-{end_local:%H:%M} {row["schoolName"]} {names}{suffix}')
    lines.extend(('', '위 일정의 강의실 배정 부탁드립니다.'))
    snapshot = hashlib.sha256(json.dumps(sorted(snapshot_rows, key=lambda r: str(r['id'])), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'reason': 'ready', 'targetDate': target.isoformat(), 'roundIds': [row['id'] for _, _, row in included], 'nearbyRemoteRounds': nearby_remote_rounds, 'text': '\n'.join(lines), 'snapshot': snapshot}


def status(db, user_id, run_date):
    row = db.execute('SELECT * FROM aura_classroom_outbox WHERE user_id=? AND run_date=? AND purpose=?', (user_id, run_date, PURPOSE)).fetchone()
    if row is None:
        return None
    return {'id': row['id'], 'runDate': row['run_date'], 'targetDate': row['target_date'], 'state': row['state'], **json.loads(row['detail'])}


def _update(db, job_id, state, detail):
    db.execute('UPDATE aura_classroom_outbox SET state=?, detail=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (state, json.dumps(detail, ensure_ascii=False), job_id))
    db.commit()


def tick(db, user_id, now, fetch_rounds, bridge, *, approved=False):
    """One guarded authorized tick; classroom_delivery supplies the production owner and bridge.

    The bridge is injected by the caller. A locked/no-window
    response must be an error, not evidence of absence. No fallback to name-only 1:1.
    """
    local = now.astimezone(KST)
    if local.hour < 9:
        return {'state': 'too_early'}
    run_date = local.date().isoformat()
    existing = status(db, user_id, run_date)
    if existing:
        return existing
    target_date = (local.date() + timedelta(days=1)).isoformat()
    # Reserve before any lookup or GUI side effect. Concurrent processes share one key.
    try:
        db.execute('INSERT INTO aura_classroom_outbox(user_id,run_date,target_date,purpose,state,detail) VALUES(?,?,?,?,?,?)',
                   (user_id, run_date, target_date, PURPOSE, 'running', '{}'))
        db.commit()
    except sqlite3.IntegrityError:
        return status(db, user_id, run_date)
    job = status(db, user_id, run_date)
    assert job is not None
    detail = {'targetRoom': PRIMARY_ROOM, 'selectedRoom': None, 'fallbackReason': None, 'deliveryStatus': 'not_started'}
    if local.hour != 9:
        detail['reason'] = 'missed_window'
        _update(db, job['id'], 'missed_window', detail)
        return status(db, user_id, run_date)
    try:
        plan = compose(now, fetch_rounds(user_id))
        detail.update({k: v for k, v in plan.items() if k not in ('text', 'snapshot')})
        if plan['reason'] != 'ready':
            _update(db, job['id'], 'skipped' if plan['reason'] == 'skip_no_in_person' else 'blocked', detail)
        elif not approved:
            detail['reason'] = 'approval_required'
            _update(db, job['id'], 'blocked', detail)
        elif compose(now, fetch_rounds(user_id)) != plan:
            detail['reason'] = 'schedule_changed'
            _update(db, job['id'], 'failed', detail)
        else:
            opened = bridge('search', room=PRIMARY_ROOM)
            if opened.get('opened') is not True or opened.get('room') != PRIMARY_ROOM or opened.get('searchEvidence') != 'unique_exact':
                if opened.get('errorCode'):
                    detail['bridgeErrorCode'] = opened['errorCode']
                detail['reason'] = 'fallback_identity_unverified' if opened.get('found') is False and opened.get('room') == PRIMARY_ROOM and opened.get('searchEvidence') == 'confirmed_absent' else 'recipient_unverified'
                _update(db, job['id'], 'blocked', detail)
            elif compose(now, fetch_rounds(user_id)) != plan:
                detail['reason'] = 'schedule_changed_after_search'
                _update(db, job['id'], 'failed', detail)
            else:
                detail['selectedRoom'] = PRIMARY_ROOM
                # Durable running row precedes the click; crash becomes unknown.
                _update(db, job['id'], 'running', detail)
                result = bridge('send', room=PRIMARY_ROOM, text=plan['text'], files=[])
                # This is detection after the mock click, NOT an atomicity guard:
                # another writer may still change the schedule after this read.
                if compose(now, fetch_rounds(user_id)) != plan:
                    detail['reason'] = 'schedule_changed_during_send'
                    detail['deliveryStatus'] = 'unknown'
                    _update(db, job['id'], 'unknown', detail)
                else:
                    detail['deliveryStatus'] = 'verified' if result.get('sent') is True else 'partial' if result.get('partial') else 'unknown' if result.get('uncertain') else 'not_verified'
                    detail['reason'] = 'send_result'
                    _update(db, job['id'], 'succeeded' if result.get('sent') is True else 'unknown', detail)
    except Exception as exc:
        # Exception at an arbitrary bridge boundary may have occurred after click.
        detail['reason'] = type(exc).__name__
        detail['deliveryStatus'] = 'unknown'
        _update(db, job['id'], 'unknown', detail)
    return status(db, user_id, run_date)
