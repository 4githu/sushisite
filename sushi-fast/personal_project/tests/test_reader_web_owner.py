import json
import stat

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import router


@pytest.fixture
def setup_owner(monkeypatch, tmp_path):
    home = tmp_path / 'owner-profile'
    home.mkdir()
    executable = tmp_path / 'fake-hermes'
    marker = tmp_path / 'invocations'
    executable.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\n' + f'Path({str(marker)!r}).touch()\n' + 'p=json.load(sys.stdin)\nprint(json.dumps({"translations":[{"id": s["id"],"text":"ok"} for s in p["segments"]]}))\n')
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv('READER_TRANSLATION_PROVIDER', 'hermes_personal_owner')
    monkeypatch.setenv('READER_TRANSLATION_PERSONAL_OWNER_ID', '71')
    monkeypatch.setenv('READER_TRANSLATION_HERMES_EXECUTABLE', str(executable))
    monkeypatch.setenv('READER_TRANSLATION_HERMES_HOME', str(home))
    app = FastAPI(); app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 71
    return TestClient(app), app, marker


def test_standard_authenticated_owner_http_uses_configured_personal_hermes(setup_owner):
    client, _, marker = setup_owner
    response = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}], 'owner_id': 72, 'profile_home': '/untrusted'})
    assert response.status_code == 200
    assert response.json() == {'translations': [{'id': 's1', 'text': 'ok'}]}
    assert marker.exists()


def test_owner_rejects_simple_text_plain_cross_site_post(setup_owner):
    client, _, marker = setup_owner
    response = client.post('/api/personal/reader/translate', content=json.dumps({'segments': [{'id': 's1', 'text': 'synthetic'}]}), headers={'content-type': 'text/plain', 'origin': 'https://untrusted.example'})
    assert response.status_code == 415
    assert not marker.exists()


def test_owner_rejects_untrusted_origin_even_if_global_cors_wildcard_allows_it(setup_owner):
    client, _, marker = setup_owner
    response = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]}, headers={'origin': 'https://attacker.trycloudflare.com'})
    assert response.status_code == 403
    assert not marker.exists()


def test_other_user_cannot_choose_owner_or_start_process(setup_owner):
    client, app, marker = setup_owner
    app.dependency_overrides[router.current_user_id] = lambda: 72
    response = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}], 'owner_id': 71, 'profile_home': '/untrusted'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'translation_provider_unavailable'
    assert not marker.exists()


@pytest.mark.parametrize('owner', ['', '0', '-1', 'bad', '７１'])
def test_missing_or_invalid_configured_owner_fails_closed(setup_owner, monkeypatch, owner):
    client, _, marker = setup_owner
    monkeypatch.setenv('READER_TRANSLATION_PERSONAL_OWNER_ID', owner)
    response = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]})
    assert response.status_code == 503
    assert not marker.exists()


def test_standard_route_still_requires_authentication(setup_owner, monkeypatch):
    client, app, marker = setup_owner
    app.dependency_overrides.clear()
    monkeypatch.setattr(router.JMT, 'SECRET_KEY', 'synthetic-test-only-secret')
    monkeypatch.setattr(router.JMT, 'ALGORITHM', 'HS256')
    response = client.post('/api/personal/reader/translate', json={'segments': [{'id': 's1', 'text': 'synthetic'}]})
    assert response.status_code == 401
    assert not marker.exists()
