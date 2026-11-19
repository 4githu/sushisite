"""Guarded, Mac-local KakaoTalk self-chat photo-bundle jobs.

The destination is deliberately not part of this module's public API.  The UI
worker independently verifies the hard-coded self-chat before every send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4


OWNER_EMAIL = "sushj27@gmail.com"
SELF_CHAT_TITLE = "본계정"
MAX_PAGES = 30
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = MAX_PAGE_BYTES * MAX_PAGES
JOB_TTL_SECONDS = 10 * 60
SEND_COOLDOWN_SECONDS = 15
WORKER_TIMEOUT_SECONDS = 180
WORKER_SCRIPT = Path(__file__).resolve().parents[3] / "kakao_photo_bundle_test.py"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _matches_image_signature(content_type: str, payload: bytes) -> bool:
    if content_type == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    return False


class NativeKakaoError(Exception):
    def __init__(self, status_code: int, message: str, code: str, *,
                 target_room: str | None = None, selected_room: str | None = None,
                 fallback_reason: str | None = None, delivery_status: str = "not_started"):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.target_room = target_room
        self.selected_room = selected_room
        self.fallback_reason = fallback_reason
        self.delivery_status = delivery_status
        self.delivery_result: dict = {}


@dataclass
class BundleJob:
    id: str
    user_id: int
    target_id: int
    directory: Path
    created_at: float
    pages: dict[int, Path] = field(default_factory=dict)
    total_bytes: int = 0
    state: str = "uploading"
    destination: str = SELF_CHAT_TITLE
    clinic: bool = False
    target_room: str | None = None
    fallback_reason: str | None = None
    fallback_text: str | None = None


_jobs: dict[str, BundleJob] = {}
_jobs_lock = threading.RLock()
# Share one UI transaction lock across every backend worker process.
from .db import DB_PATH
from .kakao_process_lock import KakaoProcessLock
_send_lock = KakaoProcessLock(str(DB_PATH) + '.kakao-ui.lock')
_last_sent_at: dict[int, float] = {}
_active_operation = ""


def _send_in_progress_error() -> NativeKakaoError:
    operation = _active_operation or "카카오톡 화면 작업"
    return NativeKakaoError(
        409,
        f"다른 카카오톡 작업({operation})이 진행 중입니다. 해당 작업이 끝난 뒤 다시 시도해주세요.",
        "send_in_progress",
    )


def _remove_job(job: BundleJob) -> None:
    _jobs.pop(job.id, None)
    shutil.rmtree(job.directory, ignore_errors=True)


def discard_clinic_job(job_id: str, user_id: int, target_id: int) -> None:
    """Drop an owned clinic job when report assembly fails before sending."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job.clinic and job.user_id == user_id and job.target_id == target_id:
            _remove_job(job)


def _cleanup_expired(now: float | None = None) -> None:
    current = now or time.monotonic()
    for job in list(_jobs.values()):
        if job.state != "sending" and current - job.created_at > JOB_TTL_SECONDS:
            _remove_job(job)


def status() -> dict:
    return {
        "enabled": sys.platform == "darwin" and WORKER_SCRIPT.is_file(),
        "destination": "나와의 채팅",
        "maxPages": MAX_PAGES,
    }


def preflight() -> dict:
    global _active_operation
    if not _send_lock.acquire(blocking=False):
        raise _send_in_progress_error()
    _active_operation = "자기채팅 사전 확인"
    try:
        return _preflight_locked()
    finally:
        _active_operation = ""
        _send_lock.release()


