"""Explicit owner-configured, bounded board ↔ Mac room relay.

No network downloads, no remote code execution, no blind send retries.
Uncertain UI sends require review; inbound observations have a quiet period.
"""
import hashlib,json,re,time,uuid,shutil,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from .db import connection
from . import community_v2 as community, native_kakao

ROOM='대학생 자료 공유방'
PREFIX='[NETAQ 자료 공유]'
QUIET_SECONDS=60
MAX_BYTES=50*1024*1024

def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS kakao_board_routes(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,board_id INTEGER NOT NULL UNIQUE,room TEXT NOT NULL UNIQUE,mention TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,ack INTEGER NOT NULL DEFAULT 1,last_post_id INTEGER NOT NULL DEFAULT 0,last_scan TEXT,error TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS kakao_board_messages(route_id INTEGER NOT NULL,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,digest TEXT NOT NULL,changed REAL NOT NULL,state TEXT NOT NULL DEFAULT 'pending',post_id INTEGER,error TEXT,PRIMARY KEY(route_id,fingerprint));
        CREATE TABLE IF NOT EXISTS kakao_board_assets(route_id INTEGER NOT NULL,fingerprint TEXT NOT NULL,ordinal INTEGER NOT NULL,resource_id TEXT NOT NULL,PRIMARY KEY(route_id,fingerprint,ordinal));
        CREATE TABLE IF NOT EXISTS kakao_board_origins(post_id INTEGER PRIMARY KEY,route_id INTEGER NOT NULL,fingerprint TEXT NOT NULL,UNIQUE(route_id,fingerprint));
        ''')
        if 'started_at' not in {r['name'] for r in db.execute('PRAGMA table_info(kakao_board_routes)')}:db.execute('ALTER TABLE kakao_board_routes ADD COLUMN started_at REAL NOT NULL DEFAULT 0')
        columns={r['name'] for r in db.execute('PRAGMA table_info(kakao_board_routes)')}
        for name,definition in (
            ('last_attempt','TEXT'),('last_success','TEXT'),('last_row_count','INTEGER NOT NULL DEFAULT 0'),
            ('consecutive_failures','INTEGER NOT NULL DEFAULT 0'),
        ):
            if name not in columns:db.execute(f'ALTER TABLE kakao_board_routes ADD COLUMN {name} {definition}')
        db.execute('''CREATE TABLE IF NOT EXISTS kakao_board_incidents(
          id INTEGER PRIMARY KEY,route_id INTEGER NOT NULL,started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,ended_at TEXT,error TEXT NOT NULL,occurrences INTEGER NOT NULL DEFAULT 1
        )''')
        db.commit()
init()

def packets(rows,mention):
    from .kakao_bridge import mention_matches
    for i,row in enumerate(rows):
        text=row.get('text','')
        if mention not in row.get('mentions',[]) or not mention_matches(text,mention) or text.startswith(PREFIX) or row.get('direction','unknown')=='unknown':continue
        lines=text.splitlines();at=next((n for n,s in enumerate(lines) if mention_matches(s,mention)),0)
        title=re.sub(r'(?<![\w@])@'+re.escape(mention)+r'(?=$|[\s,:;.!?\[\]()])','',lines[at]).strip(' :-')
        if not title:continue
        body='\n'.join(lines[at+1:]).strip();assets=[];observed_meta=row.get('metadata','');observed_date=row.get('date','')
        clock=re.search(r'(?:오전|오후)\s*\d{1,2}:\d{2}',row.get('metadata',''))
        if not clock:
            for stamp in rows[i+1:i+21]:
                if stamp.get('newSender') or stamp.get('direction')!=row['direction']:break
                if re.search(r'(?:오전|오후)\s*\d{1,2}:\d{2}',stamp.get('metadata','')):
                    observed_meta=stamp['metadata'];observed_date=stamp.get('date') or observed_date;break
        for following in rows[i+1:i+21]:
            if following.get('newSender') or following.get('direction')!=row['direction'] or mention_matches(following.get('text',''),mention) or following.get('text','').startswith(PREFIX):break
            next_clock=re.search(r'(?:오전|오후)\s*\d{1,2}:\d{2}',following.get('metadata',''))
            if clock and next_clock and clock[0]!=next_clock[0]:break
            if following.get('date') and row.get('date') and following['date']!=row['date']:break
            if next_clock:observed_meta=following.get('metadata','')
            if following.get('date'):observed_date=following['date']
            if following.get('photo') or following.get('file'):
                for subindex in range(following.get('photoCount',1) if following.get('photo') else 1):
                    assets.append({'index':following['index'],'subindex':subindex,'kind':'photo' if following.get('photo') else 'file','name':following.get('fileName','')})
            elif following.get('text'):break
            else:break
        meta=re.sub(r'^\s*\d+\s*','',row.get('metadata','')).strip()
        # A bubble's clock can disappear when its sender adds another bubble.
        # Prefer conservative same-day duplicate suppression over double posts.
        sender=re.sub(r'(?:오전|오후)\s*\d{1,2}:\d{2}','',meta).strip()
        fingerprint=hashlib.sha256(json.dumps([row['direction'],sender,text],ensure_ascii=False).encode()).hexdigest()
        yield fingerprint,{'title':title[:160],'body':body[:30000],'anchor':row['index'],'expected':text,'assets':assets,'date':observed_date,'metadata':meta,'observed_metadata':observed_meta}

def summary(uid):
    with connection() as db:
        routes=[dict(r) for r in db.execute('SELECT * FROM kakao_board_routes WHERE user_id=?',(uid,))]
        for r in routes:
            r['counts']={a['state']:a['n'] for a in db.execute('SELECT state,count(*) n FROM kakao_board_messages WHERE route_id=? GROUP BY state',(r['id'],))}
            r['issues']=[dict(a) for a in db.execute("SELECT fingerprint,state,error FROM kakao_board_messages WHERE route_id=? AND error IS NOT NULL LIMIT 20",(r['id'],))]
    return routes

def configure(uid,bid,room,mention,enabled,ack=True):
    from .kakao_bridge import invoke
    if not community.admin(uid):raise HTTPException(403,'게시판 관리자 권한이 필요합니다.')
    if room!=ROOM:raise HTTPException(400,'지정된 대학생 자료 공유방만 자동 연동할 수 있습니다.')
    if not mention.strip():raise HTTPException(400,'멘션 이름을 입력해주세요.')
    with connection() as db:
        community.board_access(db,uid,bid,'post')
        bound=db.execute('SELECT board_id FROM kakao_board_routes WHERE room=?',(room,)).fetchone()
        if bound and bound['board_id']!=bid:raise HTTPException(409,'이 방은 이미 다른 게시판에 연결되어 있습니다. 기존 연결의 게시판을 선택해주세요.')
        old=db.execute('SELECT * FROM kakao_board_routes WHERE board_id=?',(bid,)).fetchone()
        if old and old['user_id']!=uid:raise HTTPException(403,'연결 소유자가 다릅니다.')
        if enabled and old and old['enabled'] and old['mention']!=mention:raise HTTPException(409,'연결을 끈 뒤 멘션을 변경해주세요.')
    baseline=[]
    if enabled and (not old or not old['enabled']):
        with native_kakao._send_lock:
            opened=invoke('search',room=room)
            if opened.get('error'):raise HTTPException(409,opened['error'])
            read=invoke('read',room=room)
            if read.get('error'):raise HTTPException(409,read['error'])
            baseline=list(packets(read.get('rows',[]),mention))
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        cursor=db.execute('SELECT COALESCE(MAX(id),0) FROM community_posts WHERE board_id=?',(bid,)).fetchone()[0]
        db.execute('''INSERT INTO kakao_board_routes(user_id,board_id,room,mention,enabled,ack,last_post_id) VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(board_id) DO UPDATE SET mention=excluded.mention,enabled=excluded.enabled,ack=excluded.ack,error=NULL,last_post_id=CASE WHEN kakao_board_routes.enabled=0 THEN excluded.last_post_id ELSE kakao_board_routes.last_post_id END''',(uid,bid,room,mention.strip(),int(enabled),int(ack),cursor))
        rid=db.execute('SELECT id FROM kakao_board_routes WHERE board_id=?',(bid,)).fetchone()[0]
        if enabled and (not old or not old['enabled']):
            db.execute('UPDATE kakao_board_routes SET started_at=? WHERE id=?',(time.time(),rid))
            db.execute("UPDATE kakao_board_messages SET state='baseline',error=NULL WHERE route_id=? AND state='pending'",(rid,))
        for fp,p in baseline:
            db.execute("INSERT OR IGNORE INTO kakao_board_messages VALUES(?,?,?,?,?,'baseline',NULL,NULL)",(rid,fp,json.dumps(p),'-',time.time()))
        db.execute('INSERT INTO community_audit(actor,action,target) VALUES(?,?,?)',(uid,'kakao.relay',f'{bid}:{int(enabled)}'));db.commit()
    return summary(uid)

def enqueue(db,uid,key,payload):
    db.execute("INSERT OR IGNORE INTO kakao_bridge_outbox(id,user_id,idempotency_key,payload,state) VALUES(?,?,?,?,'queued')",(uuid.uuid4().hex,uid,key,json.dumps(payload,ensure_ascii=False,sort_keys=True)))

def plain(node):
    if isinstance(node,list):return '\n'.join(filter(None,(plain(n) for n in node)))
    if not isinstance(node,dict):return ''
    if node.get('richContent'):return plain(node['richContent'])
    if node.get('type')=='text':return node.get('text','')
    if node.get('type')=='hardBreak':return '\n'
    if node.get('type') in ('paragraph','heading','codeBlock','detailsSummary'):
        return ''.join(plain(c) for c in node.get('content',node.get('children',[])))
    return plain(node.get('content',node.get('blocks',[])))

def export_posts(route):
    uid,bid=route['user_id'],route['board_id']
    with connection() as db:
        community.board_access(db,uid,bid)
        db.execute('BEGIN IMMEDIATE')
        posts=db.execute('SELECT * FROM community_posts WHERE board_id=? AND id>? ORDER BY id LIMIT 20',(bid,route['last_post_id'])).fetchall()
        for p in posts:
            if not p['deleted'] and not db.execute('SELECT 1 FROM kakao_board_origins WHERE post_id=?',(p['id'],)).fetchone():
                doc=json.loads(p['document']);community.validate_assets(db,uid,doc,bid)
                ids=list(dict.fromkeys(re.findall(r'/api/personal/resources/([a-f0-9]{32})',json.dumps(doc))))
                images=[]
                for rid in ids:
                    resource=db.execute('SELECT * FROM personal_resources WHERE id=? AND board_id=?',(rid,bid)).fetchone()
                    if resource and resource['mime'] in native_kakao.ALLOWED_IMAGE_TYPES:images.append(rid)
                body=plain(doc)
                link=f'https://netaq.chobab.app/personal-project/calendar/boards?board={bid}&post={p["id"]}'
                payload={'room':route['room'],'text':f'{p["title"]}\n\n{body}\n\n{link}','resources':images,'route_id':route['id'],'post_id':p['id'],'revision':p['revision']}
                if len(payload['text'])>10000 or len(images)>10:raise ValueError(f'글 #{p["id"]}: 카톡 전송 한도(본문 1만자/사진 10장)를 초과했습니다. 글을 나눠주세요.')
                enqueue(db,uid,f'relay:{route["id"]}:post:{p["id"]}',payload)
            db.execute('UPDATE kakao_board_routes SET last_post_id=? WHERE id=?',(p['id'],route['id']))
        db.commit()

def capture_assets(route,fp,packet):
    from .kakao_bridge import invoke
    ids=[]
    for ordinal,asset in enumerate(packet['assets']):
        with connection() as db:
            old=db.execute('SELECT resource_id FROM kakao_board_assets WHERE route_id=? AND fingerprint=? AND ordinal=?',(route['id'],fp,ordinal)).fetchone()
        if old:ids.append(old[0]);continue
        rid=uuid.uuid4().hex;community.ROOT.mkdir(parents=True,exist_ok=True)
        destination=community.ROOT/rid
        result=invoke(asset['kind'],room=route['room'],index=asset['index'],subindex=asset.get('subindex',0),anchor=packet['anchor'],expected=packet['expected'],output=str(destination))
        if not result.get('saved') or not destination.is_file():raise ValueError(result.get('error','첨부파일 수집 결과를 확인하지 못했습니다.'))
        size=destination.stat().st_size
        if not 0<size<=MAX_BYTES:destination.unlink(missing_ok=True);raise ValueError('첨부파일은 50MB까지 수집할 수 있습니다.')
        mime='image/png' if asset['kind']=='photo' else 'application/octet-stream'
        if mime=='image/png' and not native_kakao._matches_image_signature(mime,destination.read_bytes()):destination.unlink(missing_ok=True);raise ValueError('이미지 형식 검증 실패')
        destination.chmod(0o600)
        with connection() as db:
            total=db.execute('SELECT COALESCE(SUM(size),0) FROM personal_resources WHERE user_id=?',(route['user_id'],)).fetchone()[0]
            if total+size>1024*1024*1024:destination.unlink(missing_ok=True);raise ValueError('자료 저장 한도에 도달했습니다.')
            db.execute('INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES(?,?,?,?,?,?)',(rid,route['user_id'],route['board_id'],asset['name'] or '카카오톡 사진.png',mime,size))
            db.execute('INSERT INTO kakao_board_assets VALUES(?,?,?,?)',(route['id'],fp,ordinal,rid));db.commit()
        ids.append(rid)
    return ids

def publish_packet(route,fp,packet,ids):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');community.board_access(db,route['user_id'],route['board_id'],'post')
        seen=db.execute('SELECT post_id,state FROM kakao_board_messages WHERE route_id=? AND fingerprint=?',(route['id'],fp)).fetchone()
        if not seen or seen['state']!='pending':return
        nodes=[{'type':'paragraph','content':[{'type':'text','text':line}]} for line in packet['body'].splitlines() if line]
        for rid in ids:
            r=db.execute('SELECT * FROM personal_resources WHERE id=? AND board_id=?',(rid,route['board_id'])).fetchone()
            if not r:raise ValueError('첨부 접근 권한 확인 실패')
            url=f'/api/personal/resources/{rid}'
            nodes.append({'type':'image','attrs':{'src':url,'alt':r['name']}} if r['mime'].startswith('image/') else {'type':'attachment','attrs':{'href':url,'name':r['name']}})
        nodes.append({'type':'paragraph','content':[{'type':'text','text':f'카카오톡 자료 공유 · {packet["metadata"]}'}]})
        doc={'version':1,'schemaVersion':2,'documentId':uuid.uuid4().hex,'blocks':[],'richContent':{'type':'doc','content':nodes}}
        encoded=community.encode_document(doc)
        pid=db.execute('INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',(route['board_id'],route['user_id'],packet['title'],encoded,packet['body'])).lastrowid
        db.execute('INSERT INTO kakao_board_origins VALUES(?,?,?)',(pid,route['id'],fp))
        db.execute("UPDATE kakao_board_messages SET state='published',post_id=?,error=NULL WHERE route_id=? AND fingerprint=?",(pid,route['id'],fp))
        if route['ack']:
            link=f'https://netaq.chobab.app/personal-project/calendar/boards?board={route["board_id"]}&post={pid}'
            enqueue(db,route['user_id'],f'relay:{route["id"]}:ack:{fp}',{'room':route['room'],'text':f'등록 완료\n{packet["title"]}\n{link}','resources':[],'route_id':route['id'],'post_id':pid})
        db.commit()

def observe(route,rows,now=None):
    now=now or time.time()
    for fp,packet in packets(rows,route['mention']):
        # AX date help and bubble clocks can change when Kakao recycles rows.
        # The same mention text is deliberately imported only once per route.
        with connection() as db:
            duplicates=db.execute('SELECT fingerprint,state FROM kakao_board_messages WHERE route_id=? AND json_extract(payload,\'$.expected\')=? AND fingerprint<>?',(route['id'],packet['expected'],fp)).fetchall()
            if any(r['state'] in ('baseline','published') for r in duplicates):continue
            for r in duplicates:db.execute("UPDATE kakao_board_messages SET state='superseded',error=NULL WHERE route_id=? AND fingerprint=?",(route['id'],r['fingerprint']))
            db.commit()
        if route.get('started_at'):
            date_parts=re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})',packet['date'])
            clock=re.search(r'(오전|오후)\s*(\d{1,2}):(\d{2})',packet['observed_metadata'])
            # Do not import older messages that become visible after reconnect.
            if not date_parts or not clock:continue
            hour=int(clock[2])%12+(12 if clock[1]=='오후' else 0)
            try:observed=datetime(*map(int,date_parts.groups()),hour,int(clock[3]),tzinfo=timezone(timedelta(hours=9))).timestamp()
            except ValueError:continue
            if observed<int(route['started_at']//60)*60:continue
        canonical={k:v for k,v in packet.items() if k not in ('anchor','assets','observed_metadata')}
        canonical['assets']=[{k:v for k,v in a.items() if k!='index'} for a in packet['assets']]
        digest=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
        with connection() as db:
            old=db.execute('SELECT * FROM kakao_board_messages WHERE route_id=? AND fingerprint=?',(route['id'],fp)).fetchone()
            if old and old['state']!='pending':continue
            if not old or old['digest']!=digest:
                db.execute('DELETE FROM kakao_board_assets WHERE route_id=? AND fingerprint=?',(route['id'],fp))
                db.execute("INSERT INTO kakao_board_messages(route_id,fingerprint,payload,digest,changed) VALUES(?,?,?,?,?) ON CONFLICT(route_id,fingerprint) DO UPDATE SET payload=excluded.payload,digest=excluded.digest,changed=excluded.changed,error=NULL",(route['id'],fp,json.dumps(packet),digest,now));db.commit();continue
            if now-old['changed']<QUIET_SECONDS:continue
        try:publish_packet(route,fp,packet,capture_assets(route,fp,packet))
        except Exception as e:
            with connection() as db:db.execute('UPDATE kakao_board_messages SET error=? WHERE route_id=? AND fingerprint=?',(str(e)[:500],route['id'],fp));db.commit()

def tick():
    from .kakao_bridge import invoke
    with connection() as db:routes=[dict(r) for r in db.execute('SELECT * FROM kakao_board_routes WHERE enabled=1')]
    for route in routes:
        try:
            with connection() as db:db.execute('UPDATE kakao_board_routes SET last_attempt=CURRENT_TIMESTAMP WHERE id=?',(route['id'],));db.commit()
            if not community.admin(route['user_id']):raise ValueError('연결 소유자의 관리자 권한이 회수되었습니다.')
            export_posts(route)
            with native_kakao._send_lock:
                # Keep the dedicated room window at the live edge. If the room
                # was closed, reopen the exact unique result once and retry.
                read=invoke('read-latest',room=route['room'])
                if read.get('error'):
                    opened=invoke('search',room=route['room'])
                    if opened.get('error'):raise ValueError(opened['error'])
                    read=invoke('read-latest',room=route['room'])
                if read.get('error'):raise ValueError(read['error'])
                observe(route,read.get('rows',[]))
            with connection() as db:
                db.execute('''UPDATE kakao_board_routes SET last_scan=CURRENT_TIMESTAMP,last_success=CURRENT_TIMESTAMP,
                  last_row_count=?,consecutive_failures=0,error=NULL WHERE id=?''',(len(read.get('rows',[])),route['id']))
                db.execute('UPDATE kakao_board_incidents SET ended_at=CURRENT_TIMESTAMP WHERE route_id=? AND ended_at IS NULL',(route['id'],));db.commit()
        except Exception as e:
            message=str(e)[:500]
            with connection() as db:
                db.execute('UPDATE kakao_board_routes SET error=?,consecutive_failures=consecutive_failures+1 WHERE id=?',(message,route['id']))
                incident=db.execute('SELECT id,error FROM kakao_board_incidents WHERE route_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1',(route['id'],)).fetchone()
                if incident and incident['error']==message:
                    db.execute('UPDATE kakao_board_incidents SET last_seen=CURRENT_TIMESTAMP,occurrences=occurrences+1 WHERE id=?',(incident['id'],))
                else:
                    if incident:db.execute('UPDATE kakao_board_incidents SET ended_at=CURRENT_TIMESTAMP WHERE id=?',(incident['id'],))
                    db.execute('INSERT INTO kakao_board_incidents(route_id,error) VALUES(?,?)',(route['id'],message))
                db.commit()

def validate_job(db,job,payload):
    route=db.execute('SELECT * FROM kakao_board_routes WHERE id=? AND user_id=? AND enabled=1',(payload['route_id'],job['user_id'])).fetchone()
    if not route or route['room']!=payload['room'] or not community.admin(job['user_id']):raise ValueError('연결이 꺼졌거나 권한이 회수되었습니다.')
    community.board_access(db,job['user_id'],route['board_id'])
    post=db.execute('SELECT * FROM community_posts WHERE id=? AND board_id=? AND deleted=0',(payload['post_id'],route['board_id'])).fetchone()
    if not post:raise ValueError('게시글이 삭제되어 전송하지 않습니다.')
    if payload.get('revision') and payload['revision']!=post['revision']:raise ValueError('전송 대기 중 글이 수정되었습니다. 새 내용 확인 후 수동으로 공유해주세요.')
    allowed=set(re.findall(r'/api/personal/resources/([a-f0-9]{32})',post['document']))
    if not set(payload['resources']).issubset(allowed):raise ValueError('게시글 첨부가 변경되었습니다.')
    return route['board_id']
