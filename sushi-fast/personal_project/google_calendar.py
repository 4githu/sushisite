"""One-way Google imports and explicit exports; never automatically push app edits."""
import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from .db import connection
from . import workspace
from .schemas import EventUpdate

ROOT='https://www.googleapis.com/calendar/v3'
sync_lock=threading.Lock()
stop_worker=threading.Event()


def account_for(user_id,account_id):
    with connection() as db:
        account=db.execute('SELECT * FROM google_accounts WHERE id=? AND user_id=?',(account_id,user_id)).fetchone()
        if not account: raise HTTPException(404,'연결된 Google 계정이 없습니다.')
        return dict(account)


def client(account):
    from auth.google_oauth import access_token
    return httpx.Client(base_url=ROOT,headers={'Authorization':'Bearer '+access_token(account)},timeout=25)


def checked(response):
    if response.status_code==412: raise HTTPException(409,'구글에서도 수정된 일정입니다. 구글의 최신 내용을 확인한 뒤 다시 동기화해주세요.')
    if response.status_code>=400: raise HTTPException(502,'Google Calendar 요청에 실패했습니다. 권한과 API 사용 설정을 확인해주세요.')
    return response.json() if response.content else {}


def list_accounts(user_id):
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT id,email,last_sync,error FROM google_accounts WHERE user_id=?',(user_id,))]


def calendars(user_id,account_id,refresh=True):
    account=account_for(user_id,account_id)
    if refresh:
        with client(account) as http:
            page=None
            while True:
                data=checked(http.get('/users/me/calendarList',params={'pageToken':page} if page else {}))
                with connection() as db:
                    for cal in data.get('items',[]):
                        db.execute('''INSERT INTO google_calendars(account_id,calendar_id,name,writable) VALUES(?,?,?,?)
                            ON CONFLICT(account_id,calendar_id) DO UPDATE SET name=excluded.name,writable=excluded.writable''',
                            (account_id,cal['id'],cal.get('summary','캘린더'),cal.get('accessRole') in ('owner','writer')))
                    db.commit()
                page=data.get('nextPageToken')
                if not page: break
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM google_calendars WHERE account_id=?',(account_id,))]


def select_calendars(user_id,account_id,ids):
    account_for(user_id,account_id)
    with connection() as db:
        available={r[0] for r in db.execute('SELECT calendar_id FROM google_calendars WHERE account_id=?',(account_id,))}
        if not set(ids)<=available: raise HTTPException(400,'캘린더 목록을 먼저 새로고침해주세요.')
        db.execute('UPDATE google_calendars SET enabled=0 WHERE account_id=?',(account_id,))
        db.executemany('UPDATE google_calendars SET enabled=1 WHERE account_id=? AND calendar_id=?',[(account_id,i) for i in ids]); db.commit()
    return calendars(user_id,account_id,False)