def _preflight_locked() -> dict:
    if sys.platform != "darwin" or not WORKER_SCRIPT.is_file():
        raise NativeKakaoError(503, "Mac용 카카오 전송 도우미를 사용할 수 없습니다.", "worker_unavailable")
    try:
        completed = subprocess.run(
            [sys.executable, str(WORKER_SCRIPT), "--verify-self-chat", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NativeKakaoError(504, "카카오톡 자기채팅 확인 시간이 초과되었습니다.", "preflight_timeout") from exc
    message = _result_message(completed.stdout)
    if completed.returncode != 0:
        if completed.returncode == 20:
            raise NativeKakaoError(
                503,
                "macOS가 sushisite 백엔드의 화면 제어를 차단했습니다. 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용에서 sushi-fast/.venv/bin/python을 허용한 뒤 백엔드를 다시 시작해주세요.",
                "backend_accessibility_missing",
            )
        raise NativeKakaoError(
            409,
            "Mac mini에서 카카오톡 ‘본계정’ 채팅 창을 열어둔 뒤 다시 눌러주세요. " + message,
            "self_chat_not_ready",
        )
    return {"ready": True, "destination": "나와의 채팅"}


def create_job(user_id: int, target_id: int) -> dict:
    with _jobs_lock:
        _cleanup_expired()
        # Each report preparation must retain its own uploaded pages. Removing
        # another job here races with concurrent preparation by the same user.
        directory = Path(tempfile.mkdtemp(prefix="sushisite-kakao-self-"))
        directory.chmod(0o700)
        job = BundleJob(
            id=uuid4().hex,
            user_id=user_id,
            target_id=target_id,
            directory=directory,
            created_at=time.monotonic(),
        )
        _jobs[job.id] = job
    return {
        "jobId": job.id,
        "maxPages": MAX_PAGES,
        "maxPageBytes": MAX_PAGE_BYTES,
    }


def _owned_job(job_id: str, user_id: int, target_id: int) -> BundleJob:
    with _jobs_lock:
        _cleanup_expired()
        job = _jobs.get(job_id)
        if not job or job.user_id != user_id or job.target_id != target_id:
            raise NativeKakaoError(404, "카카오 전송 작업을 찾을 수 없습니다.", "job_not_found")
        return job


def store_page(
    job_id: str,
    user_id: int,
    target_id: int,
    page_number: int,
    content_type: str,
    payload: bytes,
) -> dict:
    if page_number < 1 or page_number > MAX_PAGES:
        raise NativeKakaoError(400, f"리포트 이미지는 최대 {MAX_PAGES}장까지 보낼 수 있습니다.", "page_limit")
    normalized_type = content_type.lower().split(";", 1)[0].strip()
    suffix = ALLOWED_IMAGE_TYPES.get(normalized_type)
    if not suffix:
        raise NativeKakaoError(415, "JPG, PNG, WebP 이미지만 전송할 수 있습니다.", "unsupported_image")
    if not payload or len(payload) > MAX_PAGE_BYTES:
        raise NativeKakaoError(413, "리포트 이미지 한 장은 8MB 이하여야 합니다.", "page_too_large")
    if not _matches_image_signature(normalized_type, payload):
        raise NativeKakaoError(415, "파일 내용이 선언된 이미지 형식과 일치하지 않습니다.", "invalid_image")
    job = _owned_job(job_id, user_id, target_id)
    with _jobs_lock:
        if job.state != "uploading":
            raise NativeKakaoError(409, "이미 전송 중이거나 완료된 작업입니다.", "job_not_uploading")
        previous = job.pages.get(page_number)
        previous_size = previous.stat().st_size if previous and previous.is_file() else 0
        next_total = job.total_bytes - previous_size + len(payload)
        if next_total > MAX_TOTAL_BYTES:
            raise NativeKakaoError(
                413,
                f"리포트 이미지 전체 용량은 {MAX_TOTAL_BYTES // (1024 * 1024)}MB 이하여야 합니다.",
                "bundle_too_large",
            )
        if previous:
            previous.unlink(missing_ok=True)
        path = job.directory / f"clinic-report-{page_number:02d}{suffix}"
        path.write_bytes(payload)
        path.chmod(0o600)
        job.pages[page_number] = path
        job.total_bytes = next_total
    return {"stored": True, "page": page_number, "byteSize": len(payload)}


def _result_message(stdout: str) -> str:
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return "카카오 자동화 도우미의 결과를 해석하지 못했습니다."
    message = result.get("message")
    return message if isinstance(message, str) and message else "카카오 자동화가 완료 증거를 반환하지 않았습니다."


def send_job(job_id: str, user_id: int, target_id: int) -> dict:
    global _active_operation
    job = _owned_job(job_id, user_id, target_id)
    with _jobs_lock:
        page_numbers = sorted(job.pages)
        if not page_numbers or page_numbers != list(range(1, len(page_numbers) + 1)):
            raise NativeKakaoError(400, "리포트 이미지가 1번부터 빠짐없이 업로드되어야 합니다.", "incomplete_pages")
        if job.state != "uploading":
            raise NativeKakaoError(409, "이미 전송 중이거나 완료된 작업입니다.", "job_not_uploading")
        since_last = time.monotonic() - _last_sent_at.get(user_id, 0)
        if since_last < SEND_COOLDOWN_SECONDS:
            wait_seconds = max(1, int(SEND_COOLDOWN_SECONDS - since_last + 0.999))
            raise NativeKakaoError(429, f"중복 전송 방지를 위해 {wait_seconds}초 후 다시 시도해주세요.", "send_cooldown")
        if not _send_lock.acquire(blocking=False):
            raise _send_in_progress_error()
        _active_operation = "나와의 채팅 사진 전송"
        job.state = "sending"

    try:
        if sys.platform != "darwin" or not WORKER_SCRIPT.is_file():
            raise NativeKakaoError(503, "Mac용 카카오 전송 도우미를 사용할 수 없습니다.", "worker_unavailable")
        command = [sys.executable, str(WORKER_SCRIPT), "--send", "--quiet"]
        command.extend(str(job.pages[number]) for number in page_numbers)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=WORKER_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise NativeKakaoError(504, "카카오톡 화면 응답을 기다리다 시간이 초과되었습니다.", "worker_timeout") from exc
        message = _result_message(completed.stdout)
        if completed.returncode != 0:
            raise NativeKakaoError(409, message, "delivery_not_verified")
        if "Delivery verified" not in message:
            raise NativeKakaoError(409, message, "delivery_not_verified")
        with _jobs_lock:
            job.state = "sent"
            _last_sent_at[user_id] = time.monotonic()
        return {
            "sent": True,
            "sentCount": len(page_numbers),
            "destination": "나와의 채팅",
            "evidence": message,
        }
    finally:
        _active_operation = ""
        _send_lock.release()
        with _jobs_lock:
            _remove_job(job)


def _clinic_fallback_text(report: dict, target: str) -> str:
    """User authorized student report text to the configured own room, 2026-11-11."""
    generated=report.get('generatedReportJson') or {}
    learning=generated.get('learningContent') or {}
    lines=['[아우라 리포트 · 본계정 대체 수신]',f"대상: {target}",
           '클리닉·관리방을 찾지 못해 본계정으로 전달합니다. 학생 방에는 발송되지 않았습니다.',
           str(report.get('roundLabel') or '')]
    for key,title in [('startTime','시작'),('endTime','종료'),('lectureProgress','강의수강도'),('lectureComprehension','강의이해도'),('memoryBefore','클리닉 전 암기'),('memoryAfter','클리닉 후 암기')]:
        if report.get(key) is not None:lines.append(f'{title}: {report[key]}')
    assessment=generated.get('assessment') or report.get('assessmentJson') or {}
    for item in assessment.get('items') or []:
        if isinstance(item,dict):lines.append(f"{item.get('name','')}: {item.get('score','')}")
    lines.extend(str(p) for p in (learning.get('paragraphs') or [learning.get('text') or '']) if str(p).strip())
    if generated.get('problemSolvingNote'):lines.append(str(generated['problemSolvingNote']))
    def visible(node):
        if isinstance(node,dict):
            if isinstance(node.get('text'),str):return node['text']
            return '\n'.join(filter(None,(visible(v) for k,v in node.items() if k in ('children','blocks','content'))))
        if isinstance(node,list):return '\n'.join(filter(None,map(visible,node)))
        return ''
    content=visible(report.get('contentJson'))
    if content:lines.append(content)
    return '\n'.join(line for line in lines if line.strip())


def create_clinic_job(user_id: int, target_id: int, report: dict) -> dict:
    global _active_operation
    from .kakao_bridge import invoke
    school=' '.join(report['schoolName'].split())
    student=' '.join(report['studentName'].split())
    if not school or not student:
        raise NativeKakaoError(400,'학교와 학생 이름이 필요합니다.','missing_recipient')
    candidates=[f'{school} {student} 생명클리닉',f'{school} {student} 생명관리방']
    target=candidates[0]
    destination=None
    reason=None
    if not _send_lock.acquire(blocking=False):
        raise _send_in_progress_error()
    _active_operation = "클리닉 채팅방 확인"
    try:
        for room in candidates:
            try:
                result=invoke('search',room=room,redact_errors=True)
            except subprocess.TimeoutExpired as error:
                raise NativeKakaoError(504,'Mac 화면 응답이 시간 초과됐습니다. 대체 수신자로 보내지 않습니다.','recipient_timeout',target_room=target,fallback_reason=reason) from error
            if result.get('opened') is True and result.get('room')==room and result.get('searchEvidence')=='unique_exact':
                destination=room
                break
            if result.get('found') is False and result.get('room')==room and result.get('searchEvidence')=='confirmed_absent':
                reason='primary_confirmed_absent' if room==target else 'both_rooms_confirmed_absent'
                continue
            raise NativeKakaoError(409,result.get('error','채팅방 확인 실패'),'recipient_unverified',target_room=target,fallback_reason=reason)
        if destination is None:
            try:
                self_result=invoke('search',room=SELF_CHAT_TITLE,redact_errors=True)
            except subprocess.TimeoutExpired as error:
                raise NativeKakaoError(504,'본계정 채팅방 확인 시간이 초과되어 전송하지 않았습니다.','fallback_identity_unverified',target_room=target,fallback_reason=reason) from error
            if not (self_result.get('opened') is True and self_result.get('room')==SELF_CHAT_TITLE and self_result.get('searchEvidence')=='unique_exact'):
                raise NativeKakaoError(409,'설정된 본계정 방을 찾지 못했습니다.','self_room_not_found',target_room=target,fallback_reason=reason)
            destination=SELF_CHAT_TITLE
    finally:
        _active_operation = ""
        _send_lock.release()
    result=create_job(user_id,target_id)
    with _jobs_lock:
        job=_jobs[result['jobId']]
        job.destination=destination
        job.clinic=True
        job.target_room=target
        job.fallback_reason=reason
        if reason == 'both_rooms_confirmed_absent':
            job.fallback_text = f'[아우라 리포트 대체 전송] 원래 수신 대상: {target}\n클리닉·관리방을 찾지 못해 본계정으로 리포트 이미지를 전달합니다. 학생 방에는 발송되지 않았습니다.'
    return {**result,'deliveryFormat':'images','destination':destination,'targetRoom':target,'selectedRoom':destination,'fallbackReason':reason,'deliveryStatus':'not_started','maxPages':MAX_PAGES}

def send_clinic_job(job_id: str, user_id: int, target_id: int) -> dict:
    global _active_operation
    from .kakao_bridge import invoke
    job=_owned_job(job_id,user_id,target_id)
    stages = {'recipient': 'not_started', 'images': 'not_started', 'text': 'not_started'}
    sent_count = 0
    with _jobs_lock:
        pages=sorted(job.pages)
        if not job.clinic or job.state!='uploading' or not pages or pages!=list(range(1,len(pages)+1)) or len(pages)>MAX_PAGES:
            raise NativeKakaoError(409,'전송할 리포트 묶음을 확인해주세요.','invalid_clinic_job')
        if not _send_lock.acquire(blocking=False):raise _send_in_progress_error()
        _active_operation = "클리닉 리포트 이미지와 안내문 전송"
        job.state='sending'
    try:
        try:
            opened=invoke('search',room=job.destination,operation_id=job_id,redact_errors=True)
        except subprocess.TimeoutExpired as error:
            raise NativeKakaoError(504,'카카오톡 채팅방 확인이 시간 초과됐습니다. 전송은 시작되지 않았습니다. Mac 잠금과 카카오톡 상태를 확인해주세요.','recipient_timeout') from error
        if not (opened.get('opened') is True and opened.get('room')==job.destination and opened.get('searchEvidence')=='unique_exact'):
            raise NativeKakaoError(409,opened.get('error','받는 방 재확인 실패'),'recipient_unverified')
        stages['recipient'] = 'verified'
        if job.fallback_text is not None:
            stages['text'] = 'unknown'
            try:
                text_result = invoke('send', room=job.destination, operation_id=job_id, text=job.fallback_text, files=[], keepRoomOpen=True, redact_errors=True)
            except Exception as error:
                raise NativeKakaoError(409,'대체 전송 안내문을 확인하지 못했습니다.','delivery_unknown') from error
            if not isinstance(text_result, dict) or text_result.get('sent') is not True:
                raise NativeKakaoError(409,'대체 전송 안내문을 확인하지 못했습니다.','delivery_unknown')
            stages['text'] = 'verified'
        stages['images'] = 'unknown'
        try:
            images=invoke(
                'send', room=job.destination, operation_id=job_id, text='',
                files=[str(job.pages[number]) for number in pages], keepRoomOpen=job.fallback_text is None, redact_errors=True,
            )
        except subprocess.TimeoutExpired as error:
            detail='카카오톡 이미지 묶음 전송 확인이 시간 초과됐습니다. 전송 여부가 불명확하니 대화방을 확인하고 자동 재전송하지 마세요.'
            raise NativeKakaoError(504,detail,'delivery_unknown') from error
        except Exception as error:
            raise NativeKakaoError(409,'이미지 전송 응답을 확인하지 못했습니다. 전송 여부가 불명확하니 대화방을 확인하고 재전송하지 마세요.','delivery_unknown') from error
        if not isinstance(images, dict):
            raise NativeKakaoError(409,'이미지 전송 응답을 확인하지 못했습니다. 전송 여부가 불명확하니 대화방을 확인하고 재전송하지 마세요.','delivery_unknown')
        if images.get('sent') is not True:
            detail=images.get('error','카카오톡 이미지 전송 확인 실패. 대화방을 확인해주세요.')
            if images.get('uncertain'):
                detail+=' 전송이 일부 진행됐을 수 있으니 대화방을 확인하고 자동 재전송하지 마세요.'
            raise NativeKakaoError(409,detail,'delivery_unverified')
        sent_count=len(pages)
        stages['images'] = 'verified'
        if job.fallback_text is not None:
            return {'sent':True,'sentCount':len(pages),'deliveryFormat':'images','destination':job.destination,'targetRoom':job.target_room,'selectedRoom':job.destination,'fallbackReason':job.fallback_reason,'deliveryStatus':'verified','stages':stages}
        stages['text'] = 'unknown'
        try:
            note=invoke('send',room=job.destination,operation_id=job_id,text=job.fallback_text or '저번 클리닉 리포트입니다',files=[],redact_errors=True)
        except subprocess.TimeoutExpired as error:
            raise NativeKakaoError(504,f'이미지 {sent_count}장은 전송 확인됐지만 안내문 전송 확인이 시간 초과됐습니다. 대화방을 확인해주세요.','partial_delivery') from error
        except Exception as error:
            # The image is already confirmed; a broken bridge response cannot
            # make the overall operation a fresh, safe-to-retry send.
            raise NativeKakaoError(409,'이미지는 전송됐지만 안내문 전송을 확인하지 못했습니다. 대화방을 확인해주세요.','partial_delivery') from error
        if not isinstance(note, dict) or note.get('sent') is not True:raise NativeKakaoError(409,'이미지는 전송됐지만 안내문 전송을 확인하지 못했습니다. 대화방을 확인해주세요.','partial_delivery')
        stages['text'] = 'verified'
        return {'sent':True,'sentCount':len(pages),'deliveryFormat':'images','destination':job.destination,'targetRoom':job.target_room,'selectedRoom':job.destination,'fallbackReason':job.fallback_reason,'deliveryStatus':'verified','stages':stages}
    except NativeKakaoError as error:
        error.target_room=job.target_room
        error.selected_room=job.destination
        error.fallback_reason=job.fallback_reason
        if job.fallback_text is not None and stages['text'] == 'verified' and stages['images'] != 'verified':
            error.code = 'partial_delivery'
        error.delivery_status=('partial' if error.code=='partial_delivery' else
                               'unknown' if error.code in ('delivery_unknown','delivery_unverified') else 'not_started')
        error.delivery_result = {'deliveryFormat': 'images',
                                 'sentCount': sent_count, 'stages': stages,
                                 'targetRoom': job.target_room, 'fallbackReason': job.fallback_reason}
        if stages['recipient'] == 'verified':
            error.delivery_result.update(destination=job.destination, selectedRoom=job.destination)
        raise
    finally:
        _active_operation = ""
        _send_lock.release()
        with _jobs_lock:_remove_job(job)
