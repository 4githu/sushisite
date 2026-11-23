import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('reader_gateway', Path(__file__).with_name('gateway.py'))
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


def test_mount_preserves_existing_routes_and_is_idempotent(tmp_path):
    source = '''import http from 'node:http';
const server = http.createServer((req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  const hostname = String(req.headers.host || '').split(':')[0].toLowerCase();
  if (hostname === 'netaq.chobab.app' && path === '/notes') res.end('existing notes');
  else res.end('existing app');
});
'''
    result = gateway.mount(source)
    assert "res.end('existing notes')" in result
    assert "res.end('existing app')" in result
    assert result.index(gateway.MARKER) < result.index("hostname === 'netaq.chobab.app'")
    assert gateway.mount(result) == result
    file = tmp_path / 'gateway.mjs'; file.write_text(result)
    subprocess.run(['/opt/homebrew/opt/node@22/bin/node', '--check', file], check=True, capture_output=True)


def test_unrecognized_gateway_is_not_silently_changed():
    with pytest.raises(RuntimeError, match='layout changed'):
        gateway.mount('unrecognized existing gateway')


@pytest.mark.parametrize('has_previous', [False, True])
def test_failed_candidate_restores_gateway_and_previous_reader(tmp_path, monkeypatch, has_previous):
    import json
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        spec = importlib.util.spec_from_file_location('reader_installer', Path(__file__).with_name('install_frontend.py'))
        installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
    finally:
        sys.path.pop(0)
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    legacy = tmp_path / 'legacy'; (legacy / 'scripts').mkdir(parents=True)
    original = "const server = http.createServer((req, res) => {\n  const hostname = 'synthetic';\n});\n"
    script = legacy / 'scripts/serve-production.mjs'; script.write_text(original)
    (legacy / '.env').write_text("PAIPER_READER_UPSTREAM=''\n")
    (runtime / 'frontend-env.json').write_text('{}')
    previous = {'revision': 'b' * 40, 'release': '/synthetic-previous'}
    if has_previous: (runtime / 'frontend-state.json').write_text(json.dumps(previous))
    release = tmp_path / 'release'; (release / 'sushi-app/build-reader/client/__paiper').mkdir(parents=True)
    (release / 'sushi-app/build-reader/handler.js').touch()
    (tmp_path / 'Library/LaunchAgents').mkdir(parents=True)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(installer, 'stop', lambda *a: None)
    calls = []
    monkeypatch.setattr(installer, 'run', lambda args, **kw: calls.append([str(a) for a in args]))
    monkeypatch.setattr(installer, 'healthy', lambda *a: (_ for _ in ()).throw(RuntimeError('synthetic startup failure')))
    monkeypatch.setattr(sys, 'argv', ['install', '--home', str(runtime), '--release', str(release), '--revision', 'a' * 40, '--legacy-frontend', str(legacy)])
    with pytest.raises(RuntimeError, match='synthetic startup failure'): installer.main()
    assert script.read_text() == original
    assert installer.dotenv_values(legacy / '.env')['PAIPER_READER_UPSTREAM'] == ''
    state = runtime / 'frontend-state.json'
    if has_previous: assert json.loads(state.read_text()) == previous
    else: assert not state.exists()
