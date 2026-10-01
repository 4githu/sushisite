"""Boards, revisioned documents and access-controlled originals shared by editors."""
import json
import os
import re
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool
from .db import connection, DB_PATH
from .router import current_user_id

def write_origin(request:Request):
    if request.method in ('GET','HEAD','OPTIONS'):return
    origin=request.headers.get('origin')
    allowed={'https://chobab.app','https://aura.chobab.app','http://localhost:5173','http://127.0.0.1:5174'}
    if (origin and origin.rstrip('/') not in allowed) or request.headers.get('sec-fetch-site')=='cross-site':
        raise HTTPException(403,'허용된 사이트에서 요청해주세요.')
router = APIRouter(prefix='', tags=['documents-and-boards'],dependencies=[Depends(write_origin)])
ROOT = Path(os.getenv('PERSONAL_RESOURCE_ROOT', str(DB_PATH.parent / 'resources')))
ACTIONS = {'read','post','comment','create','manage'}

def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS community_boards(id INTEGER PRIMARY KEY, name TEXT NOT NULL, realm TEXT NOT NULL DEFAULT 'other', school TEXT NOT NULL DEFAULT '',department TEXT NOT NULL DEFAULT '', creator_id INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO community_boards(id,name,realm) VALUES(1,'메인 게시판','main');
        CREATE TABLE IF NOT EXISTS community_acl(user_id INTEGER NOT NULL,scope TEXT NOT NULL,action TEXT NOT NULL,allowed INTEGER NOT NULL,PRIMARY KEY(user_id,scope,action));
        CREATE TABLE IF NOT EXISTS community_posts(id INTEGER PRIMARY KEY,board_id INTEGER NOT NULL REFERENCES community_boards(id),author_id INTEGER NOT NULL,title TEXT NOT NULL,document TEXT NOT NULL,plain TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,pinned INTEGER NOT NULL DEFAULT 0,deleted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,legacy_id INTEGER UNIQUE);
        CREATE INDEX IF NOT EXISTS community_posts_list ON community_posts(board_id,deleted,pinned DESC,id DESC);
        CREATE TABLE IF NOT EXISTS community_comments(id INTEGER PRIMARY KEY,post_id INTEGER NOT NULL REFERENCES community_posts(id),author_id INTEGER NOT NULL,parent_id INTEGER REFERENCES community_comments(id),content TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS community_comments_post ON community_comments(post_id,id);
        CREATE TABLE IF NOT EXISTS personal_resources(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,board_id INTEGER REFERENCES community_boards(id),name TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS personal_documents(user_id INTEGER NOT NULL,document_key TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,document_key));
        CREATE TABLE IF NOT EXISTS personal_document_history(user_id INTEGER NOT NULL,document_key TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,document_key,revision));
        ''')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_board'").fetchone():
            for old in db.execute('SELECT * FROM student_board WHERE id NOT IN (SELECT legacy_id FROM community_posts WHERE legacy_id IS NOT NULL)').fetchall():
                board=db.execute('SELECT id FROM community_boards WHERE school=? AND department=?',(old['school'],old['department'])).fetchone()
                bid=board['id'] if board else db.execute("INSERT INTO community_boards(name,school,department) VALUES(?,?,?)",(old['department'],old['school'],old['department'])).lastrowid
                doc={'version':1,'documentId':f"legacy-{old['id']}",'blocks':[{'id':f"legacy-{old['id']}",'type':'paragraph','children':[{'type':'text','text':old['content']}]}]}
                db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain,deleted,created_at,legacy_id) VALUES(?,?,?,?,?,?,?,?)',(bid,old['author_id'],old['title'],json.dumps(doc),old['content'],old['deleted'],old['created_at'],old['id']))
        db.commit()
init()

def author_names(rows):
    # Resolve only public display names, in one query per response.
    from auth.userdb import get_connection
    ids=list({r['author_id'] for r in rows});names={}
    if ids:
        with get_connection() as db:names={r['id']:r['name'] for r in db.execute('SELECT id,name FROM users WHERE id IN ('+','.join('?' for _ in ids)+')',ids)}
    return [dict(r)|{'author_name':names.get(r['author_id']) or f"회원 {r['author_id']}"} for r in rows]

def admin(uid): return str(uid) in os.getenv('COMMUNITY_ADMINS',os.getenv('STUDENT_CURRICULUM_EDITORS','')).split(',')
def permission(db,uid,board,action):
    flags=[r[0] for r in db.execute('SELECT allowed FROM community_acl WHERE user_id=? AND action=? AND scope IN (?,?)',(uid,action,board['realm'],f"board:{board['id']}"))]
    if 0 in flags:return False
    if admin(uid):return True
    if board['school']:
        p=db.execute('SELECT school,department,is_student FROM student_profiles WHERE user_id=?',(uid,)).fetchone()
        if not p or not p['is_student'] or (p['school'],p['department'])!=(board['school'],board['department']):return False
    flags=[r[0] for r in db.execute('SELECT allowed FROM community_acl WHERE user_id=? AND action=? AND scope IN (?,?)',(uid,action,board['realm'],f"board:{board['id']}"))]
    if 0 in flags:return False
    if flags:return True
    return action in ('read','post','comment') or (action=='manage' and board['creator_id']==uid)
def board_access(db,uid,bid,action='read'):
    b=db.execute('SELECT * FROM community_boards WHERE id=?',(bid,)).fetchone()
    if not b or not permission(db,uid,b,'read') or not permission(db,uid,b,action):raise HTTPException(403,'이 게시판의 접근 권한이 없습니다.')
    return b

def encode_document(value):
    encoded=json.dumps(value,ensure_ascii=False)
    if len(encoded.encode('utf-8'))>500000:raise HTTPException(413,'문서는 500KB 이하로 저장해주세요.')
    return encoded

def document_text(value):
    if isinstance(value,dict):
        if value.get('richContent'):return document_text(value['richContent'])
        if isinstance(value.get('text'),str):return value['text']
        return ' '.join(document_text(v) for k,v in value.items() if k in ('blocks','children','content','rows'))
    if isinstance(value,list):return ' '.join(document_text(v) for v in value)
    return ''

def validate_assets(db,uid,document,bid=None):
    for resource in set(re.findall(r'/api/personal/resources/([a-f0-9]{32})',json.dumps(document))):
        row=db.execute('SELECT * FROM personal_resources WHERE id=?',(resource,)).fetchone()
        if not row:raise HTTPException(400,'첨부파일을 찾을 수 없습니다.')
        if bid is not None and row['board_id']!=bid:raise HTTPException(400,'이 게시판에 업로드한 파일을 선택해주세요.')
        if row['board_id']:board_access(db,uid,row['board_id'])
        elif row['user_id']!=uid:raise HTTPException(403,'다른 사람의 비공개 파일입니다.')

class BoardCreate(BaseModel):
    name:str=Field(min_length=1,max_length=80)
class ACL(BaseModel):
    user_id:int=Field(gt=0)
    scope:str=Field(pattern=r'^(main|other|board:[1-9][0-9]*)$')
    action:Literal['read','post','comment','create','manage']
    allowed:bool | None
class PostWrite(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    document:dict=Field(default_factory=dict)
    revision:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def trim(self):
        self.title=self.title.strip()
        if not self.title:raise ValueError('제목을 입력해주세요.')
        return self
class PostState(BaseModel):
    deleted:bool | None=None
    pinned:bool | None=None
class CommentWrite(BaseModel):
    content:str=Field(min_length=1,max_length=10000)
    parent_id:int | None=None
class DocumentWrite(BaseModel):
    data:dict
    revision:int=Field(ge=0)

@router.get('/boards')
def boards(uid:int=Depends(current_user_id)):
    with connection() as db:
        result=[dict(b)|{'permissions':{a:permission(db,uid,b,a) for a in ACTIONS}} for b in db.execute('SELECT * FROM community_boards ORDER BY id') if permission(db,uid,b,'read')]
        return {'boards':result,'canAdmin':admin(uid),'canCreate':admin(uid) or bool(db.execute("SELECT 1 FROM community_acl WHERE user_id=? AND scope='other' AND action='create' AND allowed=1",(uid,)).fetchone())}
@router.post('/boards')
def create_board(data:BoardCreate,uid:int=Depends(current_user_id)):
    if not boards(uid)['canCreate']:raise HTTPException(403,'게시판 생성 권한이 필요합니다.')
    with connection() as db:
        bid=db.execute('INSERT INTO community_boards(name,creator_id) VALUES(?,?)',(data.name.strip(),uid)).lastrowid;db.commit()
    return {'id':bid}
@router.get('/boards/permissions')
def permissions(uid:int=Depends(current_user_id)):
    if not admin(uid):raise HTTPException(403,'관리자 권한이 필요합니다.')
    with connection() as db:return [dict(r) for r in db.execute('SELECT * FROM community_acl ORDER BY user_id,scope,action')]
@router.put('/boards/permissions')
def set_permission(data:ACL,uid:int=Depends(current_user_id)):
    if not admin(uid):raise HTTPException(403,'관리자 권한이 필요합니다.')
    with connection() as db:
        if data.allowed is None:db.execute('DELETE FROM community_acl WHERE user_id=? AND scope=? AND action=?',(data.user_id,data.scope,data.action))
        else:db.execute('INSERT OR REPLACE INTO community_acl VALUES(?,?,?,?)',(data.user_id,data.scope,data.action,int(data.allowed)))
        db.commit()
    return {'saved':True}
@router.get('/boards/{bid}/posts')
def posts(bid:int,q:str=Query('',max_length=120),page:int=Query(1,ge=1),deleted:bool=False,uid:int=Depends(current_user_id)):
    with connection() as db:
        b=board_access(db,uid,bid)
        if deleted and not permission(db,uid,b,'manage'):raise HTTPException(403,'관리 권한이 필요합니다.')
        args=(bid,int(deleted),'%'+q+'%','%'+q+'%')
        where='board_id=? AND deleted=? AND (title LIKE ? OR plain LIKE ?)'
        total=db.execute('SELECT count(*) FROM community_posts WHERE '+where,args).fetchone()[0]
        rows=db.execute('SELECT id,title,author_id,pinned,revision,created_at,updated_at,(SELECT count(*) FROM community_comments c WHERE c.post_id=p.id AND c.deleted=0) AS comments FROM community_posts p WHERE '+where+' ORDER BY pinned DESC,id DESC LIMIT 30 OFFSET ?',(*args,(page-1)*30)).fetchall()
        return {'posts':author_names(rows),'total':total,'page':page}
@router.post('/boards/{bid}/posts')
def create_post(bid:int,data:PostWrite,uid:int=Depends(current_user_id)):
    encoded=encode_document(data.document)
    with connection() as db:
        board_access(db,uid,bid,'post');validate_assets(db,uid,data.document,bid)
        pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(bid,uid,data.title,encoded,document_text(data.document))).lastrowid;db.commit()
    return {'id':pid}
def get_post(db,uid,pid,include_deleted=False):
    p=db.execute('SELECT * FROM community_posts WHERE id=?',(pid,)).fetchone()
    if not p:raise HTTPException(404,'글을 찾을 수 없습니다.')
    b=board_access(db,uid,p['board_id'])
    if p['deleted'] and not (include_deleted and permission(db,uid,b,'manage')):raise HTTPException(404,'삭제된 글입니다.')
    return p,b
@router.get('/boards/posts/{pid}')
def post_detail(pid:int,uid:int=Depends(current_user_id)):
    with connection() as db:
        p,b=get_post(db,uid,pid)
        comments=[dict(r)|{'canDelete':r['author_id']==uid or permission(db,uid,b,'manage')} for r in db.execute("SELECT id,author_id,parent_id,CASE WHEN deleted=1 THEN '삭제된 댓글입니다.' ELSE content END AS content,deleted,created_at FROM community_comments WHERE post_id=? ORDER BY id",(pid,))]
        return dict(p)|{'document':json.loads(p['document']),'comments':author_names(comments),'author_name':author_names([p])[0]['author_name'],'canEdit':p['author_id']==uid or permission(db,uid,b,'manage'),'canManage':permission(db,uid,b,'manage'),'canComment':permission(db,uid,b,'comment')}
@router.put('/boards/posts/{pid}')
def edit_post(pid:int,data:PostWrite,uid:int=Depends(current_user_id)):
    encoded=encode_document(data.document)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');p,b=get_post(db,uid,pid)
        if not permission(db,uid,b,'post') or not (p['author_id']==uid or permission(db,uid,b,'manage')):raise HTTPException(403,'수정 권한이 없습니다.')
        if p['revision']!=data.revision:raise HTTPException(409,'글이 변경되었습니다. 작성 내용을 보존한 뒤 최신 글을 확인해주세요.')
        validate_assets(db,uid,data.document,p['board_id'])
        db.execute('INSERT OR IGNORE INTO personal_document_history VALUES(?,?,?,?,CURRENT_TIMESTAMP)',(p['author_id'],f'post:{pid}',p['revision'],p['document']))
        db.execute('UPDATE community_posts SET title=?,document=?,plain=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',(data.title,encoded,document_text(data.document),pid));db.commit()
    return post_detail(pid,uid)
@router.patch('/boards/posts/{pid}')
def post_state(pid:int,data:PostState,uid:int=Depends(current_user_id)):
    with connection() as db:
        p,b=get_post(db,uid,pid,True);manager=permission(db,uid,b,'manage')
        if not manager and p['author_id']!=uid:raise HTTPException(403,'관리 권한이 없습니다.')
        if data.pinned is not None and not manager:raise HTTPException(403,'공지는 관리자만 지정할 수 있습니다.')
        db.execute('UPDATE community_posts SET deleted=?,pinned=? WHERE id=?',(int(data.deleted) if data.deleted is not None else p['deleted'],int(data.pinned) if data.pinned is not None else p['pinned'],pid));db.commit()
    return {'saved':True}
@router.post('/boards/posts/{pid}/comments')
def create_comment(pid:int,data:CommentWrite,uid:int=Depends(current_user_id)):
    if not data.content.strip():raise HTTPException(400,'댓글 내용을 입력해주세요.')
    with connection() as db:
        p,b=get_post(db,uid,pid);board_access(db,uid,p['board_id'],'comment')
        if data.parent_id and not db.execute('SELECT 1 FROM community_comments WHERE id=? AND post_id=?',(data.parent_id,pid)).fetchone():raise HTTPException(400,'답글 대상을 확인해주세요.')
        db.execute('INSERT INTO community_comments(post_id,author_id,parent_id,content) VALUES(?,?,?,?)',(pid,uid,data.parent_id,data.content));db.commit()
    return post_detail(pid,uid)
@router.delete('/boards/comments/{cid}')
def delete_comment(cid:int,uid:int=Depends(current_user_id)):
    with connection() as db:
        c=db.execute('SELECT * FROM community_comments WHERE id=?',(cid,)).fetchone()
        if not c:raise HTTPException(404,'댓글을 찾을 수 없습니다.')
        _,b=get_post(db,uid,c['post_id'])
        if c['author_id']!=uid and not permission(db,uid,b,'manage'):raise HTTPException(403,'삭제 권한이 없습니다.')
        db.execute('UPDATE community_comments SET deleted=1 WHERE id=?',(cid,));db.commit()
    return {'saved':True}

@router.post('/resources')
async def upload(request:Request,name:str=Query(...,min_length=1,max_length=240),board_id:int|None=None,uid:int=Depends(current_user_id)):
    if board_id:
        with connection() as db:board_access(db,uid,board_id,'post')
    resource=uuid.uuid4().hex;ROOT.mkdir(parents=True,exist_ok=True);path=ROOT/resource;size=0
    mime=request.headers.get('content-type','application/octet-stream').split(';')[0]
    try:
        with path.open('xb') as f:
            async for chunk in request.stream():
                size+=len(chunk)
                if size>50*1024*1024:raise HTTPException(413,'파일은 50MB 이하로 올려주세요.')
                await run_in_threadpool(f.write,chunk)
        if not size:raise HTTPException(400,'빈 파일입니다.')
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if board_id:board_access(db,uid,board_id,'post')
            used=db.execute('SELECT COALESCE(SUM(size),0) FROM personal_resources WHERE user_id=?',(uid,)).fetchone()[0]
            if used+size>int(os.getenv('PERSONAL_RESOURCE_QUOTA_BYTES','1073741824')):raise HTTPException(413,'자료 저장 한도(기본 1GB)를 초과했습니다.')
            db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(resource,uid,board_id,Path(name).name,mime,size));db.commit()
    except BaseException:
        path.unlink(missing_ok=True);raise
    return {'id':resource,'name':Path(name).name,'mimeType':mime,'byteSize':size,'url':f'/api/personal/resources/{resource}'}
def resource_access(db,uid,rid):
    r=db.execute('SELECT * FROM personal_resources WHERE id=?',(rid,)).fetchone()
    if not r:raise HTTPException(404,'자료를 찾을 수 없습니다.')
    if r['board_id']:board_access(db,uid,r['board_id'])
    elif r['user_id']!=uid:raise HTTPException(403,'비공개 자료입니다.')
    return r
@router.get('/resources')
def resources(uid:int=Depends(current_user_id)):
    with connection() as db:return [dict(r)|{'mimeType':r['mime'],'byteSize':r['size'],'url':f"/api/personal/resources/{r['id']}"} for r in db.execute('SELECT * FROM personal_resources WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(uid,))]
@router.get('/resources/{rid}')
def download(rid:str,uid:int=Depends(current_user_id)):
    with connection() as db:r=resource_access(db,uid,rid)
    inline=r['mime'] in ('image/png','image/jpeg','image/webp','image/gif','application/pdf')
    return FileResponse(ROOT/rid,media_type=r['mime'] if inline else 'application/octet-stream',filename=r['name'],content_disposition_type='inline' if inline else 'attachment',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-cache','Content-Security-Policy':"default-src 'none'; sandbox"})
@router.get('/documents/{key}')
def document(key:str,uid:int=Depends(current_user_id)):
    with connection() as db:
        r=db.execute('SELECT * FROM personal_documents WHERE user_id=? AND document_key=?',(uid,key)).fetchone()
        return {'data':json.loads(r['data']) if r else None,'revision':r['revision'] if r else 0}
@router.put('/documents/{key}')
def save_document(key:str,data:DocumentWrite,uid:int=Depends(current_user_id)):
    if len(key)>160:raise HTTPException(400,'문서 이름이 너무 깁니다.')
    encoded=encode_document(data.data)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT * FROM personal_documents WHERE user_id=? AND document_key=?',(uid,key)).fetchone()
        if (old['revision'] if old else 0)!=data.revision:raise HTTPException(409,'다른 화면에서 문서가 변경되었습니다. 현재 내용을 복사하고 최신 문서를 확인해주세요.')
        validate_assets(db,uid,data.data)
        if old:db.execute('INSERT OR IGNORE INTO personal_document_history(user_id,document_key,revision,data) VALUES(?,?,?,?)',(uid,key,old['revision'],old['data']))
        db.execute('INSERT INTO personal_documents(user_id,document_key,revision,data) VALUES(?,?,?,?) ON CONFLICT(user_id,document_key) DO UPDATE SET revision=excluded.revision,data=excluded.data,updated_at=CURRENT_TIMESTAMP',(uid,key,data.revision+1,encoded));db.commit()
    return {'revision':data.revision+1}
@router.get('/documents/{key}/history')
def document_history(key:str,uid:int=Depends(current_user_id)):
    with connection() as db:return [dict(r)|{'data':json.loads(r['data'])} for r in db.execute('SELECT revision,data,created_at FROM personal_document_history WHERE user_id=? AND document_key=? ORDER BY revision DESC LIMIT 100',(uid,key))]

with connection() as db:
    db.execute('CREATE TABLE IF NOT EXISTS curriculum_structured_versions(rule_id TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,author_id INTEGER NOT NULL,source_version TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(rule_id,revision))');db.commit()

@router.get('/student/rules/{rule_id}/versions')
def rule_versions(rule_id:str,uid:int=Depends(current_user_id)):
    from .snu_catalog import curriculum
    official=curriculum(rule_id)
    with connection() as db:row=db.execute('SELECT * FROM curriculum_structured_versions WHERE rule_id=? ORDER BY revision DESC LIMIT 1',(rule_id,)).fetchone()
    return {'official':official,'data':json.loads(row['data']) if row else None,'revision':row['revision'] if row else 0}

@router.put('/student/rules/{rule_id}/versions')
def revise_rule(rule_id:str,data:DocumentWrite,uid:int=Depends(current_user_id)):
    from .snu_catalog import curriculum,metadata
    official=curriculum(rule_id)
    if not isinstance(data.data.get('tracks'),list) or not data.data['tracks']:raise HTTPException(400,'전공 유형이 필요합니다.')
    if {t.get('key') for t in data.data['tracks']}!={t['key'] for t in official['tracks']}:raise HTTPException(400,'전공 유형은 공식 자료와 일치해야 합니다.')
    def validate(v,depth=0):
        if depth>20:raise HTTPException(400,'규정 중첩이 너무 깊습니다.')
        if isinstance(v,dict):
            for k,x in v.items():
                if k in ('credits','total_credits','major_min_credits','min_credits','min_courses','required_credits','select_min') and (not isinstance(x,(int,float)) or not 0<=x<=500):raise HTTPException(400,'학점과 과목 수는 0~500 범위로 입력해주세요.')
                validate(x,depth+1)
        elif isinstance(v,list):
            for x in v:validate(x,depth+1)
    validate(data.data);encoded=encode_document(data.data)
    if '/api/personal/resources/' in encoded:raise HTTPException(400,'공개 규정 설명에는 비공개 첨부파일을 넣을 수 없습니다.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');revision=db.execute('SELECT COALESCE(MAX(revision),0) FROM curriculum_structured_versions WHERE rule_id=?',(rule_id,)).fetchone()[0]
        if revision!=data.revision:raise HTTPException(409,'다른 사람이 규정을 먼저 수정했습니다. 편집 내용을 보존하고 최신 판본과 비교해주세요.')
        db.execute('INSERT INTO curriculum_structured_versions(rule_id,revision,data,author_id,source_version) VALUES(?,?,?,?,?)',(rule_id,revision+1,encoded,uid,metadata()['revision']));db.commit()
    return {'revision':revision+1}
@router.get('/student/rules/{rule_id}/history')
def rule_history(rule_id:str,uid:int=Depends(current_user_id)):
    with connection() as db:return [dict(r)|{'data':json.loads(r['data'])} for r in db.execute('SELECT revision,data,author_id,source_version,created_at FROM curriculum_structured_versions WHERE rule_id=? ORDER BY revision DESC LIMIT 100',(rule_id,))]

@router.get('/documents')
def document_copies(uid:int=Depends(current_user_id)):
    with connection() as db:return [dict(r) for r in db.execute("SELECT document_key,revision,updated_at FROM personal_documents WHERE user_id=? AND document_key LIKE '%conflict:%' ORDER BY updated_at DESC LIMIT 100",(uid,))]
