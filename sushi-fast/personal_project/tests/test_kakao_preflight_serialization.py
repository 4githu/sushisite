"""The legacy self-chat preflight must share the Kakao UI transaction lock."""
import pytest
from personal_project import native_kakao


def test_preflight_does_not_touch_ui_while_another_operation_owns_lock(monkeypatch, tmp_path):
    script = tmp_path / 'worker.py'
    script.write_text('')
    monkeypatch.setattr(native_kakao, 'WORKER_SCRIPT', script)
    monkeypatch.setattr(native_kakao.sys, 'platform', 'darwin')
    calls = []
    monkeypatch.setattr(native_kakao.subprocess, 'run', lambda *a, **k: calls.append(a))
    assert native_kakao._send_lock.acquire(blocking=False)
    try:
        with pytest.raises(native_kakao.NativeKakaoError) as error:
            native_kakao.preflight()
        assert error.value.code == 'send_in_progress'
        assert calls == []
    finally:
        native_kakao._send_lock.release()


def test_expired_cleanup_does_not_delete_an_active_send(monkeypatch, tmp_path):
    folder = tmp_path / 'active'
    folder.mkdir()
    page = folder / 'page.jpg'
    page.write_bytes(b'synthetic')
    job = native_kakao.BundleJob('synthetic-active', 1, 2, folder, 1, state='sending')
    job.pages[1] = page
    monkeypatch.setattr(native_kakao, '_jobs', {job.id: job})
    native_kakao._cleanup_expired(now=native_kakao.JOB_TTL_SECONDS + 2)
    assert job.id in native_kakao._jobs
    assert page.exists()
