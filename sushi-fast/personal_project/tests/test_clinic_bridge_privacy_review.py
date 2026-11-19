"""Clinic bridge errors may include UI content; logs must not contain it."""
import json
from types import SimpleNamespace

import pytest
from personal_project import kakao_bridge, native_kakao


@pytest.mark.parametrize('failure_stage', ['search', 'image', 'note', 'fallback'])
def test_clinic_bridge_error_details_are_redacted(monkeypatch, tmp_path, caplog, failure_stage):
    binary = tmp_path / 'bridge'
    binary.write_text('synthetic')
    monkeypatch.setattr(kakao_bridge, 'BINARY', binary)
    monkeypatch.setattr(kakao_bridge, '_notify_failure', lambda *args, **kwargs: None)
    calls = []
    def run(*args, **kwargs):
        request = json.loads(kwargs['input'])
        calls.append(request['command'])
        if failure_stage == 'search' or (request['command'] == 'send' and (
            failure_stage in ('image', 'fallback') or calls.count('send') == 2
        )):
            payload = {'error': 'synthetic private student detail', 'errorCode': 'bridge_error'}
        elif request['command'] == 'search':
            absent = failure_stage == 'fallback' and request['room'] != native_kakao.SELF_CHAT_TITLE
            payload = {'room': request['room'], 'found': False, 'searchEvidence': 'confirmed_absent'} if absent else {
                'room': request['room'], 'opened': True, 'searchEvidence': 'unique_exact'}
        else:
            payload = {'sent': True}
        return SimpleNamespace(stdout=json.dumps(payload))
    monkeypatch.setattr(kakao_bridge.subprocess, 'run', run)
    report = {'schoolName': '합성학교', 'studentName': '합성학생'}
    with pytest.raises(native_kakao.NativeKakaoError):
        job = native_kakao.create_clinic_job(1, 2, report)
        native_kakao.store_page(job['jobId'], 1, 2, 1, 'image/png', b'\x89PNG\r\n\x1a\nsynthetic')
        native_kakao.send_clinic_job(job['jobId'], 1, 2)
    assert 'outcome=error' in caplog.text
    assert 'synthetic private student detail' not in caplog.text
    assert '합성학생' not in caplog.text
