"""Private DSHS board relay via a bounded browser adapter, durable provenance."""
import base64,json,os,shutil,subprocess,threading,time,uuid
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from .db import connection
from .router import native_kakao_user_id
from . import community_v2 as community
from .kakao_board_sync import plain
router=APIRouter(prefix='/dshs-relay')
SCRIPT=Path(__file__).resolve().parents[2]/'ops/dshs_bridge.mjs'
CONFIG=Path(__file__).resolve().parents[1]/'.runtime/dshs-credentials.json'
stop=threading.Event()
with connection() as db:
 db.executescript('''CREATE TABLE IF NOT EXISTS dshs_relay_state(id INTEGER PRIMARY KEY CHECK(id=1),last_post_id INTEGER NOT NULL DEFAULT 0,last_scan TEXT,error TEXT);
 CREATE TABLE IF NOT EXISTS dshs_relay_health(id INTEGER PRIMARY KEY CHECK(id=1),error TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS dshs_relay_seen(remote_id TEXT PRIMARY KEY,post_id INTEGER,state TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS dshs_relay_outbox(post_id INTEGER PRIMARY KEY,state TEXT NOT NULL DEFAULT 'queued',result TEXT);''');db.commit()
def relay_access(db,uid,bid,action='read'):
 board=community.board_access(db,uid,bid,action)
 # The source is a private board. Never mirror it into a public destination.
 if not board['restricted']:raise HTTPException(403,'자료공유 연동 대상은 비공개 게시판이어야 합니다.')
 if not db.execute("SELECT 1 FROM community_acl WHERE user_id=? AND scope=? AND action='read' AND allowed=1",(uid,f'board:{bid}')).fetchone():raise HTTPException(403,'연동 계정의 게시판 열람 허용이 필요합니다.')
 return board
def invoke(job):
 node=shutil.which('node') or '/opt/homebrew/bin/node'
 r=subprocess.run([node,str(SCRIPT)],input=json.dumps(job),text=True,capture_output=True,timeout=600)
 try:result=json.loads(r.stdout)
 except ValueError:raise RuntimeError('DSHS 자동화 응답 오류')
 if result.get('error'):raise RuntimeError(result['error'])
 return result
@router.get('')
def status(uid:int=Depends(native_kakao_user_id)):
 if not community.admin(uid):raise HTTPException(403,"관리자 권한이 필요합니다.")
 with connection() as db:
  r=db.execute('SELECT * FROM dshs_relay_state WHERE id=1').fetchone()
  return {'configured':CONFIG.is_file(),'health':dict(db.execute('SELECT * FROM dshs_relay_health WHERE id=1').fetchone() or {}),'state':dict(r) if r else None,'jobs':[dict(r) for r in db.execute('SELECT * FROM dshs_relay_outbox ORDER BY post_id DESC LIMIT 20')],'intervalSeconds':1800}
def tick():
 created=[]
 try:return _tick(created)
 except BaseException:
  # A rolled-back import must not leave private orphan files consuming disk.
  with connection() as db:
   for path in created:
    if not db.execute('SELECT 1 FROM personal_resources WHERE id=?',(path.name,)).fetchone():path.unlink(missing_ok=True)
  raise

