"""Private DSHS board relay via a bounded browser adapter, durable provenance."""
import base64,json,logging,os,shutil,subprocess,threading,time,uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter,Depends,HTTPException
from .db import connection
from .router import native_kakao_user_id
from . import community_v2 as community
from .kakao_board_sync import enqueue, plain
router=APIRouter(prefix='/dshs-relay')
SCRIPT=Path(__file__).resolve().parents[2]/'ops/dshs_bridge.mjs'
RUNTIME=Path(__file__).resolve().parents[1]/'.runtime'
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
DSHS_EMAIL=os.getenv('DSHS_EMAIL','bot@dshs.app').strip()
_credentials_ready=None
stop=threading.Event()
DSHS_CATEGORIES={
 '기타':('기타',),
 '대회':('대회정보','대회'),
 '장학금/지원사업':('장학금정보','장학금/지원사업'),
 '학습':('학습',),
}

def credentials_ready():
 global _credentials_ready
 if _credentials_ready is not None:return _credentials_ready
 _credentials_ready=bool(DSHS_EMAIL and os.getenv('DSHS_PASSWORD','').strip())
 return _credentials_ready

with connection() as db:
 db.executescript('''CREATE TABLE IF NOT EXISTS dshs_relay_state(id INTEGER PRIMARY KEY CHECK(id=1),last_post_id INTEGER NOT NULL DEFAULT 0,last_scan TEXT,error TEXT);
 CREATE TABLE IF NOT EXISTS dshs_relay_health(id INTEGER PRIMARY KEY CHECK(id=1),error TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS dshs_relay_seen(remote_id TEXT PRIMARY KEY,post_id INTEGER,state TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS dshs_relay_outbox(post_id INTEGER PRIMARY KEY,state TEXT NOT NULL DEFAULT 'queued',result TEXT);
 CREATE TABLE IF NOT EXISTS dshs_relay_categories(root_board_id INTEGER NOT NULL,category TEXT NOT NULL,board_id INTEGER UNIQUE,PRIMARY KEY(root_board_id,category),FOREIGN KEY(root_board_id) REFERENCES community_boards(id) ON DELETE CASCADE,FOREIGN KEY(board_id) REFERENCES community_boards(id) ON DELETE SET NULL);''');db.commit()
def relay_access(db,uid,bid,action='read'):
 board=community.board_access(db,uid,bid,action)
 root=board
 while root['parent_id']:
  parent=db.execute('SELECT * FROM community_boards WHERE id=?',(root['parent_id'],)).fetchone()
  if not parent:raise HTTPException(403,'자료공유 상위 게시판을 찾을 수 없습니다.')
  root=parent
 # Channels inherit the private access boundary of their 자료공유 parent.
 if not root['restricted']:raise HTTPException(403,'자료공유 연동 대상은 비공개 게시판이어야 합니다.')
 if not db.execute("SELECT 1 FROM community_acl WHERE user_id=? AND scope=? AND action='read' AND allowed=1",(uid,f"board:{root['id']}" )).fetchone():raise HTTPException(403,'연동 계정의 상위 게시판 열람 허용이 필요합니다.')
 return board

def ensure_category_channels(db,root_id):
 root=db.execute('SELECT * FROM community_boards WHERE id=?',(root_id,)).fetchone()
 if not root:raise RuntimeError('자료공유 상위 게시판을 찾을 수 없습니다.')
 for category,aliases in DSHS_CATEGORIES.items():
  mapping=db.execute('SELECT board_id FROM dshs_relay_categories WHERE root_board_id=? AND category=?',(root_id,category)).fetchone()
  if mapping:continue
  channels=db.execute('SELECT id,name FROM community_boards WHERE parent_id=? AND archived=0 ORDER BY sort_order,id',(root_id,)).fetchall()
  channel=next((row for alias in aliases for row in channels if row['name']==alias),None)
  if not channel:
   sort_order=db.execute('SELECT COALESCE(MAX(sort_order),0)+10 FROM community_boards WHERE parent_id=?',(root_id,)).fetchone()[0]
   channel_id=db.execute('INSERT INTO community_boards(name,parent_id,sort_order) VALUES(?,?,?)',(aliases[0],root_id,sort_order)).lastrowid
  else:channel_id=channel['id']
  db.execute('INSERT INTO dshs_relay_categories(root_board_id,category,board_id) VALUES(?,?,?)',(root_id,category,channel_id))
 return {r['category']:r['board_id'] for r in db.execute('SELECT category,board_id FROM dshs_relay_categories WHERE root_board_id=?',(root_id,))}

