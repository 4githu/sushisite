from pathlib import Path
import subprocess

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from personal_project import native_kakao
from personal_project import router as personal_router


def request_with_origin(origin: str = "https://aura.chobab.app") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"origin", origin.encode())],
        }
    )


@pytest.fixture(autouse=True)
def clear_native_jobs():
    with native_kakao._jobs_lock:
        for job in list(native_kakao._jobs.values()):
            native_kakao._remove_job(job)
        native_kakao._last_sent_at.clear()
    yield
    with native_kakao._jobs_lock:
        for job in list(native_kakao._jobs.values()):
            native_kakao._remove_job(job)
        native_kakao._last_sent_at.clear()


def test_native_kakao_account_is_server_locked(monkeypatch):
    monkeypatch.setattr(
        personal_router.JMT,
        "check_jwt",
        lambda _request, _key: {"data": {"id": 7, "email": "someone@example.com"}},
    )
    with pytest.raises(HTTPException) as error:
        personal_router.native_kakao_user_id(request_with_origin())
    assert error.value.status_code == 403

    monkeypatch.setattr(
        personal_router.JMT,
        "check_jwt",
        lambda _request, _key: {"data": {"id": 3, "email": " SUSHJ27@GMAIL.COM "}},
    )
    assert personal_router.native_kakao_user_id(request_with_origin()) == 3


def test_native_kakao_mutations_reject_foreign_origin():
    with pytest.raises(HTTPException) as error:
        personal_router.require_native_kakao_origin(request_with_origin("https://attacker.example"))
    assert error.value.status_code == 403
    personal_router.require_native_kakao_origin(request_with_origin())


def test_job_is_bound_to_user_and_report_and_validates_image_content():
    created = native_kakao.create_job(user_id=3, target_id=50)
    job_id = created["jobId"]
    jpeg = b"\xff\xd8\xff" + b"report-page"

    with pytest.raises(native_kakao.NativeKakaoError) as wrong_target:
        native_kakao.store_page(job_id, 3, 51, 1, "image/jpeg", jpeg)
    assert wrong_target.value.code == "job_not_found"

    with pytest.raises(native_kakao.NativeKakaoError) as wrong_content:
        native_kakao.store_page(job_id, 3, 50, 1, "image/jpeg", b"not-an-image")
    assert wrong_content.value.code == "invalid_image"

    stored = native_kakao.store_page(job_id, 3, 50, 1, "image/jpeg", jpeg)
    assert stored == {"stored": True, "page": 1, "byteSize": len(jpeg)}
    job = native_kakao._jobs[job_id]
    assert job.pages[1].name == "clinic-report-01.jpg"
    assert job.pages[1].parent == job.directory


def test_send_invokes_worker_without_any_destination_argument(monkeypatch):
    created = native_kakao.create_job(user_id=3, target_id=50)
    job_id = created["jobId"]
    native_kakao.store_page(job_id, 3, 50, 1, "image/jpeg", b"\xff\xd8\xffpage")
    observed: dict[str, list[str]] = {}

    def fake_run(command, **_kwargs):
        observed["command"] = command
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"message":"Delivery verified in the target chat: 사진을 보냈습니다."}',
            stderr="",
        )

    monkeypatch.setattr(native_kakao.subprocess, "run", fake_run)
    result = native_kakao.send_job(job_id, 3, 50)

    assert result["sent"] is True
    assert result["destination"] == "나와의 채팅"
    assert observed["command"][2:4] == ["--send", "--quiet"]
    assert "김지후" not in observed["command"]
    assert all("chat" not in argument.lower() for argument in observed["command"][4:])
    assert not Path(observed["command"][4]).exists()


def test_send_requires_contiguous_pages():
    created = native_kakao.create_job(user_id=3, target_id=50)
    job_id = created["jobId"]
    native_kakao.store_page(job_id, 3, 50, 2, "image/png", b"\x89PNG\r\n\x1a\npage")
    with pytest.raises(native_kakao.NativeKakaoError) as error:
        native_kakao.send_job(job_id, 3, 50)
    assert error.value.code == "incomplete_pages"


def test_preflight_distinguishes_backend_accessibility_failure(monkeypatch):
    monkeypatch.setattr(
        native_kakao.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            20,
            stdout='{"message":"Accessibility permission is missing."}',
            stderr="",
        ),
    )
    with pytest.raises(native_kakao.NativeKakaoError) as error:
        native_kakao.preflight()
    assert error.value.status_code == 503
    assert error.value.code == "backend_accessibility_missing"
