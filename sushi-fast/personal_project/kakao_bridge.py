"""Owner-only Mac bridge; durable outbox, private inbox, explicit board publication.

Kakao UI automation is not a server API: only loaded messages can be observed.
A failed/uncertain send is never automatically retried, including after restart.
"""
import hashlib,json,os,re,shutil,subprocess,threading,time,uuid,tempfile
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from .db import connection,DB_PATH
from .router import native_kakao_user_id,require_native_kakao_origin
from . import native_kakao,community_v2 as community
router=APIRouter(prefix='/kakao-bridge',tags=['mac-kakao-bridge'])
BINARY=Path(__file__).resolve().parents[1]/'.runtime/kakao-bridge'
stop=threading.Event()

def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS kakao_bridge_sources(user_id INTEGER NOT NULL,room TEXT NOT NULL,mention TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,last_scan TEXT,error TEXT,PRIMARY KEY(user_id,room));
        CREATE TABLE IF NOT EXISTS kakao_bridge_inbox(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,room TEXT NOT NULL,fingerprint TEXT NOT NULL,text TEXT NOT NULL,metadata TEXT NOT NULL,photo_id TEXT,photo_error TEXT,published_post INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,room,fingerprint));
        CREATE TABLE IF NOT EXISTS kakao_bridge_outbox(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,idempotency_key TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,result TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,idempotency_key));
        ''')
        # A crash after a click may have delivered a message. Never replay it.
        db.execute("UPDATE kakao_bridge_outbox SET state='unknown',result=? WHERE state='running'",(json.dumps({'error':'서버가 재시작되어 전송 여부가 불명확합니다. 대화방을 직접 확인해주세요.'}),));db.commit()
init()

def invoke(command,**args):
    if not BINARY.is_file():raise RuntimeError('Mac 도우미가 설치되지 않았습니다. ops/build_kakao_bridge.sh를 실행해주세요.')
    result=subprocess.run([str(BINARY)],input=json.dumps({'command':command,**args}),text=True,capture_output=True,timeout=55)
    try:payload=json.loads(result.stdout)
    except ValueError:raise RuntimeError('Mac 도우미 응답을 확인하지 못했습니다.')
    return payload

def mention_matches(text,name):return bool(re.search(r'(?<![\w@])@'+re.escape(name)+r'(?=$|[\s,:;.!?\[\]()])',text))
def mentions(rows,name):
    for i,row in enumerate(rows):
        text=row.get('text','')
        if not mention_matches(text,name):continue
        photo=rows[i+1] if i+1<len(rows) and rows[i+1].get('photo') and not rows[i+1].get('newSender') else None
        # Unread counts change after every read; they are not message identity.
        meta=re.sub(r'^\s*\d+\s*','',row.get('metadata','')).strip()
        identity=json.dumps([row.get('date',''),meta,text],ensure_ascii=False)
        yield hashlib.sha256(identity.encode()).hexdigest(),row,photo

def scan(uid,room,mention):
    with native_kakao._send_lock:
        payload=invoke('read',room=room)
        if payload.get('error'):raise RuntimeError(payload['error'])
        for fingerprint,row,photo in mentions(payload.get('rows',[]),mention):
            with connection() as db:
                db.execute('INSERT OR IGNORE INTO kakao_bridge_inbox(id,user_id,room,fingerprint,text,metadata) VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,uid,room,fingerprint,row['text'],row.get('metadata','')))
                item=db.execute('SELECT * FROM kakao_bridge_inbox WHERE user_id=? AND room=? AND fingerprint=?',(uid,room,fingerprint)).fetchone();db.commit()
            if photo and not item['photo_id']:
                rid=uuid.uuid4().hex;community.ROOT.mkdir(parents=True,exist_ok=True);destination=community.ROOT/rid
                result=invoke('photo',room=room,index=photo['index'],expected=row['text'],output=str(destination))
                with connection() as db:
                    if result.get('saved') and destination.is_file():
                        destination.chmod(0o600)
                        db.execute('INSERT INTO personal_resources(id,user_id,name,mime,size) VALUES(?,?,?,?,?)',(rid,uid,'카카오톡 사진.png','image/png',destination.stat().st_size))
                        db.execute('UPDATE kakao_bridge_inbox SET photo_id=?,photo_error=NULL WHERE id=?',(rid,item['id']))
                    else:db.execute('UPDATE kakao_bridge_inbox SET photo_error=? WHERE id=?',(result.get('error','사진 수집 실패'),item['id']))
                    db.commit()
    with connection() as db:db.execute('UPDATE kakao_bridge_sources SET last_scan=CURRENT_TIMESTAMP,error=NULL WHERE user_id=? AND room=?',(uid,room));db.commit()

def process_job(job):
    with connection() as db:
        if not db.execute("UPDATE kakao_bridge_outbox SET state='running' WHERE id=? AND state='queued'",(job['id'],)).rowcount:return
        db.commit()
    state='unknown';result={};stage=tempfile.TemporaryDirectory(prefix='ondo-kakao-send-')
    try:
        payload=json.loads(job['payload']);files=[]
        with connection() as db:
            relay_board=None
            if payload.get('route_id'):
                from .kakao_board_sync import validate_job
                relay_board=validate_job(db,job,payload)
            for rid in payload['resources']:
                r=db.execute('SELECT * FROM personal_resources WHERE id=? AND board_id=?',(rid,relay_board)).fetchone() if relay_board else db.execute('SELECT * FROM personal_resources WHERE id=? AND user_id=?',(rid,job['user_id'])).fetchone()
                if not r:raise ValueError('첨부파일 접근 권한이 변경되었습니다.')
                if r['mime'] not in native_kakao.ALLOWED_IMAGE_TYPES or r['size']>8*1024*1024:raise ValueError('사진은 PNG/JPG/WebP, 장당 8MB까지 전송할 수 있습니다.')
                if not native_kakao._matches_image_signature(r['mime'],(community.ROOT/rid).read_bytes()):raise ValueError('사진 파일 형식이 올바르지 않습니다.')
                if r['board_id']:community.board_access(db,job['user_id'],r['board_id'])
                target=Path(stage.name)/(rid+native_kakao.ALLOWED_IMAGE_TYPES[r['mime']]);shutil.copyfile(community.ROOT/rid,target);files.append(str(target))
        with native_kakao._send_lock:
            opened=invoke('search',room=payload['room'])
            result=opened if opened.get('error') else invoke('send',room=payload['room'],text=payload['text'],files=files)
        state='succeeded' if result.get('sent') else 'unknown' if result.get('uncertain') else 'failed'
    except Exception as e:result={'error':str(e)}
    stage.cleanup()
    with connection() as db:db.execute('UPDATE kakao_bridge_outbox SET state=?,result=? WHERE id=?',(state,json.dumps(result),job['id']));db.commit()

def loop():
    last=0
    while not stop.wait(2):
        with connection() as db:jobs=db.execute("SELECT * FROM kakao_bridge_outbox WHERE state='queued' ORDER BY created_at LIMIT 1").fetchall()
        for job in jobs:process_job(job)
        if time.monotonic()-last<30:continue
        last=time.monotonic()
        try:
            from .kakao_board_sync import tick
            tick()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Kakao relay scan failed')
        with connection() as db:sources=db.execute('SELECT * FROM kakao_bridge_sources WHERE enabled=1').fetchall()
        for source in sources:
            if stop.is_set():break
            try:scan(source['user_id'],source['room'],source['mention'])
            except Exception as e:
                with connection() as db:db.execute('UPDATE kakao_bridge_sources SET error=? WHERE user_id=? AND room=?',(str(e),source['user_id'],source['room']));db.commit()
@router.on_event('startup')
def start():
    if os.getenv('DISABLE_KAKAO_BRIDGE')=='1':return
    stop.clear();threading.Thread(target=loop,daemon=True,name='kakao-bridge').start()
@router.on_event('shutdown')
def shutdown():stop.set()
@router.post('/probe')
def probe(request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    return invoke('status')

class Source(BaseModel):
    room:str=Field(min_length=1,max_length=100)
    mention:str=Field(default='김지후',min_length=1,max_length=40)
    enabled:bool=False
class Send(BaseModel):
    room:str=Field(min_length=1,max_length=100)
    text:str=Field(default='',max_length=10000)
    resources:list[str]=Field(default_factory=list,max_length=5)
    idempotency_key:str=Field(min_length=8,max_length=100)
class Publish(BaseModel):
    board_id:int
    title:str=Field(min_length=1,max_length=160)
@router.get('')
def status(uid:int=Depends(native_kakao_user_id)):
    with connection() as db:return {'installed':BINARY.is_file(),'sources':[dict(r) for r in db.execute('SELECT * FROM kakao_bridge_sources WHERE user_id=?',(uid,))],'jobs':[dict(r) for r in db.execute('SELECT id,state,result,created_at FROM kakao_bridge_outbox WHERE user_id=? ORDER BY created_at DESC LIMIT 20',(uid,))],'inbox':[dict(r) for r in db.execute('SELECT * FROM kakao_bridge_inbox WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(uid,))]}

class BoardRelay(BaseModel):
    board_id:int=Field(gt=0)
    room:str='대학생 자료 공유방'
    mention:str=Field(default='김지후',min_length=1,max_length=40)
    enabled:bool=False
    ack:bool=True
@router.get('/board-relay')
def board_relay_status(uid:int=Depends(native_kakao_user_id)):
    from .kakao_board_sync import summary
    return summary(uid)
@router.put('/board-relay')
def board_relay(data:BoardRelay,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    from .kakao_board_sync import configure
    return configure(uid,data.board_id,data.room,data.mention,data.enabled,data.ack)
@router.put('/source')
def source(data:Source,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    with connection() as db:db.execute('INSERT INTO kakao_bridge_sources(user_id,room,mention,enabled) VALUES(?,?,?,?) ON CONFLICT(user_id,room) DO UPDATE SET mention=excluded.mention,enabled=excluded.enabled',(uid,data.room.strip(),data.mention.strip(),int(data.enabled)));db.commit()
    return {'saved':True}
@router.post('/search')
def search(data:Source,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    with native_kakao._send_lock:return invoke('search',room=data.room)
@router.post('/scan')
def scan_now(data:Source,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    try:scan(uid,data.room,data.mention)
    except Exception as e:raise HTTPException(409,str(e))
    return status(uid)
@router.post('/send')
def send(data:Send,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    if not data.text.strip() and not data.resources:raise HTTPException(400,'글 또는 사진을 선택해주세요.')
    payload=json.dumps(data.model_dump(exclude={'idempotency_key'}),sort_keys=True)
    with connection() as db:
        for rid in data.resources:
            r=db.execute('SELECT * FROM personal_resources WHERE id=? AND user_id=?',(rid,uid)).fetchone()
            if not r or r['mime'] not in native_kakao.ALLOWED_IMAGE_TYPES or r['size']>8*1024*1024:raise HTTPException(400,'내 자료의 PNG/JPG/WebP 사진(8MB 이하)을 선택해주세요.')
            if not native_kakao._matches_image_signature(r['mime'],(community.ROOT/rid).read_bytes()):raise HTTPException(400,'이미지 형식이 올바르지 않습니다.')
            if r['board_id']:community.board_access(db,uid,r['board_id'])
        old=db.execute('SELECT * FROM kakao_bridge_outbox WHERE user_id=? AND idempotency_key=?',(uid,data.idempotency_key)).fetchone()
        if old:
            if old['payload']!=payload:raise HTTPException(409,'같은 전송 키에 다른 내용을 사용할 수 없습니다.')
            return {'id':old['id'],'state':old['state']}
        jid=uuid.uuid4().hex;db.execute("INSERT INTO kakao_bridge_outbox(id,user_id,idempotency_key,payload,state) VALUES(?,?,?,?,'queued')",(jid,uid,data.idempotency_key,payload));db.commit()
    return {'id':jid,'state':'queued'}
@router.post('/inbox/{iid}/publish')
def publish(iid:str,data:Publish,request:Request,uid:int=Depends(native_kakao_user_id)):
    require_native_kakao_origin(request)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');community.board_access(db,uid,data.board_id,'post')
        row=db.execute('SELECT * FROM kakao_bridge_inbox WHERE id=? AND user_id=?',(iid,uid)).fetchone()
        if not row:raise HTTPException(404,'수집한 글을 찾지 못했습니다.')
        if row['published_post']:return {'id':row['published_post']}
        nodes=[{'type':'paragraph','content':[{'type':'text','text':row['text']}]}]
        if row['photo_id']:
            old=db.execute('SELECT * FROM personal_resources WHERE id=? AND user_id=?',(row['photo_id'],uid)).fetchone()
            if old:
                rid=uuid.uuid4().hex;shutil.copyfile(community.ROOT/old['id'],community.ROOT/rid)
                db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(rid,uid,data.board_id,old['name'],old['mime'],old['size']))
                nodes.append({'type':'image','attrs':{'src':f'/api/personal/resources/{rid}','alt':'카카오톡에서 공유한 사진'}})
        doc={'version':1,'schemaVersion':2,'documentId':uuid.uuid4().hex,'blocks':[],'richContent':{'type':'doc','content':nodes}}
        pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(data.board_id,uid,data.title,json.dumps(doc),row['text'])).lastrowid
        db.execute('UPDATE kakao_bridge_inbox SET published_post=? WHERE id=?',(pid,iid));db.commit()
    return {'id':pid}
