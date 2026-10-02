"""Add the NETAQ hostname to the existing Cloudflare tunnel, with backup.

Uses the existing machine's Cloudflare login; never prints its credentials.
Does not replace any existing record or remove another hostname.
"""
from pathlib import Path
import base64,json,urllib.request,datetime,subprocess,shutil

root=Path.home()/'.cloudflared'
config=root/'config.yml'
text=config.read_text()
hostname='netaq.chobab.app'
tunnel='dcecd4bc-11d4-4e8c-982a-83c5721b9eb0'
if f'tunnel: {tunnel}' not in text:raise SystemExit('Unexpected tunnel; no changes made.')
pem=(root/'cert.pem').read_text()
auth=json.loads(base64.b64decode(''.join(line for line in pem.splitlines() if not line.startswith('---'))))
base='https://api.cloudflare.com/client/v4/zones/'+auth['zoneID']+'/dns_records'
def request(method,suffix='',body=None):
    req=urllib.request.Request(base+suffix,method=method,data=json.dumps(body).encode() if body else None,headers={'Authorization':'Bearer '+auth['apiToken'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:result=json.load(r)
    if not result.get('success'):raise RuntimeError('Cloudflare rejected the request.')
    return result['result']
desired={'type':'CNAME','name':hostname,'content':tunnel+'.cfargotunnel.com','proxied':True,'ttl':1}
records=request('GET','?name='+hostname)
if records and (len(records)!=1 or any(records[0].get(k)!=desired[k] for k in ('type','content','proxied'))):raise SystemExit('Existing DNS differs; refusing to overwrite.')
if f'hostname: {hostname}' not in text:
    backup=config.with_name('config.before-netaq-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+'.yml')
    shutil.copy2(config,backup)
    rules=f'  - hostname: {hostname}\n    path: ^/(auth|api)(/.*)?$\n    service: http://127.0.0.1:8000\n  - hostname: {hostname}\n    service: http://127.0.0.1:5173\n'
    if text.count('  - service: http_status:404')!=1:raise SystemExit('Unexpected fallback rule.')
    config.write_text(text.replace('  - service: http_status:404',rules+'  - service: http_status:404'))
    result=subprocess.run(['/opt/homebrew/bin/cloudflared','tunnel','ingress','validate'],capture_output=True,text=True)
    if result.returncode:shutil.copy2(backup,config);raise SystemExit('Ingress validation failed; restored original config.')
    print('Ingress added; backup:',backup.name)
if not records:request('POST',body=desired);print('DNS created:',hostname)
else:print('DNS already matches:',hostname)