def category_board(db,root_id,category):
 if category in ('공지','_announcement'):return root_id
 rows=ensure_category_channels(db,root_id)
 return rows.get(category) or rows.get('기타') or root_id

def category_for_board(db,root_id,bid):
 row=db.execute('SELECT category FROM dshs_relay_categories WHERE root_board_id=? AND board_id=?',(root_id,bid)).fetchone()
 if row:return row['category']
 channel=db.execute('SELECT name FROM community_boards WHERE id=?',(bid,)).fetchone()
 name=channel['name'] if channel else ''
 return {'대회정보':'대회','대회':'대회','장학금정보':'장학금/지원사업','장학금/지원사업':'장학금/지원사업','학습':'학습'}.get(name,'기타')
def invoke(job):
 node=shutil.which('node') or '/opt/homebrew/bin/node'
 r=subprocess.run([node,str(SCRIPT)],input=json.dumps(job),text=True,capture_output=True,timeout=600)
 try:result=json.loads(r.stdout)
 except ValueError:raise RuntimeError('DSHS 자동화 응답 오류')
 if result.get('error'):raise RuntimeError(result['error'])
 return result

def enqueue_post(db,post_id):
 if not credentials_ready():return False
 route=db.execute('SELECT * FROM kakao_board_routes WHERE enabled=1 AND board_id=4').fetchone()
 if not route:return False
 post=db.execute('SELECT * FROM community_posts WHERE id=? AND deleted=0',(post_id,)).fetchone()
 if not post:return False
 scope=[route['board_id'],*[r['id'] for r in db.execute('SELECT id FROM community_boards WHERE parent_id=? AND archived=0',(route['board_id'],))]]
 if post['board_id'] not in scope:return False
 if db.execute('SELECT 1 FROM dshs_relay_seen WHERE post_id=?',(post_id,)).fetchone():return False
 relay_access(db,route['user_id'],post['board_id'],'post')
 db.execute("INSERT OR IGNORE INTO dshs_relay_outbox(post_id,state) VALUES(?,'queued')",(post_id,))
 return True

