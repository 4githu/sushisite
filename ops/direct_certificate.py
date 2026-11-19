"""DNS-validated certificate, loading existing credentials only into child environment."""
import os
from pathlib import Path
import subprocess

from direct_dns import auth

state = Path('/Users/sagi/Library/Application Support/sushisite-direct-tls')
state.mkdir(mode=0o700, parents=True, exist_ok=True)
environment = dict(os.environ, CF_DNS_API_TOKEN=auth['apiToken'])
raise SystemExit(subprocess.call([
    '/opt/homebrew/bin/lego', 'run', '--path', str(state), '--accept-tos',
    '--email', 'sgonsisgood@gmail.com', '--dns', 'cloudflare',
    '--dns.resolvers', '1.1.1.1:53',
    '--domains', 'direct.chobab.app', '--domains', 'chobab.app',
    '--domains', 'aura.chobab.app', '--domains', 'rehear.chobab.app',
], env=environment))
