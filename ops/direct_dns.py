"""Manage only the direct-route probe record with existing zone credentials."""
import base64
import json
from pathlib import Path
import urllib.request

pem = Path('/Users/sagi/.cloudflared/cert.pem').read_text()
auth = json.loads(base64.b64decode(''.join(line for line in pem.splitlines() if not line.startswith('---'))))
base = 'https://api.cloudflare.com/client/v4/zones/' + auth['zoneID'] + '/dns_records'


def request(method, suffix='', body=None):
    req = urllib.request.Request(base + suffix, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + auth['apiToken'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    if not data.get('success'):
        raise RuntimeError(str(data.get('errors')))
    return data['result']


if __name__ == '__main__':
    records = request('GET', '?name=direct.chobab.app')
    desired = {'type': 'A', 'name': 'direct.chobab.app', 'content': '147.47.160.229', 'proxied': False, 'ttl': 300}
    if records:
        if len(records) != 1 or any(records[0].get(k) != desired[k] for k in ('type', 'content', 'proxied')):
            raise SystemExit('Existing probe DNS differs; refusing to overwrite.')
        print('Existing probe record matches.')
    else:
        result = request('POST', body=desired)
        print('Created DNS-only HTTPS probe record:', result['name'])
