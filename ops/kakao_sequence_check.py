#!/usr/bin/env python3
"""Fixed synthetic photo+note live check through the clinic product path, own room only."""
import argparse,json,os,sys,tempfile,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',action='store_true');p.add_argument('--attempt-id',default='01');p.add_argument('--pages',type=int,default=4);p.add_argument('--close-first',action='store_true');args=p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]{2,60}',args.attempt_id):raise SystemExit('Invalid synthetic attempt ID')
if not 1<=args.pages<=20:raise SystemExit('Use 1–20 synthetic report pages')
root=Path(__file__).resolve().parents[1];kind='candidate' if args.candidate else 'installed'
proof=root/'sushi-fast/.runtime/kakao-live-checks'/('sequence-20261111-'+kind+('' if args.attempt_id=='01' else '-'+args.attempt_id)+'.json')
if proof.exists():
 prior=json.loads(proof.read_text())
 if prior.get('pages',1)!=args.pages or prior.get('closedFirst',False)!=args.close_first:
  print('Attempt ID belongs to different page-count/window conditions. Use a new attempt ID; no send was performed.',file=sys.stderr);raise SystemExit(2)
 print(proof.read_text());print('Prior attempt is preserved and not resent. After a fix, use --attempt-id NEW_ID for a distinct authorized synthetic own-room test.',file=sys.stderr);raise SystemExit(0 if prior.get('state')=='succeeded' else 2)
with proof.open('x') as f:json.dump({'state':'started'},f)
sys.path.insert(0,str(root/'sushi-fast'))
with tempfile.TemporaryDirectory(prefix='kakao-sequence-') as tmp:
 os.environ['PERSONAL_PROJECT_DB_PATH']=str(Path(tmp)/'fixture.db');os.environ['PERSONAL_RESOURCE_ROOT']=str(Path(tmp)/'resources');os.environ['DISABLE_KAKAO_BRIDGE']='1';os.environ['DISABLE_TREND_REFRESH']='1'
 from personal_project import native_kakao,kakao_bridge
 if args.candidate:kakao_bridge.BINARY=root/'sushi-fast/.runtime/kakao-bridge.next'
 real=kakao_bridge.invoke;calls=[]
 def invoke(command,**kw):
  if kw.get('room')!='본계정':raise RuntimeError('Own-room fixture only')
  value=real(command,**kw)
  calls.append({'command':command,'fileCount':len(kw.get('files') or []),'keepRoomOpen':kw.get('keepRoomOpen',False),'sent':value.get('sent'),'verifiedBy':value.get('verifiedBy'),'cleanup':value.get('cleanup'),'trusted':value.get('trusted')})
  return value
 kakao_bridge.invoke=invoke
 try:
  health=real('status')
  if not health.get('trusted'):raise RuntimeError('Actual executing process lacks accessibility permission')
  if args.close_first:
   cleanup=real('cleanup',room='본계정')
   if cleanup.get('roomClosed') is not True:raise RuntimeError('Could not establish a closed initial test window')
  job=native_kakao.create_job(999999,0)
  with native_kakao._jobs_lock:
   item=native_kakao._jobs[job['jobId']];item.clinic=True;item.destination='본계정';item.target_room='합성 검증';item.fallback_reason=None
  import pymupdf
  document=pymupdf.open()
  for number in range(1,args.pages+1):
   page=document.new_page(width=595,height=842)
   page.insert_text((50,70),f'SYNTHETIC CLINIC REPORT {args.attempt_id} / {number} of {args.pages}',fontsize=15)
   page.insert_textbox(pymupdf.Rect(50,110,545,760),('Own-room product-path test. No real student data.\n' * (5+number)),fontsize=12)
   payload=page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).tobytes('jpeg')
   native_kakao.store_page(job['jobId'],999999,0,number,'image/jpeg',payload)
  document.close()
  result=native_kakao.send_clinic_job(job['jobId'],999999,0)
  sends=[v for v in calls if v['command']=='send']
  assert len(sends)==2 and sends[0]['fileCount']==args.pages and all(v['sent'] and v['verifiedBy']=='outgoing_rows' for v in sends)
  assert sends[0]['cleanup']['roomClosed'] is False and sends[0]['cleanup']['closeRequested'] is False
  assert sends[1]['cleanup']['roomClosed'] is True and sends[1]['cleanup']['searchCleared'] is True
  record={'state':'succeeded','binary':kind,'pages':args.pages,'closedFirst':args.close_first,'result':result,'calls':calls}
 except Exception as error:record={'state':'failed','binary':kind,'error_type':type(error).__name__,'error':str(error),'calls':calls}
 proof.write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False));raise SystemExit(0 if record['state']=='succeeded' else 2)
