"""Revocable, expiring board-only credentials. Never accepted by calendar/Aura APIs."""
import hashlib,json,secrets,time,uuid
from dataclasses import dataclass
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Header,Query,Response
from pydantic import BaseModel,Field
from .db import connection
from .router import current_user_id
from . import community_v2 as c
router=APIRouter(prefix='/board-api',tags=['board-automation'])
with connection() as db:
    db.executescript('''
    CREATE TABLE IF NOT EXISTS board_api_tokens(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,digest TEXT UNIQUE NOT NULL,board_ids TEXT NOT NULL,scopes TEXT NOT NULL,expires_at INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS board_api_limits(token_id TEXT NOT NULL,minute INTEGER NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(token_id,minute));
    CREATE TABLE IF NOT EXISTS board_api_requests(user_id INTEGER NOT NULL,operation TEXT NOT NULL,request_key TEXT NOT NULL,digest TEXT NOT NULL,result TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,operation,request_key));
    ''');db.commit()
class TokenCreate(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    board_ids:list[int]=Field(min_length=1,max_length=30)
    scopes:list[Literal['read','post','comment','upload']]=Field(default_factory=lambda:['read','post','upload'],min_length=1,max_length=4)
    expires_days:int=Field(default=30,ge=1,le=90)
@dataclass
class Principal:
    uid:int
    boards:list[int]
    scopes:list[str]
def principal(request:Request):
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer '):raise HTTPException(401,'Bearer API 키가 필요합니다.')
    digest=hashlib.sha256(header[7:].encode()).hexdigest();minute=int(time.time())//60
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM board_api_tokens WHERE digest=? AND revoked=0 AND expires_at>?',(digest,int(time.time()))).fetchone()
        if not r:raise HTTPException(401,'만료되었거나 폐기된 API 키입니다.')
        count=db.execute('SELECT count FROM board_api_limits WHERE token_id=? AND minute=?',(r['id'],minute)).fetchone()
        if count and count[0]>=120:raise HTTPException(429,'분당 요청 한도를 초과했습니다.',headers={'Retry-After':'60'})
        db.execute('INSERT INTO board_api_limits VALUES(?,?,1) ON CONFLICT(token_id,minute) DO UPDATE SET count=count+1',(r['id'],minute))
        db.execute('DELETE FROM board_api_limits WHERE minute<?',(minute-2,));db.commit()
        return Principal(r['user_id'],json.loads(r['board_ids']),json.loads(r['scopes']))
def allowed(p,bid,scope):
    if bid not in p.boards or scope not in p.scopes:raise HTTPException(403,'API 키의 게시판 또는 작업 범위를 벗어났습니다.')
    with connection() as db:c.board_access(db,p.uid,bid,'post' if scope=='upload' else scope)
@router.get('/tokens')
def tokens(response:Response,uid:int=Depends(current_user_id)):
    response.headers['Cache-Control']='no-store'
    with connection() as db:return [dict(r) for r in db.execute('SELECT id,name,board_ids,scopes,expires_at,revoked,created_at FROM board_api_tokens WHERE user_id=? ORDER BY created_at DESC',(uid,))]
@router.post('/tokens',dependencies=[Depends(c.write_origin)])
def create_token(data:TokenCreate,response:Response,uid:int=Depends(current_user_id)):
    response.headers['Cache-Control']='no-store'
    with connection() as db:
        for bid in data.board_ids:
            for scope in data.scopes:c.board_access(db,uid,bid,'post' if scope=='upload' else scope)
        token='netaq_'+secrets.token_urlsafe(32);tid=uuid.uuid4().hex;expires=int(time.time())+data.expires_days*86400
        db.execute('INSERT INTO board_api_tokens(id,user_id,name,digest,board_ids,scopes,expires_at) VALUES(?,?,?,?,?,?,?)',(tid,uid,data.name,hashlib.sha256(token.encode()).hexdigest(),json.dumps(sorted(set(data.board_ids))),json.dumps(sorted(set(data.scopes))),expires));db.commit()
    return {'id':tid,'token':token,'expires_at':expires}
@router.delete('/tokens/{tid}',dependencies=[Depends(c.write_origin)])
def revoke(tid:str,uid:int=Depends(current_user_id)):
    with connection() as db:db.execute('UPDATE board_api_tokens SET revoked=1 WHERE id=? AND user_id=?',(tid,uid));db.commit()
    return {'revoked':True}
@router.get('/boards/{bid}/posts')
def posts(bid:int,q:str=Query('',max_length=120),page:int=Query(1,ge=1),p:Principal=Depends(principal)):
    allowed(p,bid,'read');return c.posts(bid,q,page,False,p.uid)

def idempotency(db,p,operation,key,data):
    if not key or not 8<=len(key)<=120:raise HTTPException(400,'8~120자의 Idempotency-Key 헤더가 필요합니다.')
    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    old=db.execute('SELECT * FROM board_api_requests WHERE user_id=? AND operation=? AND request_key=?',(p.uid,operation,key)).fetchone()
    if old and old['digest']!=digest:raise HTTPException(409,'같은 Idempotency-Key의 내용이 달라졌습니다.')
    return digest,json.loads(old['result']) if old else None
@router.post('/boards/{bid}/posts')
def post(bid:int,data:c.PostWrite,key:str|None=Header(None,alias='Idempotency-Key'),p:Principal=Depends(principal)):
    allowed(p,bid,'post');encoded=c.encode_document(data.document)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');digest,old=idempotency(db,p,f'post:{bid}',key,data.model_dump())
        if old:return old
        c.board_access(db,p.uid,bid,'post');c.validate_assets(db,p.uid,data.document,bid)
        pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(bid,p.uid,data.title,encoded,c.document_text(data.document))).lastrowid
        result={'id':pid,'board_id':bid,'revision':1,'url':f'/personal-project/calendar/boards?board={bid}&post={pid}'}
        db.execute('INSERT INTO board_api_requests(user_id,operation,request_key,digest,result) VALUES(?,?,?,?,?)',(p.uid,f'post:{bid}',key,digest,json.dumps(result)));db.commit()
    return result

