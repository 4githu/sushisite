"""Add only Reader endpoints and modules to the existing shared backend."""
import argparse
import ast
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values, set_key


SETTINGS = {
    'READER_TRANSLATION_PROVIDER': 'hermes_personal_owner',
    'READER_TRANSLATION_HERMES_EXECUTABLE': '/Users/sagi/.hermes/hermes-agent/.hermes/bin/hermes',
    'READER_TRANSLATION_HERMES_HOME': '/Users/sagi/.hermes/profiles/personalbackend',
}


def mount_router(source, candidate):
    """Keep every unrelated existing route byte for byte."""
    if '/reader/translate' in source or '/reader/explain-image' in source:
        raise RuntimeError('Reader routes already exist; review the current integration')
    imports = ('from .reader_translation import translate_reader_segments\n'
               'from .reader_translation.image import explain_reader_image\n')
    anchor = 'from . import workspace\n'
    if source.count(anchor) != 1:
        raise RuntimeError('Shared router import anchor changed')
    source = source.replace(anchor, anchor + imports, 1)
    lines = candidate.splitlines(keepends=True)
    functions = []
    for node in ast.parse(candidate).body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name in {'reader_translate', 'reader_explain_image'}:
            functions.append(''.join(lines[min(d.lineno for d in node.decorator_list) - 1:node.end_lineno]))
    if len(functions) != 2:
        raise RuntimeError('The accepted Reader route contract is missing')
    anchor = '@router.get("/kakao/status")'
    if source.count(anchor) != 1:
        raise RuntimeError('Shared router route anchor changed')
    result = source.replace(anchor, '\n\n'.join(functions) + '\n\n\n' + anchor, 1)
    ast.parse(result)
    return result


def healthy(timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            req = urllib.request.Request('http://127.0.0.1:8000/api/personal/reader/translate',
                                         data=b'{}', headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=2).close()
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return
        except OSError:
            pass
        time.sleep(.2)
    raise RuntimeError('Reader authenticated route health did not pass')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--home', required=True)
    parser.add_argument('--owner-id', required=True, type=int)
    args = parser.parse_args()
    if args.owner_id <= 0:
        raise RuntimeError('A server-confirmed positive owner ID is required')
    SETTINGS['READER_TRANSLATION_PERSONAL_OWNER_ID'] = str(args.owner_id)
    source, backend, home = (Path(p).resolve() for p in (args.source, args.backend, args.home))
    candidate = source / 'personal_project'
    target = backend / 'personal_project'
    router = target / 'router.py'
    original = router.read_text()
    updated = mount_router(original, (candidate / 'router.py').read_text())
    module = target / 'reader_translation'
    if module.exists():
        raise RuntimeError('An existing Reader module must be reviewed before installation')
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    backup = home / ('backend-before-' + str(time.time_ns()))
    backup.mkdir(mode=0o700)
    shutil.copy2(router, backup / 'router.py')
    env = backend / '.env'
    prior = dotenv_values(env)
    manifest = {'source': str(source), 'router_before_sha256': hashlib.sha256(original.encode()).hexdigest(),
                'settings_before': {key: prior.get(key) for key in SETTINGS}}
    manifest_path = backup / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)); manifest_path.chmod(0o600)
    label = f'gui/{os.getuid()}/app.sushisite.backend'
    try:
        shutil.copytree(candidate / 'reader_translation', module,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'AI_WEB_CONTRACT.md'))
        for file in module.rglob('*.py'):
            py_compile.compile(str(file), doraise=True)
        if router.read_text() != original:
            raise RuntimeError('Shared router changed during installation')
        router.write_text(updated)
        for key, value in SETTINGS.items():
            set_key(env, key, value)
        subprocess.run(['/bin/launchctl', 'kickstart', '-k', label], check=True)
        healthy()
        print('READER BACKEND DEPLOYED; existing mainauth remains required')
    except BaseException:
        from dotenv import unset_key
        router.write_text(original)
        if module.exists():
            shutil.rmtree(module)
        for key in SETTINGS:
            if prior.get(key) is None:
                unset_key(env, key)
            else:
                set_key(env, key, prior[key])
        subprocess.run(['/bin/launchctl', 'kickstart', '-k', label], check=False)
        raise


if __name__ == '__main__':
    main()
