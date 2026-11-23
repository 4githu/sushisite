import json
import os
import stat

import pytest
from fastapi.testclient import TestClient

from personal_project import router
from personal_project.reader_translation.personal_local import create_app


@pytest.fixture
def local_app(tmp_path):
    home = tmp_path / 'personal-profile'
    home.mkdir()
    exe = tmp_path / 'fake-hermes'
    exe.write_text('#!/usr/bin/python3\nimport sys, json\np=json.load(sys.stdin)\nprint(json.dumps({"translations":[{"id":s["id"], "text":"translated"} for s in p["segments"]]}))\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    app = create_app(owner_id=71, executable=str(exe), profile_home=str(home))
    app.dependency_overrides[router.current_user_id] = lambda: 71
    return app


def test_local_http_calls_personal_profile_only_for_owner(local_app):
    client = TestClient(local_app, client=('127.0.0.1', 12345), base_url='http://127.0.0.1')
    payload = {'segments': [{'id': 's1', 'text': 'synthetic'}], 'target_language': 'Korean'}
    response = client.post('/api/personal/reader/translate', json=payload)
    assert response.status_code == 200
    assert response.json() == {'translations': [{'id': 's1', 'text': 'translated'}]}
    assert response.headers['cache-control'].startswith('no-store')
    local_app.dependency_overrides[router.current_user_id] = lambda: 72
    assert client.post('/api/personal/reader/translate', json=payload).status_code == 403


def test_opt_in_browser_origin_is_exact_and_local(tmp_path):
    home = tmp_path / 'profile'
    home.mkdir()
    exe = tmp_path / 'fake-hermes'
    exe.write_text('#!/usr/bin/python3\nimport sys,json\np=json.load(sys.stdin)\nprint(json.dumps({"translations":[{"id":p["segments"][0]["id"],"text":"ok"}]}))')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(ValueError):
        create_app(owner_id=71, executable=str(exe), profile_home=str(home), reader_origin='https://evil.example')
    app = create_app(owner_id=71, executable=str(exe), profile_home=str(home), reader_origin='http://127.0.0.1:5173')
    app.dependency_overrides[router.current_user_id] = lambda: 71
    client = TestClient(app, client=('127.0.0.1', 1234), base_url='http://127.0.0.1:9011')
    preflight = client.options('/api/personal/reader/translate', headers={'origin': 'http://127.0.0.1:5173', 'access-control-request-method': 'POST', 'access-control-request-headers': 'content-type'})
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == 'http://127.0.0.1:5173'
    result = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]}, headers={'origin': 'http://127.0.0.1:5173'})
    assert result.status_code == 200
    assert result.headers['access-control-allow-credentials'] == 'true'
    assert client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]}, headers={'origin': 'http://localhost:5174'}).status_code == 403


def test_rejects_remote_and_forwarded_requests(local_app):
    payload = {'segments': [{'id': 's1', 'text': 'synthetic'}]}
    remote = TestClient(local_app, client=('192.0.2.1', 1234), base_url='http://127.0.0.1')
    assert remote.post('/api/personal/reader/translate', json=payload).status_code == 403
    local = TestClient(local_app, client=('127.0.0.1', 1234), base_url='http://127.0.0.1')
    assert local.post('/api/personal/reader/translate', json=payload, headers={'x-forwarded-for': '192.0.2.1'}).status_code == 403
    assert local.post('/api/personal/reader/translate', json=payload, headers={'origin': 'https://evil.example'}).status_code == 403
    assert local.post('/api/personal/reader/translate', content=json.dumps(payload), headers={'content-type': 'text/plain'}).status_code == 415


def test_personal_provider_errors_are_sanitized(local_app, tmp_path):
    local = TestClient(local_app, client=('127.0.0.1', 1234), base_url='http://127.0.0.1')
    executable = tmp_path / 'fake-hermes'
    executable.write_text('#!/bin/sh\nprintf "secret-looking-error" >&2\nexit 1\n')
    response = local.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'SYNTH_PRIVATE'}]})
    assert response.status_code == 502
    assert 'SYNTH_PRIVATE' not in response.text
    assert 'secret-looking-error' not in response.text


def test_requires_real_mainauth_when_not_overridden(local_app, monkeypatch):
    local_app.dependency_overrides.clear()
    monkeypatch.setattr(router.JMT, 'SECRET_KEY', 'synthetic-only-test-secret')
    monkeypatch.setattr(router.JMT, 'ALGORITHM', 'HS256')
    local = TestClient(local_app, client=('127.0.0.1', 1234), base_url='http://127.0.0.1')
    assert local.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]}).status_code == 401
