"""Durable, owner-scoped scheduled clinic report delivery.

Only the scheduler holding the process-wide file lock may recover or consume jobs.
Sending is recorded before touching the Kakao UI; ambiguity never auto-retries.
"""
from __future__ import annotations

import fcntl
import json
import logging
import math
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clickedAt: float
    requestId: uuid.UUID

from . import ai_report, native_kakao, report_pdf, repository, report_generation_store

log = logging.getLogger(__name__)
DELAY = 90 * 60
BUSY_DELAY = 30
_stop = threading.Event()
_thread = None


def init():
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE IF NOT EXISTS aura_clinic_delivery_queue (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
            state TEXT NOT NULL, requested_at REAL NOT NULL, send_after REAL NOT NULL,
            next_attempt REAL NOT NULL, error_code TEXT, updated_at REAL NOT NULL)""")
        # Replace the legacy partial index so a cancelled reservation permits a new one.
        db.execute("DROP INDEX IF EXISTS idx_clinic_delivery_dedup")
        db.execute("DROP INDEX IF EXISTS idx_clinic_delivery_dedup_v4")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_clinic_delivery_dedup_v5
            ON aura_clinic_delivery_queue(user_id, target_id)
            WHERE state NOT IN ('sent','failed','cancelled','unknown','partial','acknowledged_unknown','acknowledged_partial')""")
        db.execute("DROP INDEX IF EXISTS idx_clinic_delivery_dedup_v2")
        db.execute("DROP INDEX IF EXISTS idx_clinic_delivery_dedup_v3")
        db.execute("CREATE INDEX IF NOT EXISTS idx_clinic_delivery_due ON aura_clinic_delivery_queue(state,next_attempt,requested_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS aura_clinic_delivery_requests (
            user_id INTEGER NOT NULL, request_id TEXT NOT NULL, target_id INTEGER NOT NULL,
            job_id TEXT NOT NULL, PRIMARY KEY(user_id, request_id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS aura_clinic_immediate_requests (
            user_id INTEGER NOT NULL, request_id TEXT NOT NULL, target_id INTEGER NOT NULL,
            job_id TEXT NOT NULL, delivery_format TEXT, sent_count INTEGER,
            PRIMARY KEY(user_id, request_id), UNIQUE(job_id))""")
        # Serialize additive migration across workers; never store report content.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(aura_clinic_immediate_requests)')}
        if 'receipt_json' not in columns:
            db.execute('ALTER TABLE aura_clinic_immediate_requests ADD COLUMN receipt_json TEXT')
        db.commit()


def _serialize(row):
    return {'id': row['id'], 'targetId': row['target_id'], 'state': row['state'],
            'requestedAt': row['requested_at'], 'sendAfter': row['send_after'],
            'errorCode': row['error_code']}


def enqueue(user_id, target_id, now=None, request=None):
    now = time.time() if now is None else now
    repository.get_or_create_target_report(user_id, target_id)  # ownership before insertion
    init()
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        request_id = request.requestId.hex if request is not None else None
        if request is not None:
            prior = db.execute('SELECT target_id, job_id FROM aura_clinic_delivery_requests WHERE user_id=? AND request_id=?', (user_id, request_id)).fetchone()
            if prior:
                if prior['target_id'] != target_id:
                    raise HTTPException(409, '다른 예약에 사용된 요청 번호입니다.')
                row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=? AND user_id=?', (prior['job_id'], user_id)).fetchone()
                if row is None:
                    raise HTTPException(409, '기존 예약을 확인할 수 없습니다.')
                db.commit()
                return _serialize(row)
            if not math.isfinite(request.clickedAt) or not now - 300 <= request.clickedAt <= now + 5:
                raise HTTPException(422, '예약 시각을 확인할 수 없습니다. 기기 시간을 확인하고 다시 예약해 주세요.')
        row = db.execute("SELECT * FROM aura_clinic_delivery_queue WHERE user_id=? AND target_id=? AND state NOT IN ('sent','failed','cancelled','unknown','partial','acknowledged_unknown','acknowledged_partial')", (user_id, target_id)).fetchone()
        if row is not None and db.execute('SELECT 1 FROM aura_clinic_immediate_requests WHERE job_id=?', (row['id'],)).fetchone():
            raise HTTPException(409, '이 리포트의 즉시 전송 결과를 먼저 확인해주세요.')
        if row is None:
            job_id = uuid.uuid4().hex
            clicked = request.clickedAt if request is not None else now
            db.execute("INSERT INTO aura_clinic_delivery_queue VALUES(?,?,?,'queued',?,?,?,?,?)", (job_id, user_id, target_id, clicked, clicked + DELAY, now, None, now))
            row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=?', (job_id,)).fetchone()
        if request is not None:
            db.execute('INSERT INTO aura_clinic_delivery_requests VALUES(?,?,?,?)', (user_id, request_id, target_id, row['id']))
        db.commit()
        return _serialize(row)


def reserve_immediate(user_id, target_id, request_id):
    init()
    now = time.time()
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT * FROM aura_clinic_immediate_requests WHERE user_id=? AND request_id=?', (user_id, request_id)).fetchone()
        if prior:
            if prior['target_id'] != target_id:
                raise HTTPException(409, '다른 리포트에 사용된 요청 번호입니다.')
            row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=?', (prior['job_id'],)).fetchone()
            db.commit()
            return None, _immediate_result(row, prior)
        row = db.execute("SELECT id,state FROM aura_clinic_delivery_queue WHERE user_id=? AND target_id=? AND state NOT IN ('sent','failed','cancelled','unknown','partial','acknowledged_unknown','acknowledged_partial')", (user_id, target_id)).fetchone()
        if row and row['state'] in ('queued', 'ready'):
            # A new immediate request replaces a future reservation; the same
            # transaction excludes the scheduler and prevents a later double send.
            db.execute("UPDATE aura_clinic_delivery_queue SET state='cancelled',error_code='superseded_by_immediate',updated_at=? WHERE id=?", (now, row['id']))
            row = None
        if row:
            raise HTTPException(409, '리포트 생성 또는 전송이 진행 중입니다.')
        job_id = uuid.uuid4().hex
        db.execute("INSERT INTO aura_clinic_delivery_queue VALUES(?,?,?,'sending',?,?,?,?,?)", (job_id, user_id, target_id, now, now, now, None, now))
        db.execute('INSERT INTO aura_clinic_immediate_requests(user_id,request_id,target_id,job_id) VALUES(?,?,?,?)', (user_id, request_id, target_id, job_id))
        db.commit()
        return job_id, None


def _immediate_result(row, request):
    result = _serialize(row)
    result.update({'requestId': request['request_id'], 'deliveryFormat': request['delivery_format'], 'sentCount': request['sent_count']})
    if request['receipt_json']:
        result.update(json.loads(request['receipt_json']))
    state = row['state']
    result.update({'sent': state == 'sent',
                   'deliveryStatus': {'sent': 'verified', 'failed': 'not_started', 'sending': 'unknown', 'acknowledged_unknown': 'unknown', 'acknowledged_partial': 'partial'}.get(state, state),
                   'completionStatus': ('pending' if row['error_code'] == 'completion_pending' else 'completed') if state == 'sent' else 'not_started',
                   'retryable': state == 'failed'})
    return result


def lookup_immediate(user_id, target_id, request_id):
    init()
    with repository.connection() as db:
        req = db.execute('SELECT * FROM aura_clinic_immediate_requests WHERE user_id=? AND target_id=? AND request_id=?', (user_id, target_id, request_id)).fetchone()
        if not req:
            raise HTTPException(404, {'code': 'request_not_found', 'message': '요청을 찾을 수 없어 전송 여부를 판단할 수 없습니다.', 'deliveryStatus': 'unknown', 'retryable': False})
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=?', (req['job_id'],)).fetchone()
        return _immediate_result(row, req)


def finish_immediate(job_id, state, error_code=None, result=None):
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if result is not None:
            fmt = result.get('deliveryFormat') if result.get('deliveryFormat') in ('text', 'image', 'images') else None
            count = result.get('sentCount') if type(result.get('sentCount')) is int else None
            receipt = {key: result[key] for key in ('destination', 'targetRoom', 'selectedRoom', 'fallbackReason', 'stages') if key in result}
            db.execute('UPDATE aura_clinic_immediate_requests SET delivery_format=?,sent_count=?,receipt_json=? WHERE job_id=?', (fmt, count, json.dumps(receipt, ensure_ascii=False), job_id))
        now = time.time()
        db.execute("UPDATE aura_clinic_delivery_queue SET state=?,error_code=?,updated_at=?,next_attempt=? WHERE id=? AND (state='sending' OR (state='unknown' AND error_code='restart_during_send'))", (state, error_code, now, now + BUSY_DELAY, job_id))
        db.commit()


def finish_completion(job_id):
    with repository.connection() as db:
        db.execute("UPDATE aura_clinic_delivery_queue SET error_code=NULL,updated_at=? WHERE id=? AND state='sent' AND error_code='completion_pending'", (time.time(), job_id))
        db.commit()


def get(user_id, job_id, target_id=None):
    init()
    with repository.connection() as db:
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE user_id=? AND id=?', (user_id, job_id)).fetchone()
    if not row or (target_id is not None and row['target_id'] != target_id):
        raise HTTPException(404, '예약을 찾을 수 없습니다.')
    return _serialize(row)


def latest(user_id, target_id):
    repository.get_or_create_target_report(user_id, target_id)
    init()
    with repository.connection() as db:
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE user_id=? AND target_id=? ORDER BY requested_at DESC, rowid DESC LIMIT 1', (user_id, target_id)).fetchone()
    return _serialize(row) if row else None


def acknowledge_uncertainty(user_id, target_id, job_id):
    """Record an explicit user choice, without sending or asserting delivery."""
    init()
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=? AND user_id=? AND target_id=?', (job_id, user_id, target_id)).fetchone()
        if not row:
            raise HTTPException(404, '요청을 찾을 수 없습니다.')
        if row['state'] in ('unknown', 'partial'):
            db.execute('UPDATE aura_clinic_delivery_queue SET state=?,updated_at=? WHERE id=?', ('acknowledged_' + row['state'], time.time(), job_id))
            row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=?', (job_id,)).fetchone()
        elif row['state'] not in ('acknowledged_unknown', 'acknowledged_partial'):
            raise HTTPException(409, '전송 진행 중이거나 확인 대상이 아닌 요청입니다.')
        db.commit()
        return _serialize(row)


def cancel(user_id, target_id, job_id):
    init()
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=? AND user_id=? AND target_id=?', (job_id, user_id, target_id)).fetchone()
        if not row:
            raise HTTPException(404, '예약을 찾을 수 없습니다.')
        if row['state'] == 'cancelled':
            db.commit()
            return _serialize(row)
        if row['state'] not in ('queued', 'generating', 'ready'):
            raise HTTPException(409, '전송이 시작됐거나 종료된 예약은 취소할 수 없습니다.')
        db.execute("UPDATE aura_clinic_delivery_queue SET state='cancelled',updated_at=?,error_code=NULL WHERE id=?", (time.time(), job_id))
        row = db.execute('SELECT * FROM aura_clinic_delivery_queue WHERE id=?', (job_id,)).fetchone()
        db.commit()
        return _serialize(row)


def recover():
    """Call only after obtaining the exclusive scheduler process lock."""
    init()
    with repository.connection() as db:
        db.execute("UPDATE aura_clinic_delivery_queue SET state='queued',error_code=NULL WHERE state='generating'")
        db.execute("UPDATE aura_clinic_delivery_queue SET state='unknown',error_code='restart_during_send' WHERE state='sending'")
        db.commit()


def _transition(job_id, old, new, now, error=None, next_attempt=None):
    with repository.connection() as db:
        changed = db.execute('UPDATE aura_clinic_delivery_queue SET state=?,updated_at=?,error_code=?,next_attempt=COALESCE(?,next_attempt) WHERE id=? AND state=?', (new, now, error, next_attempt, job_id, old)).rowcount
        db.commit()
    return bool(changed)


def _generate(user_id, target_id):
    report = repository.get_or_create_target_report(user_id, target_id)
    if report.get('generatedReportJson'):
        return
    generated = ai_report.generate(user_id, target_id)
    result = (generated.get('results') or [None])[0]
    if not result or not isinstance(result.get('output'), dict) or not result['output']:
        raise ValueError('missing generated output')
    # The database condition is atomic with the write, so user edits win.
    report_generation_store.save_if_missing(user_id, report['id'], result['output'], result.get('model'))


def _deliver(user_id, target_id):
    # Import lazily to share the existing PDF/attachment path without an import cycle.
    from .router import _target_report_pdf
    report = repository.get_or_create_target_report(user_id, target_id)
    if not report.get('generatedReportJson'):
        raise ValueError('generated report missing')

    job_id = None
    try:
        job = native_kakao.create_clinic_job(user_id, target_id, report)
        job_id = job['jobId']
        if job.get('deliveryFormat') != 'text':
            pdf = _target_report_pdf(user_id, target_id)
            pages = report_pdf.render_pages(pdf, max_pages=native_kakao.MAX_PAGES)
            for number, image in enumerate(pages, 1):
                native_kakao.store_page(job_id, user_id, target_id, number, 'image/jpeg', image)
        try:
            return native_kakao.send_clinic_job(job_id, user_id, target_id)
        except native_kakao.NativeKakaoError as error:
            if error.code not in ('send_in_progress', 'recipient_timeout', 'recipient_unverified', 'invalid_clinic_job') and error.delivery_status == 'not_started':
                error.delivery_status = 'unknown'
            raise
    finally:
        if job_id:
            native_kakao.discard_clinic_job(job_id, user_id, target_id)


def _complete_report(row, now):
    try:
        report = repository.get_or_create_target_report(row['user_id'], row['target_id'])
        repository.update_target_report(row['user_id'], report['id'], None, submit=True)
    except Exception as error:
        log.warning('clinic completion pending: %s', type(error).__name__)
        with repository.connection() as db:
            db.execute("UPDATE aura_clinic_delivery_queue SET next_attempt=? WHERE id=? AND state='sent' AND error_code='completion_pending'", (now + BUSY_DELAY, row['id']))
            db.commit()
        return
    with repository.connection() as db:
        db.execute("UPDATE aura_clinic_delivery_queue SET error_code=NULL,updated_at=? WHERE id=? AND state='sent' AND error_code='completion_pending'", (now, row['id']))
        db.commit()


def run_once(now=None):
    now = time.time() if now is None else now
    init()
    with repository.connection() as db:
        pending = db.execute("SELECT * FROM aura_clinic_delivery_queue WHERE state='sent' AND error_code='completion_pending' AND next_attempt<=? ORDER BY requested_at LIMIT 1", (now,)).fetchone()
    if pending:
        _complete_report(pending, now)
        return {'state': 'completion_pending', 'id': pending['id']}
    with repository.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("""SELECT q.* FROM aura_clinic_delivery_queue q
            WHERE (q.state='queued' OR (q.state='ready' AND q.send_after<=?
              AND NOT EXISTS (SELECT 1 FROM aura_clinic_delivery_queue older
                WHERE older.state='ready' AND older.send_after<=?
                  AND (older.requested_at<q.requested_at OR
                    (older.requested_at=q.requested_at AND older.rowid<q.rowid)))))
              AND q.next_attempt<=?
            ORDER BY q.requested_at, q.rowid LIMIT 1""", (now, now, now)).fetchone()
        if not row:
            db.commit()
            return {'state': 'waiting'}
        old = row['state']
        new = 'generating' if old == 'queued' else 'sending'
        changed = db.execute('UPDATE aura_clinic_delivery_queue SET state=?,updated_at=? WHERE id=? AND state=?', (new, now, row['id'], old)).rowcount
        db.commit()
    if not changed:
        return {'state': 'waiting'}
    try:
        if new == 'generating':
            _generate(row['user_id'], row['target_id'])
            state, code, retry = 'ready', None, None
        else:
            result = _deliver(row['user_id'], row['target_id'])
            state, code, retry = ('sent', 'completion_pending', now) if result.get('sent') is True and result.get('deliveryStatus') == 'verified' else ('unknown', 'delivery_unverified', None)
    except native_kakao.NativeKakaoError as error:
        if new == 'sending' and error.code == 'send_in_progress' and error.delivery_status == 'not_started':
            state, code, retry = 'ready', 'send_in_progress', now + BUSY_DELAY
        elif new == 'sending' and (error.delivery_status in ('unknown', 'partial') or error.code in ('delivery_unknown', 'delivery_unverified', 'partial_delivery')):
            state, code, retry = ('partial' if error.delivery_status == 'partial' or error.code == 'partial_delivery' else 'unknown'), error.code, None
        else:
            state, code, retry = 'failed', error.code, None
    except Exception as error:
        # A failure after entering the send path may have occurred after delivery.
        state = 'unknown' if new == 'sending' else 'failed'
        code, retry = ('send_exception' if new == 'sending' else 'generation_failed'), None
        log.warning('clinic scheduled delivery %s: %s', code, type(error).__name__)
    _transition(row['id'], new, state, now, code, retry)
    if state == 'sent':
        _complete_report(row, now)
    return {'state': state, 'id': row['id']}


def _loop():
    # The lock must live on the same filesystem as the shared SQLite database.
    from .db import DB_PATH
    lock_path = Path(str(DB_PATH) + '.clinic-delivery.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        while not _stop.is_set():
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                _stop.wait(10)
        else:
            return
        try:
            recover()
            while not _stop.is_set():
                try:
                    result = run_once()
                    if result['state'] != 'waiting':
                        continue
                except Exception as error:
                    log.error('clinic scheduler error: %s', type(error).__name__)
                _stop.wait(10)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def start():
    global _thread
    if os.getenv('DISABLE_KAKAO_BRIDGE') == '1':
        return
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_loop, name='clinic-delivery-scheduler', daemon=True)
        _thread.start()


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=2)


def build_router(owner_dependency, read_owner_dependency):
    router = APIRouter(prefix='/aura/targets/{target_id}/kakao-clinic/scheduled-deliveries')

    @router.post('')
    def schedule(target_id: int, body: ScheduleRequest | None = None, user_id: int = Depends(owner_dependency)):
        return enqueue(user_id, target_id, request=body)

    @router.get('')
    def get_latest(target_id: int, user_id: int = Depends(read_owner_dependency)):
        return latest(user_id, target_id)

    @router.get('/{job_id}')
    def get_job(target_id: int, job_id: str, user_id: int = Depends(read_owner_dependency)):
        return get(user_id, job_id, target_id)

    @router.post('/{job_id}/acknowledge-uncertainty')
    def acknowledge_job(target_id: int, job_id: str, user_id: int = Depends(owner_dependency)):
        return acknowledge_uncertainty(user_id, target_id, job_id)

    router.add_event_handler('startup', start)
    router.add_event_handler('shutdown', stop)
    @router.delete('/{job_id}')
    def cancel_job(target_id: int, job_id: str, user_id: int = Depends(owner_dependency)):
        return cancel(user_id, target_id, job_id)

    return router
