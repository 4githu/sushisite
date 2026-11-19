import json
import logging
import subprocess
from types import SimpleNamespace

import pytest

from personal_project import kakao_bridge


def test_send_success_log_correlates_stage_without_message_content(monkeypatch, caplog):
    monkeypatch.setattr(kakao_bridge, 'BINARY', SimpleNamespace(is_file=lambda: True, __str__=lambda: '/fake'))
    monkeypatch.setattr(kakao_bridge.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'sent': True})))
    with caplog.at_level(logging.INFO, logger=kakao_bridge.__name__):
        kakao_bridge.invoke('send', operation_id='synthetic-job', room='private-room', text='private-message', files=[])
    text = caplog.text
    assert 'operation=synthetic-job' in text
    assert 'stage=text' in text
    assert 'outcome=ok' in text
    assert 'private-room' not in text and 'private-message' not in text


@pytest.mark.parametrize('failure', ['timeout', 'invalid_response'])
def test_failed_image_trace_preserves_correlation_without_payload(monkeypatch, caplog, failure):
    monkeypatch.setattr(kakao_bridge, 'BINARY', SimpleNamespace(is_file=lambda: True, __str__=lambda: '/fake'))
    def run(*args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired('fake', 55)
        return SimpleNamespace(stdout='private-invalid-response')
    monkeypatch.setattr(kakao_bridge.subprocess, 'run', run)
    with caplog.at_level(logging.ERROR, logger=kakao_bridge.__name__), pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        kakao_bridge.invoke('send', operation_id='synthetic-job', room='private-room', files=['private-path'])
    assert 'operation=synthetic-job' in caplog.text
    assert 'stage=image' in caplog.text
    assert f'outcome={failure}' in caplog.text
    assert 'private-room' not in caplog.text and 'private-path' not in caplog.text and 'private-invalid-response' not in caplog.text
