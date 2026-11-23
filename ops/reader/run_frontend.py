"""Private settings are loaded at runtime, after the public-only frontend build."""
import json
import os
import sys
from pathlib import Path

home = Path(sys.argv[1])
state = json.loads((home / 'frontend-state.json').read_text())
env = {k: os.environ[k] for k in ('HOME', 'PATH', 'LANG', 'TMPDIR') if k in os.environ}
env.update(json.loads((home / 'frontend-env.json').read_text()))
env.update(PAIPER_REVISION=state['revision'], PAIPER_PORT='5194',
           SUSHI_ORIGIN='https://chobab.app', SUSHI_PROTOCOL_HEADER='x-sushi-proto')
release = Path(state['release'])
os.chdir(release / 'sushi-app')
node = '/opt/homebrew/opt/node@22/bin/node'
os.execve(node, [node, str(release / 'ops/reader/serve.mjs'), str(release / 'sushi-app/build-reader')], env)