def _tick(created):
 if not CONFIG.is_file():return
 with connection() as db:
  route=db.execute('SELECT * FROM kakao_board_routes WHERE enabled=1 AND board_id=4').fetchone()
  if not route:return
  uid=route['user_id'];bid=route['board_id'];relay_access(db,uid,bid,'post')
  state=db.execute('SELECT * FROM dshs_relay_state WHERE id=1').fetchone()
  seen=[r[0] for r in db.execute('SELECT remote_id FROM dshs_relay_seen')]
 result=invoke({'command':'read','seen':seen,'baseline':not state})
 if not result.get('complete'):raise RuntimeError('DSHS 목록을 끝까지 읽지 못했습니다.')
 with connection() as db:
  relay_access(db,uid,bid,'post')
  if not state:
   db.executemany("INSERT OR IGNORE INTO dshs_relay_seen VALUES(?,NULL,'baseline')",[(id,) for id in result['ids']])
   maximum=db.execute('SELECT COALESCE(MAX(id),0) FROM community_posts WHERE board_id=?',(bid,)).fetchone()[0]
   db.execute('INSERT INTO dshs_relay_state(id,last_post_id,last_scan) VALUES(1,?,CURRENT_TIMESTAMP)',(maximum,));db.commit();return
  for post in result['posts']:
   if db.execute('SELECT 1 FROM dshs_relay_seen WHERE remote_id=?',(post['id'],)).fetchone():continue
   # Outbound provenance is explicit; never echo our own mirrored source link.
   if 'https://netaq.chobab.app/personal-project/calendar/boards?board=4&post=' in post['text']:
    db.execute("INSERT OR IGNORE INTO dshs_relay_seen VALUES(?,NULL,'outbound')",(post['id'],));continue
   nodes=[{'type':'paragraph','content':[{'type':'text','text':post['text'][:30000]}]}]
   for png in post.get('images',[]):
    content=base64.b64decode(png,validate=True)
    if len(content)>8*1024*1024 or not content.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('DSHS 이미지 형식 오류')
    asset=uuid.uuid4().hex;community.ROOT.mkdir(parents=True,exist_ok=True);target=community.ROOT/asset;created.append(target);target.write_bytes(content);target.chmod(0o600)
    db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(asset,uid,bid,'첨부.png','image/png',len(content)))
    nodes.append({'type':'image','attrs':{'src':f'/api/personal/resources/{asset}','alt':'자료 첨부'}})
   for attachment in post.get('files',[]):
    content=base64.b64decode(attachment['data'],validate=True)
    if not content or len(content)>20*1024*1024:raise RuntimeError('DSHS 첨부 크기 제한')
    asset=uuid.uuid4().hex;name=Path(attachment['name']).name[:240] or '첨부파일'
    community.ROOT.mkdir(parents=True,exist_ok=True);target=community.ROOT/asset;created.append(target);target.write_bytes(content);target.chmod(0o600)
    db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(asset,uid,bid,name,'application/octet-stream',len(content)))
    nodes.append({'type':'paragraph','content':[{'type':'text','text':name,'marks':[{'type':'link','attrs':{'href':f'/api/personal/resources/{asset}'}}]}]})
   nodes.append({'type':'paragraph','content':[{'type':'text','text':post['url']}]})
   document={'schemaVersion':2,'version':1,'documentId':uuid.uuid4().hex,'blocks':[],'richContent':{'type':'doc','content':nodes}}
   used=db.execute('SELECT COALESCE(SUM(size),0) FROM personal_resources WHERE user_id=?',(uid,)).fetchone()[0]
   if used>int(os.getenv('PERSONAL_RESOURCE_QUOTA_BYTES','1073741824')):raise RuntimeError('자료 저장 한도를 초과했습니다.')
   pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(bid,uid,post['title'][:160],community.encode_document(document),post['text'])).lastrowid
   db.execute("INSERT INTO dshs_relay_seen VALUES(?,?,'imported')",(post['id'],pid))
  posts=db.execute('SELECT * FROM community_posts WHERE board_id=? AND id>? ORDER BY id',(bid,state['last_post_id'])).fetchall()
  for p in posts:
   if not p['deleted'] and not db.execute('SELECT 1 FROM dshs_relay_seen WHERE post_id=?',(p['id'],)).fetchone():db.execute('INSERT OR IGNORE INTO dshs_relay_outbox(post_id) VALUES(?)',(p['id'],))
   db.execute('UPDATE dshs_relay_state SET last_post_id=? WHERE id=1',(p['id'],))
  db.execute('UPDATE dshs_relay_state SET last_scan=CURRENT_TIMESTAMP,error=NULL WHERE id=1');db.commit()
 with connection() as db:jobs=db.execute("SELECT p.* FROM community_posts p JOIN dshs_relay_outbox o ON o.post_id=p.id WHERE o.state='queued'").fetchall()
 for p in jobs:
  with connection() as db:
   relay_access(db,uid,bid)
   current=db.execute('SELECT * FROM community_posts WHERE id=? AND deleted=0',(p['id'],)).fetchone()
   if not current:db.execute("UPDATE dshs_relay_outbox SET state='cancelled' WHERE post_id=?",(p['id'],));db.commit();continue
   db.execute("UPDATE dshs_relay_outbox SET state='unknown' WHERE post_id=?",(p['id'],));db.commit()
  # Unknown is durable before touching the remote submit button.
  try:
   import re,tempfile
   with tempfile.TemporaryDirectory(prefix='dshs-send-') as stage:
    files=[]
    with connection() as db:
     for rid in dict.fromkeys(re.findall(r'/api/personal/resources/([a-f0-9]{32})',current['document'])):
      asset=community.resource_access(db,uid,rid)
      if asset['board_id']!=bid:raise RuntimeError('게시판 첨부 권한 불일치')
      suffix=Path(asset['name']).suffix;target=Path(stage)/(rid+suffix);shutil.copyfile(community.ROOT/rid,target);files.append(str(target))
    result=invoke({'command':'publish','title':current['title'],'text':plain(json.loads(current['document'])),'source':f'https://netaq.chobab.app/personal-project/calendar/boards?board=4&post={p["id"]}','files':files})
   with connection() as db:db.execute("UPDATE dshs_relay_outbox SET state='succeeded',result=? WHERE post_id=?",(json.dumps(result),p['id']));db.commit()
  except Exception as e:
   with connection() as db:db.execute('UPDATE dshs_relay_outbox SET result=? WHERE post_id=?',(str(e)[:500],p['id']));db.commit()
def loop():
 # Both the backend and the standalone launch agent may start; only one may send.
 import fcntl
 lock_path=CONFIG.parent/'dshs-relay.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
 with lock_path.open('a') as leader:
  try:fcntl.flock(leader,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  while not stop.is_set():
   try:
    tick()
    with connection() as db:db.execute('INSERT OR REPLACE INTO dshs_relay_health(id,error,updated_at) VALUES(1,NULL,CURRENT_TIMESTAMP)');db.commit()
   except Exception as e:
    with connection() as db:db.execute('INSERT OR REPLACE INTO dshs_relay_health(id,error,updated_at) VALUES(1,?,CURRENT_TIMESTAMP)',(str(e)[:500],));db.commit()
   stop.wait(1800)
@router.on_event('startup')
def start():
 if os.getenv('DISABLE_KAKAO_BRIDGE')=='1' or not CONFIG.is_file():return
 stop.clear();threading.Thread(target=loop,daemon=True,name='dshs-relay').start()
@router.on_event('shutdown')
def shutdown():stop.set()

if __name__=='__main__':
 import signal
 signal.signal(signal.SIGTERM,lambda *_:stop.set())
 signal.signal(signal.SIGINT,lambda *_:stop.set())
 loop()