@router.get('')
def status(uid:int=Depends(native_kakao_user_id)):
 if not community.admin(uid):raise HTTPException(403,"관리자 권한이 필요합니다.")
 with connection() as db:
  r=db.execute('SELECT * FROM dshs_relay_state WHERE id=1').fetchone()
  route=db.execute('SELECT board_id FROM kakao_board_routes WHERE enabled=1 AND board_id=4').fetchone()
  categories=[dict(row) for row in db.execute('''SELECT c.category,b.id AS board_id,b.name FROM dshs_relay_categories c LEFT JOIN community_boards b ON b.id=c.board_id WHERE c.root_board_id=? ORDER BY c.category''',(route['board_id'],))] if route else []
  return {'configured':credentials_ready(),'health':dict(db.execute('SELECT * FROM dshs_relay_health WHERE id=1').fetchone() or {}),'state':dict(r) if r else None,'jobs':[dict(r) for r in db.execute('SELECT * FROM dshs_relay_outbox ORDER BY post_id DESC LIMIT 20')],'intervalSeconds':1800,'categories':categories}
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
 if not credentials_ready():return
 with connection() as db:
  route=db.execute('SELECT * FROM kakao_board_routes WHERE enabled=1 AND board_id=4').fetchone()
  if not route:return
  uid=route['user_id'];bid=route['board_id'];relay_access(db,uid,bid,'post')
  ensure_category_channels(db,bid)
  state=db.execute('SELECT * FROM dshs_relay_state WHERE id=1').fetchone()
  seen=[r[0] for r in db.execute('SELECT remote_id FROM dshs_relay_seen')]
 result=invoke({'command':'read','seen':seen,'baseline':not state})
 if not result.get('complete'):raise RuntimeError('DSHS 목록을 끝까지 읽지 못했습니다.')
 with connection() as db:
  relay_access(db,uid,bid,'post')
  if not state:
   db.executemany("INSERT OR IGNORE INTO dshs_relay_seen VALUES(?,NULL,'baseline')",[(id,) for id in result['ids']])
   scope=[bid,*[r['id'] for r in db.execute('SELECT id FROM community_boards WHERE parent_id=? AND archived=0',(bid,))]]
   marks=','.join('?' for _ in scope)
   maximum=db.execute(f'SELECT COALESCE(MAX(id),0) FROM community_posts WHERE board_id IN ({marks})',scope).fetchone()[0]
   db.execute('INSERT INTO dshs_relay_state(id,last_post_id,last_scan) VALUES(1,?,CURRENT_TIMESTAMP)',(maximum,));db.commit();return
  for post in result['posts']:
   if db.execute('SELECT 1 FROM dshs_relay_seen WHERE remote_id=?',(post['id'],)).fetchone():continue
   # Outbound provenance is explicit; never echo our own mirrored source link.
   scope=[bid,*[r['id'] for r in db.execute('SELECT id FROM community_boards WHERE parent_id=? AND archived=0',(bid,))]]
   if any(f'https://netaq.chobab.app/personal-project/calendar/boards?board={board_id}&post=' in post['text'] for board_id in scope):
    db.execute("INSERT OR IGNORE INTO dshs_relay_seen VALUES(?,NULL,'outbound')",(post['id'],));continue
   category=post.get('category') or '기타'
   target_board=category_board(db,bid,category)
   relay_access(db,uid,target_board,'post')
   nodes=[{'type':'paragraph','content':[{'type':'text','text':post['text'][:30000]}]}]
   for png in post.get('images',[]):
    content=base64.b64decode(png,validate=True)
    if len(content)>8*1024*1024 or not content.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('DSHS 이미지 형식 오류')
    asset=uuid.uuid4().hex;community.ROOT.mkdir(parents=True,exist_ok=True);target=community.ROOT/asset;created.append(target);target.write_bytes(content);target.chmod(0o600)
    db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(asset,uid,target_board,'첨부.png','image/png',len(content)))
    nodes.append({'type':'image','attrs':{'src':f'/api/personal/resources/{asset}','alt':'자료 첨부'}})
   for attachment in post.get('files',[]):
    content=base64.b64decode(attachment['data'],validate=True)
    if not content or len(content)>20*1024*1024:raise RuntimeError('DSHS 첨부 크기 제한')
    asset=uuid.uuid4().hex;name=Path(attachment['name']).name[:240] or '첨부파일'
    community.ROOT.mkdir(parents=True,exist_ok=True);target=community.ROOT/asset;created.append(target);target.write_bytes(content);target.chmod(0o600)
    db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(asset,uid,target_board,name,'application/octet-stream',len(content)))
    nodes.append({'type':'paragraph','content':[{'type':'text','text':name,'marks':[{'type':'link','attrs':{'href':f'/api/personal/resources/{asset}'}}]}]})
   document={'schemaVersion':2,'version':1,'documentId':uuid.uuid4().hex,'blocks':[],'richContent':{'type':'doc','content':nodes}}
   used=db.execute('SELECT COALESCE(SUM(size),0) FROM personal_resources WHERE user_id=?',(uid,)).fetchone()[0]
   if used>int(os.getenv('PERSONAL_RESOURCE_QUOTA_BYTES','1073741824')):raise RuntimeError('자료 저장 한도를 초과했습니다.')
   pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(target_board,uid,post['title'][:160],community.encode_document(document),post['text'])).lastrowid
   db.execute("INSERT INTO dshs_relay_seen VALUES(?,?,'imported')",(post['id'],pid))
   from . import kakao_board_sync
   kakao_board_sync.enqueue_post(db,pid)
  scope=[bid,*[r['id'] for r in db.execute('SELECT id FROM community_boards WHERE parent_id=? AND archived=0',(bid,))]]
  marks=','.join('?' for _ in scope)
  posts=db.execute(f'SELECT * FROM community_posts WHERE board_id IN ({marks}) AND id>? ORDER BY id',(*scope,state['last_post_id'])).fetchall()
  for p in posts:
   enqueue_post(db,p['id'])
   db.execute('UPDATE dshs_relay_state SET last_post_id=? WHERE id=1',(p['id'],))
  db.execute('UPDATE dshs_relay_state SET last_scan=CURRENT_TIMESTAMP,error=NULL WHERE id=1');db.commit()