def post_board(pid,p,scope):
    with connection() as db:
        row=db.execute('SELECT board_id FROM community_posts WHERE id=?',(pid,)).fetchone()
        if not row:raise HTTPException(404,'글을 찾을 수 없습니다.')
        allowed(p,row[0],scope)
    return row[0]
@router.get('/posts/{pid}')
def detail(pid:int,p:Principal=Depends(principal)):
    post_board(pid,p,'read');return c.post_detail(pid,p.uid)
@router.put('/posts/{pid}')
def edit(pid:int,data:c.PostWrite,p:Principal=Depends(principal)):
    post_board(pid,p,'post');return c.edit_post(pid,data,p.uid)
@router.post('/posts/{pid}/comments')
def comment(pid:int,data:c.CommentWrite,key:str|None=Header(None,alias='Idempotency-Key'),p:Principal=Depends(principal)):
    post_board(pid,p,'comment')
    if not data.content.strip():raise HTTPException(400,'댓글을 입력해주세요.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');digest,old=idempotency(db,p,f'comment:{pid}',key,data.model_dump())
        if old:return old
        post,b=c.get_post(db,p.uid,pid);c.board_access(db,p.uid,post['board_id'],'comment')
        if data.parent_id and not db.execute('SELECT 1 FROM community_comments WHERE id=? AND post_id=?',(data.parent_id,pid)).fetchone():raise HTTPException(400,'답글 대상을 확인해주세요.')
        cid=db.execute('INSERT INTO community_comments(post_id,author_id,parent_id,content) VALUES(?,?,?,?)',(pid,p.uid,data.parent_id,data.content)).lastrowid
        result={'id':cid,'post_id':pid};db.execute('INSERT INTO board_api_requests(user_id,operation,request_key,digest,result) VALUES(?,?,?,?,?)',(p.uid,f'comment:{pid}',key,digest,json.dumps(result)));db.commit()
    return result
@router.post('/boards/{bid}/resources')
async def upload(bid:int,request:Request,name:str=Query(...,min_length=1,max_length=240),p:Principal=Depends(principal)):
    allowed(p,bid,'upload');return await c.upload(request,name,bid,p.uid)
@router.get('/resources/{rid}')
def resource(rid:str,p:Principal=Depends(principal)):
    with connection() as db:
        row=db.execute('SELECT board_id FROM personal_resources WHERE id=?',(rid,)).fetchone()
        if not row or not row[0]:raise HTTPException(403,'이 API 키로 개인 자료를 열 수 없습니다.')
        allowed(p,row[0],'read')
    return c.download(rid,p.uid)