def fingerprint(row):
    # Personal completion does not change an event shared with a Google calendar.
    keys=('title','description','start_time','end_time','is_all_day','location','web_url')
    return hashlib.sha256(json.dumps({k:row[k] for k in keys},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def google_body(row):
    start=datetime.fromisoformat(row['start_time'].replace('Z','+00:00'))
    end=datetime.fromisoformat(row['end_time'].replace('Z','+00:00')) if row['end_time'] else start+timedelta(hours=1)
    if row['is_all_day']:
        if end.date()<=start.date(): end=start+timedelta(days=1)
        times={'start':{'date':start.date().isoformat()},'end':{'date':end.date().isoformat()}}
    else:
        if start.tzinfo is None: start=start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
        times={'start':{'dateTime':start.isoformat()},'end':{'dateTime':end.isoformat()}}
    body={'summary':row['title'],'description':row['description'],'location':row['location'],**times}
    body['source']={'url':row['web_url'],'title':'관련 웹페이지'} if row['web_url'] else None
    return body


def fields(remote):
    start=remote.get('start',{}); end=remote.get('end',{})
    if not (start.get('dateTime') or start.get('date')): return None
    return dict(title=(remote.get('summary') or '(제목 없음)')[:120],description=remote.get('description',''),
        start_time=start.get('dateTime') or start['date']+'T00:00:00',
        end_time=end.get('dateTime') or (end['date']+'T00:00:00' if end.get('date') else None),
        is_all_day='date' in start,location=remote.get('location','')[:500],web_url=(remote.get('source') or {}).get('url',''))


def sync_account(user_id,account_id):
    if not sync_lock.acquire(blocking=False): raise HTTPException(409,'다른 동기화가 진행 중입니다. 잠시 후 다시 시도해주세요.')
    try:
        account=account_for(user_id,account_id)
        count=0; conflicts=[]
        with connection() as db:
            selected=[dict(r) for r in db.execute('SELECT * FROM google_calendars WHERE account_id=? AND enabled=1',(account_id,))]
        with client(account) as http:
            for cal in selected:
                path='/calendars/'+quote(cal['calendar_id'],safe='')+'/events'
                # Import is strictly Google -> app. Exports change only on an explicit request.
                blocked=set()
                page=None
                while True:
                    now=datetime.now(timezone.utc)
                    params={'singleEvents':'true','showDeleted':'true','maxResults':2500,'timeMin':(now-timedelta(days=365)).isoformat(),'timeMax':(now+timedelta(days=730)).isoformat()}
                    if page: params['pageToken']=page
                    data=checked(http.get(path,params=params))
                    for remote in data.get('items',[]):
                        if remote['id'] in blocked: continue
                        with connection() as db:
                            link=db.execute('SELECT * FROM google_event_links WHERE account_id=? AND calendar_id=? AND google_id=?',(account_id,cal['calendar_id'],remote['id'])).fetchone()
                            local=db.execute('SELECT * FROM events WHERE id=?',(link['event_id'],)).fetchone() if link else None
                        if link and link['origin']=='local': continue
                        if remote.get('status')=='cancelled':
                            # Clinic/report records are never cascade-deleted by a remote Calendar deletion.
                            if local and local['type']=='google': _delete_import(local['id'])
                            if link:
                                with connection() as db:
                                    db.execute('DELETE FROM google_event_links WHERE account_id=? AND calendar_id=? AND google_id=?',(account_id,cal['calendar_id'],remote['id'])); db.commit()
                            continue
                        values=fields(remote)
                        if not values: continue
                        if link and local:
                            if link['etag']==remote.get('etag'): continue
                            if fingerprint(local)!=link['fingerprint']:
                                conflicts.append(local['title']); remember_conflict(account_id,cal['calendar_id'],link,local['title']); continue
                            try:
                                if local['type']=='aura':
                                    values={k:v for k,v in values.items() if k in ('start_time','end_time','location','web_url','description')}
                                _update_import(local['id'],values)
                            except HTTPException:
                                conflicts.append(local['title']); remember_conflict(account_id,cal['calendar_id'],link,local['title']); continue
                            event_id=local['id']
                        elif link and not local:
                            continue  # pending local deletion
                        else:
                            with connection() as db:
                                cur=db.execute(f"INSERT INTO events(user_id,type,status,category_name,{','.join(values)}) VALUES(?,?,?, ?,{','.join('?' for _ in values)})",[user_id,'google','passive',cal['name'],*values.values()]); db.commit(); event_id=cur.lastrowid
                        with connection() as db:
                            local=db.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
                            db.execute('''INSERT INTO google_event_links(account_id,calendar_id,google_id,event_id,etag,fingerprint) VALUES(?,?,?,?,?,?)
                                ON CONFLICT(account_id,calendar_id,google_id) DO UPDATE SET etag=excluded.etag,fingerprint=excluded.fingerprint''',(account_id,cal['calendar_id'],remote['id'],event_id,remote.get('etag'),fingerprint(local))); db.commit()
                        count+=1
                    page=data.get('nextPageToken')
                    if not page: break
        error='동시 수정 충돌: '+', '.join(conflicts[:5]) if conflicts else None
        with connection() as db:
            db.execute('UPDATE google_accounts SET last_sync=?,error=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),error,account_id)); db.commit()
        return {'updated':count,'conflicts':conflicts}
    except HTTPException as exc:
        with connection() as db:
            db.execute('UPDATE google_accounts SET error=? WHERE id=? AND user_id=?',(str(exc.detail),account_id,user_id)); db.commit()
        raise
    finally: sync_lock.release()


def _delete_import(event_id):
    with connection() as db: db.execute("DELETE FROM events WHERE id=? AND type='google'",(event_id,)); db.commit()


def remember_conflict(account_id,calendar_id,link,title):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO google_conflicts VALUES(?,?,?,?,?)',(account_id,calendar_id,link['google_id'],link['event_id'],title)); db.commit()


def conflicts_for(user_id,account_id):
    account_for(user_id,account_id)
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM google_conflicts WHERE account_id=?',(account_id,))]


def resolve_conflict(user_id,account_id,calendar_id,google_id,choice):
    if not sync_lock.acquire(blocking=False): raise HTTPException(409,'동기화 완료 후 다시 시도해주세요.')
    try:
        account=account_for(user_id,account_id)
        with connection() as db:
            link=db.execute('SELECT * FROM google_event_links WHERE account_id=? AND calendar_id=? AND google_id=?',(account_id,calendar_id,google_id)).fetchone()
            cal=db.execute('SELECT * FROM google_calendars WHERE account_id=? AND calendar_id=?',(account_id,calendar_id)).fetchone()
            if not link or not cal: raise HTTPException(404,'일정 연결을 찾을 수 없습니다.')
            local=db.execute('SELECT * FROM events WHERE id=?',(link['event_id'],)).fetchone()
        with client(account) as http:
            target='/calendars/'+quote(calendar_id,safe='')+'/events/'+quote(google_id,safe='')
            response=http.get(target)
            remote=None if response.status_code in (404,410) else checked(response)
            if remote and remote.get('status')=='cancelled': remote=None
            resolved_id=google_id
            if choice=='local':
                if link['origin']=='google': raise HTTPException(403,'가져온 일정은 Google에서 수정해주세요.')
                if not cal['writable']: raise HTTPException(403,'읽기 전용 캘린더입니다.')
                if local and not remote:
                    resolved_id=hashlib.sha256((google_id+fingerprint(local)+'restore').encode()).hexdigest()
                    collection='/calendars/'+quote(calendar_id,safe='')+'/events'
                    restored=http.post(collection,json={**google_body(local),'id':resolved_id})
                    remote=checked(http.get(collection+'/'+resolved_id)) if restored.status_code==409 else checked(restored)
                elif local: remote=checked(http.patch(target,json=google_body(local),headers={'If-Match':remote['etag']}))
                elif remote: checked(http.delete(target,headers={'If-Match':remote['etag']}))
            else:
                if not remote:
                    if local and local['type']=='google': _delete_import(local['id'])
                else:
                    values=fields(remote)
                    if not values: raise HTTPException(409,'구글 원본 일정을 확인할 수 없습니다.')
                    if not local:
                        with connection() as db:
                            cur=db.execute(f"INSERT INTO events(user_id,type,status,category_name,{','.join(values)}) VALUES(?,?,?, ?,{','.join('?' for _ in values)})",[user_id,'google','passive',cal['name'],*values.values()])
                            db.execute('UPDATE google_event_links SET event_id=? WHERE account_id=? AND calendar_id=? AND google_id=?',(cur.lastrowid,account_id,calendar_id,google_id)); db.commit()
                            link=dict(link);link['event_id']=cur.lastrowid
                    else:
                        if local['type']=='aura': values={k:v for k,v in values.items() if k in ('start_time','end_time','location','web_url','description')}
                        if local['type']=='google': _update_import(local['id'],values)
                        else: workspace.update_event(user_id,local['id'],EventUpdate(**values))
        with connection() as db:
            local=db.execute('SELECT * FROM events WHERE id=?',(link['event_id'],)).fetchone()
            if local and remote: db.execute('UPDATE google_event_links SET google_id=?,etag=?,fingerprint=? WHERE account_id=? AND calendar_id=? AND google_id=?',(resolved_id,remote.get('etag'),fingerprint(local),account_id,calendar_id,google_id))
            else: db.execute('DELETE FROM google_event_links WHERE account_id=? AND calendar_id=? AND google_id=?',(account_id,calendar_id,google_id))
            db.execute('DELETE FROM google_conflicts WHERE account_id=? AND calendar_id=? AND google_id=?',(account_id,calendar_id,google_id))
            db.execute('UPDATE google_accounts SET error=NULL WHERE id=?',(account_id,)); db.commit()
        return {'resolved':True}
    finally: sync_lock.release()


def _update_import(event_id,values):
    with connection() as db:
        db.execute(f"UPDATE events SET {','.join(k+'=?' for k in values)} WHERE id=? AND type='google'",[*values.values(),event_id]); db.commit()


def export_event(user_id,account_id,calendar_id,event_id):
    if not sync_lock.acquire(blocking=False): raise HTTPException(409,'다른 캘린더 작업이 진행 중입니다.')
    try: return _export_event(user_id,account_id,calendar_id,event_id)
    finally: sync_lock.release()


def _export_event(user_id,account_id,calendar_id,event_id):
    account=account_for(user_id,account_id)
    with connection() as db:
        row=workspace.accessible(db,user_id,event_id)
        if row['type']=='google': raise HTTPException(400,'Google에서 가져온 일정은 내보내기 대상이 아닙니다.')
        cal=db.execute('SELECT * FROM google_calendars WHERE account_id=? AND calendar_id=? AND writable=1',(account_id,calendar_id)).fetchone()
        if not cal: raise HTTPException(403,'쓰기 가능한 캘린더를 선택해주세요.')
        existing=db.execute('SELECT 1 FROM google_event_links WHERE account_id=? AND calendar_id=? AND event_id=?',(account_id,calendar_id,event_id)).fetchone()
    if existing: return {'exported':False}
    # Deterministic ID makes a retried export idempotent, even if the process died after Google's response.
    remote_id=hashlib.sha256(f'chobab:{user_id}:{account_id}:{event_id}'.encode()).hexdigest()
    with client(account) as http:
        path='/calendars/'+quote(calendar_id,safe='')+'/events'
        response=http.post(path,params={'sendUpdates':'none'},json={**google_body(row),'id':remote_id})
        remote=checked(http.get(path+'/'+remote_id)) if response.status_code==409 else checked(response)
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO google_event_links VALUES(?,?,?,?,?,?,?)',(account_id,calendar_id,remote['id'],event_id,remote.get('etag'),fingerprint(row),'local'))
        db.commit()
    return {'exported':True}


def disconnect(user_id,account_id):
    account_for(user_id,account_id)
    with connection() as db:
        # Keep local copies; unlink without deleting either side's events.
        db.execute("UPDATE events SET type='personal' WHERE user_id=? AND type='google' AND id IN (SELECT event_id FROM google_event_links WHERE account_id=?)",(user_id,account_id))
        db.execute('DELETE FROM google_accounts WHERE id=?',(account_id,)); db.commit()


def run_worker():
    while not stop_worker.wait(300):
        with connection() as db: accounts=[tuple(r) for r in db.execute('SELECT user_id,id FROM google_accounts')]
        for user_id,account_id in accounts:
            if stop_worker.is_set(): return
            try: sync_account(user_id,account_id)
            except Exception:
                # Provider errors are shown in the connection panel, never log tokens.
                with connection() as db:
                    db.execute("UPDATE google_accounts SET error=COALESCE(error,'자동 동기화를 완료하지 못했습니다. 다시 연결하거나 동기화를 눌러주세요.') WHERE id=?",(account_id,)); db.commit()