def process_jobs():
 with connection() as db:
  route=db.execute('SELECT * FROM kakao_board_routes WHERE enabled=1 AND board_id=4').fetchone()
  jobs=db.execute("SELECT p.* FROM community_posts p JOIN dshs_relay_outbox o ON o.post_id=p.id WHERE o.state='queued' ORDER BY p.id LIMIT 1").fetchall()
 if not route:return
 uid,bid=route['user_id'],route['board_id']
 for p in jobs:
  with connection() as db:
   relay_access(db,uid,p['board_id'])
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
      if asset['board_id']!=p['board_id']:raise RuntimeError('게시판 첨부 권한 불일치')
      suffix=Path(asset['name']).suffix;target=Path(stage)/(rid+suffix);shutil.copyfile(community.ROOT/rid,target);files.append(str(target))
     category=category_for_board(db,bid,p['board_id'])
    result=invoke({'command':'publish','title':current['title'],'text':plain(json.loads(current['document'])),'category':category,'files':files})
   remote_id=result.get('url','').rstrip('/').rsplit('/',1)[-1]
   if not remote_id.isdigit():raise RuntimeError('원격 게시물 ID를 확인하지 못했습니다.')
   with connection() as db:
    db.execute("INSERT OR IGNORE INTO dshs_relay_seen(remote_id,post_id,state) VALUES(?,?,'outbound')",(remote_id,p['id']))
    db.execute("UPDATE dshs_relay_outbox SET state='succeeded',result=? WHERE post_id=?",(json.dumps(result),p['id']))
    if route['ack'] and result.get('url'):
     netaq_link=f'https://netaq.chobab.app/personal-project/calendar/boards?board={p["board_id"]}&post={p["id"]}'
     enqueue(db,uid,f'dshs-relay:{p["id"]}:ack',{'room':route['room'],'text':f'등록 완료\n{current["title"]}\nNETAQ: {netaq_link}\n디샵: {result["url"]}','resources':[],'route_id':route['id'],'post_id':p['id']})
    db.commit()
  except Exception as e:
   with connection() as db:db.execute('UPDATE dshs_relay_outbox SET result=? WHERE post_id=?',(str(e)[:500],p['id']));db.commit()
def loop():
 # Both the backend and the standalone launch agent may start; only one may scan or send.
 import fcntl
 lock_path=RUNTIME/'dshs-relay.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
 with lock_path.open('a') as leader:
  try:fcntl.flock(leader,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  threading.Thread(target=outbox_loop,daemon=True,name='dshs-outbox').start()
  while not stop.is_set():
   try:
    tick()
    with connection() as db:db.execute('INSERT OR REPLACE INTO dshs_relay_health(id,error,updated_at) VALUES(1,NULL,CURRENT_TIMESTAMP)');db.commit()
   except Exception as e:
    with connection() as db:db.execute('INSERT OR REPLACE INTO dshs_relay_health(id,error,updated_at) VALUES(1,?,CURRENT_TIMESTAMP)',(str(e)[:500],));db.commit()
   stop.wait(1800)

def outbox_loop():
 while not stop.wait(2):
  try:process_jobs()
  except Exception:logging.getLogger(__name__).exception('DSHS outbound job failed')
@router.on_event('startup')
def start():
 if os.getenv('DISABLE_DSHS_RELAY')=='1' or not credentials_ready():return
 stop.clear();threading.Thread(target=loop,daemon=True,name='dshs-relay').start()
@router.on_event('shutdown')
def shutdown():stop.set()

if __name__=='__main__':
 import signal
 signal.signal(signal.SIGTERM,lambda *_:stop.set())
 signal.signal(signal.SIGINT,lambda *_:stop.set())
 loop()
