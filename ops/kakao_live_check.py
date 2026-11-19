#!/usr/bin/env python3
"""Explicitly authorized live checks: fixed synthetic payloads, two test rooms only.

Each attempt ID admits at most one send. Existing/uncertain attempts are never replayed.
No Aura student records, report generation, credentials or production room settings.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ('대학생 자료 공유방', '본계정')


def _check_unlocked(room, kind, attempt, *, root=ROOT, invoke=None, keep_room_open=False):
    if room not in ROOMS or kind not in ('text', 'image') or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', attempt):
        raise ValueError('Use a permitted room, text/image and an 8–80 character attempt ID.')
    binary = root/'sushi-fast/.runtime/kakao-bridge'
    fixture = root/'ops/fixtures/kakao-test.png'
    if invoke is None and (not binary.is_file() or kind == 'image' and not fixture.is_file()):
        raise FileNotFoundError('Installed bridge or synthetic fixture is missing.')
    ledger = root/'sushi-fast/.runtime/kakao-live-checks'
    ledger.mkdir(mode=0o700, exist_ok=True)
    path = ledger/(attempt+'.json')
    record = {'attempt_id': attempt, 'room': room, 'kind': kind, 'state': 'started', 'at': datetime.now(timezone.utc).isoformat()}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        old = json.loads(path.read_text())
        if old['room'] != room or old['kind'] != kind:
            raise ValueError('Attempt ID already belongs to a different test.')
        return {**old, 'already_recorded': True, 'resent': False}
    with os.fdopen(fd, 'w') as stream:
        json.dump(record, stream, ensure_ascii=False)

    def save():
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(record, ensure_ascii=False, indent=2));temp.chmod(0o600);temp.replace(path)

    def call(command, **args):
        if invoke is not None:
            return invoke(command, **args)
        proc = subprocess.run([str(binary)], input=json.dumps({'command': command, **args}, ensure_ascii=False),
                              capture_output=True, text=True, timeout=55)
        return json.loads(proc.stdout)

    try:
        health = call('status')
        if not (health.get('trusted') is True and health.get('running') is True and health.get('locked') is False):
            record.update(state='blocked', reason='kakao_unavailable');save();return record
        opened = call('search', room=room)
        if not (opened.get('opened') is True and opened.get('room') == room and opened.get('searchEvidence') == 'unique_exact'):
            record.update(state='blocked', reason='recipient_unverified', bridge_result=opened);save();return record
        marker = 'KAKAO-CHECK-'+attempt
        text = '[전송 점검] '+marker+'\n카카오 전송 도구 확인용 시험 메시지입니다. 수업·정산 안내와 무관하며 답장은 필요 없습니다.'
        record['state'] = 'sending';save()
        result = call('send', room=room, text=text if kind == 'text' else '', files=[] if kind == 'text' else [str(fixture)], keepRoomOpen=keep_room_open)
        record['bridge_result'] = result
        cleanup = result.get('cleanup', {})
        record['cleanup_verified'] = cleanup.get('searchCleared') is True and (cleanup.get('closeRequested') is False if keep_room_open and result.get('sent') is True else cleanup.get('roomClosed') is True)
        record['state'] = 'succeeded' if result.get('sent') is True else 'unknown' if result.get('uncertain') else 'failed'
        save()
        return record
    except Exception as exc:
        record.update(state='unknown' if record['state']=='sending' else 'blocked', reason=type(exc).__name__)
        save();return record


def check(room, kind, attempt, *, root=ROOT, invoke=None, keep_room_open=False):
    # Same file as the backend UI lock, including on synthetic test roots.
    default_db = root / 'sushi-fast/personal_project/personal_project.db'
    db_path = Path(os.getenv('PERSONAL_PROJECT_DB_PATH', str(default_db))) if root == ROOT else default_db
    lock_path = Path(str(db_path) + '.kakao-ui.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _check_unlocked(room, kind, attempt, root=root, invoke=invoke, keep_room_open=keep_room_open)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--room', choices=ROOMS, required=True)
    parser.add_argument('--kind', choices=('text', 'image'), default='text')
    parser.add_argument('--attempt-id', required=True)
    parser.add_argument('--keep-room-open', action='store_true', help='성공 후 채팅방을 열어 두어 연속 발송 경로를 점검합니다.')
    args = parser.parse_args()
    result = check(args.room, args.kind, args.attempt_id, keep_room_open=args.keep_room_open)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['state']=='succeeded' else 2)
