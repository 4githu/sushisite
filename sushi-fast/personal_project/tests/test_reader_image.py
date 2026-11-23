import asyncio
import base64
import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import router

# Synthetic 1x1 PNG, never a real document.
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='

@pytest.fixture
def client_setup(monkeypatch, tmp_path):
    profile=tmp_path/'profile'; profile.mkdir()
    exe=tmp_path/'hermes'; marker=tmp_path/'called'
    exe.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\n' + f'Path({str(marker)!r}).touch()\n' + 'p=json.load(sys.stdin)\nprint(json.dumps({"explanation":"Synthetic explanation"}))\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    for key,val in {'READER_TRANSLATION_PROVIDER':'hermes_personal_owner','READER_TRANSLATION_PERSONAL_OWNER_ID':'71','READER_TRANSLATION_HERMES_EXECUTABLE':str(exe),'READER_TRANSLATION_HERMES_HOME':str(profile)}.items(): monkeypatch.setenv(key,val)
    app=FastAPI(); app.include_router(router.router); app.dependency_overrides[router.current_user_id]=lambda:71
    return TestClient(app),app,marker


def test_owner_can_explain_selected_image(client_setup):
    client,_,marker=client_setup
    r=client.post('/api/personal/reader/explain-image',json={'image':{'mime_type':'image/png','base64':PNG},'caption':'Synthetic graph','context':'Synthetic context','target_language':'Korean'})
    assert r.status_code==200
    assert r.json()=={'explanation':'Synthetic explanation'}
    assert r.headers['cache-control'].startswith('no-store')
    assert marker.exists()


def payload(**extra):
    return {'image': {'mime_type': 'image/png', 'base64': PNG}, **extra}


def test_other_user_and_injected_profile_cannot_invoke(client_setup):
    client, app, marker = client_setup
    app.dependency_overrides[router.current_user_id] = lambda: 72
    r = client.post('/api/personal/reader/explain-image', json=payload(owner_id=71, profile_home='/tmp/evil'))
    assert r.status_code == 503 and not marker.exists()


def test_unauthenticated_is_rejected(client_setup, monkeypatch):
    client, app, marker = client_setup
    app.dependency_overrides.clear()
    monkeypatch.setattr(router.JMT, 'SECRET_KEY', 'synthetic-test-only-secret')
    monkeypatch.setattr(router.JMT, 'ALGORITHM', 'HS256')
    assert client.post('/api/personal/reader/explain-image', json=payload()).status_code == 401
    assert not marker.exists()


def test_invalid_image_content_type_and_origin_never_invoke(client_setup):
    client, _, marker = client_setup
    path = '/api/personal/reader/explain-image'
    assert client.post(path, json=payload(image={'mime_type':'image/png','base64':'invalid'})).status_code == 400
    assert client.post(path, content=json.dumps(payload()), headers={'Content-Type':'text/plain'}).status_code == 415
    assert client.post(path, json=payload(), headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.post(path, content=b' ' * (1100 * 1024 + 1), headers={'Content-Type':'application/json'}).status_code == 413
    assert not marker.exists()


def test_provider_error_then_retry_is_distinct_invocation(client_setup, tmp_path):
    client, _, marker = client_setup
    exe=tmp_path/'hermes'; attempts=tmp_path/'attempts'
    exe.write_text('#!/usr/bin/python3\nimport sys,json\nfrom pathlib import Path\n' + f'p=Path({str(attempts)!r})\n' + 'n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\njson.load(sys.stdin)\nif n==1: sys.exit(1)\nprint(json.dumps({"explanation":"recovered"}))\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    path='/api/personal/reader/explain-image'
    assert client.post(path,json=payload()).status_code == 502
    assert client.post(path,json=payload()).json() == {'explanation':'recovered'}
    assert attempts.read_text() == '2'


def test_cancel_kills_child_process(tmp_path):
    from personal_project.reader_translation import _run_hermes_command
    exe=tmp_path/'hermes'; pidfile=tmp_path/'pid'
    exe.write_text('#!/usr/bin/python3\nimport os,time\nfrom pathlib import Path\n' + f'Path({str(pidfile)!r}).write_text(str(os.getpid()))\n' + 'time.sleep(60)\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    async def run():
        task=asyncio.create_task(_run_hermes_command(b'{}','test',str(exe),str(tmp_path)))
        for _ in range(100):
            if pidfile.exists(): break
            await asyncio.sleep(.02)
        assert pidfile.exists()
        pid=int(pidfile.read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    asyncio.run(run())


def test_disconnect_cancels_and_reaps_provider(tmp_path):
    from personal_project.reader_translation.image import _invoke_until_disconnect
    from fastapi import HTTPException
    exe=tmp_path/'hermes'; pidfile=tmp_path/'pid'
    exe.write_text('#!/usr/bin/python3\nimport os,time\nfrom pathlib import Path\n' + f'Path({str(pidfile)!r}).write_text(str(os.getpid()))\n' + 'time.sleep(60)\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    class Request:
        async def is_disconnected(self): return pidfile.exists()
    async def run():
        with pytest.raises(HTTPException) as err:
            await _invoke_until_disconnect(Request(), b'{}', str(exe), str(tmp_path))
        assert err.value.status_code == 499
        with pytest.raises(ProcessLookupError): os.kill(int(pidfile.read_text()), 0)
    asyncio.run(run())


def test_image_plugin_sends_multimodal_and_returns_explanation(monkeypatch, capsys):
    import io
    from types import SimpleNamespace
    from personal_project.reader_translation import hermes_plugin
    seen = {}
    class LLM:
        def complete(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(text='Synthetic answer')
    monkeypatch.setattr(hermes_plugin.sys, 'stdin', io.StringIO(json.dumps(payload(caption='Synthetic caption'))))
    assert hermes_plugin._handle_image(SimpleNamespace(llm=LLM()), None) == 0
    assert json.loads(capsys.readouterr().out) == {'explanation': 'Synthetic answer'}
    assert seen['purpose'] == 'paiper-reader.image-explanation'
    parts=seen['messages'][1]['content']
    assert parts[1]['image_url']['url'] == 'data:image/png;base64,' + PNG
    assert 'Synthetic caption' in parts[0]['text']


def test_image_plugin_provider_error_does_not_emit_source(monkeypatch, capsys):
    import io
    from types import SimpleNamespace
    from personal_project.reader_translation import hermes_plugin
    class LLM:
        def complete(self, **kwargs): raise RuntimeError('sensitive provider details')
    monkeypatch.setattr(hermes_plugin.sys, 'stdin', io.StringIO(json.dumps(payload(caption='sensitive caption'))))
    assert hermes_plugin._handle_image(SimpleNamespace(llm=LLM()), None) == 2
    captured=capsys.readouterr()
    assert not captured.out and 'sensitive' not in captured.err
