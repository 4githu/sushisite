"""Install a verified Reader build without rebuilding the shared production app."""
import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values, set_key
from gateway import mount


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.chmod(0o600)
    os.replace(temp, path)


def run(args, check=True):
    result = subprocess.run([str(a) for a in args], capture_output=True)
    if check and result.returncode:
        raise RuntimeError('Local service command failed; inspect its private log')
    return result


def stop(label):
    target = f'gui/{os.getuid()}/{label}'
    if run(['/bin/launchctl', 'print', target], check=False).returncode == 0:
        run(['/bin/launchctl', 'bootout', target])


def healthy(port, revision, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{port}/personal-project/reader/_release', headers={'Host': 'chobab.app'})
            with urllib.request.urlopen(req, timeout=2) as response:
                if json.loads(response.read()).get('revision') == revision:
                    page = urllib.request.Request(f'http://127.0.0.1:{port}/personal-project/reader', headers={'Host': 'chobab.app'})
                    with urllib.request.urlopen(page, timeout=4) as rendered:
                        html = rendered.read().decode()
                    match = re.search(r'(/__paiper/[^"\s]+\.(?:js|css))', html)
                    if match:
                        asset = urllib.request.Request(f'http://127.0.0.1:{port}' + match[1], headers={'Host': 'chobab.app'})
                        with urllib.request.urlopen(asset, timeout=2) as response:
                            if response.status == 200:
                                return
        except (OSError, ValueError):
            pass
        time.sleep(.2)
    raise RuntimeError('Reader revision health did not pass')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--legacy-frontend', required=True)
    args = parser.parse_args()
    home = Path(args.home).expanduser().resolve()
    release = Path(args.release).resolve()
    legacy = Path(args.legacy_frontend).resolve()
    if not re.fullmatch('[a-f0-9]{40}', args.revision):
        raise RuntimeError('A full source revision is required')
    build = release / 'sushi-app/build-reader'
    if not (build / 'handler.js').is_file() or not (build / 'client/__paiper').is_dir():
        raise RuntimeError('An isolated __paiper node build is required')
    home.mkdir(parents=True, exist_ok=True, mode=0o700); home.chmod(0o700)
    (home / 'logs').mkdir(exist_ok=True)
    current = home / 'frontend-state.json'
    previous = json.loads(current.read_text()) if current.is_file() else None
    env_path = home / 'frontend-env.json'
    if not env_path.exists():
        source = dotenv_values(legacy / '.env')
        env = {k: v for k, v in source.items() if isinstance(v, str)
               and (k.startswith(('PUBLIC_', 'VITE_')) or k == 'BETTER_AUTH_SECRET')}
        db = Path(source.get('DATABASE_URL', 'local.db'))
        env['DATABASE_URL'] = str(db if db.is_absolute() else legacy / db)
        env.update(VITE_SUSHIFASTURL='', VITE_API_BASE_URL='')
        write_json(env_path, env)
    shutil.copy2(Path(__file__).with_name('run_frontend.py'), home / 'run_frontend.py')
    state = {'release': str(release), 'revision': args.revision}
    script = legacy / 'scripts/serve-production.mjs'
    original = script.read_text()
    prior_upstream = dotenv_values(legacy / '.env').get('PAIPER_READER_UPSTREAM', '') or ''
    updated = mount(original)
    if not (home / 'gateway.before.mjs').exists():
        (home / 'gateway.before.mjs').write_text(original)
    candidate = home / 'gateway.next.mjs'; candidate.write_text(updated)
    run(['/opt/homebrew/opt/node@22/bin/node', '--check', candidate])
    label = 'app.paiper.reader'
    plist = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    info = {'Label': label, 'ProgramArguments': [sys.executable, str(home / 'run_frontend.py'), str(home)],
            'WorkingDirectory': str(home), 'RunAtLoad': True, 'KeepAlive': True,
            'EnvironmentVariables': {'PATH': '/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin'},
            'StandardOutPath': str(home / 'logs/frontend.log'), 'StandardErrorPath': str(home / 'logs/frontend.error.log')}
    try:
        stop(label)
        write_json(current, state)
        plist.write_bytes(plistlib.dumps(info)); plist.chmod(0o600)
        run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', plist])
        healthy(5194, args.revision)
        if script.read_text() != original:
            raise RuntimeError('Gateway changed during installation')
        script.write_text(updated)
        set_key(legacy / '.env', 'PAIPER_READER_UPSTREAM', 'http://127.0.0.1:5194')
        run(['/bin/launchctl', 'kickstart', '-k', f'gui/{os.getuid()}/app.sushisite.frontend'])
        healthy(5173, args.revision)
        write_json(home / 'frontend-previous.json', previous)
        print('READER FRONTEND DEPLOYED', args.revision)
    except BaseException:
        stop(label)
        if previous:
            write_json(current, previous)
            run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', plist])
        else:
            current.unlink(missing_ok=True)
        script.write_text(original)
        set_key(legacy / '.env', 'PAIPER_READER_UPSTREAM', prior_upstream)
        run(['/bin/launchctl', 'kickstart', '-k', f'gui/{os.getuid()}/app.sushisite.frontend'])
        raise


if __name__ == '__main__':
    main()
