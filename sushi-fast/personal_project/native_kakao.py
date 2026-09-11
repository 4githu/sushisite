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
SELF_CHAT_TITLE = "김지후"
MAX_PAGES = 12
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
JOB_TTL_SECONDS = 10 * 60
SEND_COOLDOWN_SECONDS = 15
WORKER_TIMEOUT_SECONDS = 90
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
    def __init__(self, status_code: int, message: str, code: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code


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


_jobs: dict[str, BundleJob] = {}
_jobs_lock = threading.RLock()
_send_lock = threading.Lock()
_last_sent_at: dict[int, float] = {}


def _remove_job(job: BundleJob) -> None:
    _jobs.pop(job.id, None)
    shutil.rmtree(job.directory, ignore_errors=True)


def _cleanup_expired(now: float | None = None) -> None:
    current = now or time.monotonic()
    for job in list(_jobs.values()):
        if current - job.created_at > JOB_TTL_SECONDS:
            _remove_job(job)


def status() -> dict:
    return {
        "enabled": sys.platform == "darwin" and WORKER_SCRIPT.is_file(),
        "destination": "나와의 채팅",
        "maxPages": MAX_PAGES,
    }


def preflight() -> dict:
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
            "Mac mini에서 카카오톡 ‘김지후’ 나와의 채팅 창을 열어둔 뒤 다시 눌러주세요. " + message,
            "self_chat_not_ready",
        )
    return {"ready": True, "destination": "나와의 채팅"}


def create_job(user_id: int, target_id: int) -> dict:
    with _jobs_lock:
        _cleanup_expired()
        for existing in list(_jobs.values()):
            if existing.user_id == user_id and existing.state != "sending":
                _remove_job(existing)
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
            raise NativeKakaoError(413, "리포트 이미지 전체 용량은 32MB 이하여야 합니다.", "bundle_too_large")
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
            raise NativeKakaoError(409, "다른 카카오 전송이 진행 중입니다.", "send_in_progress")
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
        _send_lock.release()
        with _jobs_lock:
            _remove_job(job)
