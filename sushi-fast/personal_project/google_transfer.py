"""Explicit, previewed one-way export. Never clears a user's Google calendar."""
import hashlib
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from .db import connection
from . import google_calendar as g


def _plan(user_id, account_id, calendar_id, starts_on, ends_on, http):
    if not 0 <= (ends_on-starts_on).days <= 366:
        raise HTTPException(400, '내보내기 기간은 최대 367일입니다.')
    tz=ZoneInfo('Asia/Seoul')
    start=datetime.combine(starts_on,time.min,tz).isoformat()
    end=datetime.combine(ends_on+timedelta(days=1),time.min,tz).isoformat()
    with connection() as db:
        cal=db.execute('SELECT * FROM google_calendars WHERE account_id=? AND calendar_id=? AND writable=1',(account_id,calendar_id)).fetchone()
        if not cal: raise HTTPException(403,'쓰기 가능한 캘린더를 선택해주세요.')
        rows=[dict(r) for r in db.execute("SELECT * FROM events WHERE user_id=? AND type!='google' AND julianday(start_time)>=julianday(?) AND julianday(start_time)<julianday(?) ORDER BY id LIMIT 201",(user_id,start,end))]
        links={r['event_id']:dict(r) for r in db.execute('SELECT * FROM google_event_links WHERE account_id=? AND calendar_id=?',(account_id,calendar_id))}
    if len(rows)>200: raise HTTPException(400,'한 번에 200건까지 내보낼 수 있습니다. 기간을 줄여주세요.')
    path='/calendars/'+quote(calendar_id,safe='')+'/events'
    items=[]
    for row in rows:
        link=links.get(row['id'])
        if link and link['origin']!='local': continue
        remote_id=link['google_id'] if link else hashlib.sha256(f'chobab:{user_id}:{account_id}:{row["id"]}'.encode()).hexdigest()
        response=http.get(path+'/'+quote(remote_id,safe=''))
        remote=None if response.status_code==404 else g.checked(response)
        if remote and remote.get('status')=='cancelled':
            raise HTTPException(409,'Google에서 삭제한 내보내기 사본이 있습니다. 다른 대상 캘린더를 선택해주세요.')
        if remote and not remote.get('etag'): raise HTTPException(502,'Google 일정 버전을 확인하지 못했습니다.')
        body=g.google_body(row)
        same=remote and all(remote.get(k)==v or (not remote.get(k) and not v) for k,v in body.items())
        items.append({'event_id':row['id'],'google_id':remote_id,'title':row['title'],'action':'unchanged' if same else 'update' if remote else 'create','etag':remote.get('etag') if remote else None,'body':body,'fingerprint':g.fingerprint(row)})
    snapshot={'account':account_id,'calendar':calendar_id,'start':str(starts_on),'end':str(ends_on),'items':items}
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return path,items,digest,cal['name']


def transfer(user_id,account_id,calendar_id,starts_on,ends_on,preview_token=None):
    if not g.sync_lock.acquire(blocking=False): raise HTTPException(409,'다른 캘린더 작업이 진행 중입니다. 잠시 후 다시 시도해주세요.')
    try:
        account=g.account_for(user_id,account_id)
        with g.client(account) as http:
            path,items,digest,name=_plan(user_id,account_id,calendar_id,starts_on,ends_on,http)
            if preview_token is None:
                return {'preview_token':digest,'calendar_name':name,'create':sum(i['action']=='create' for i in items),'update':sum(i['action']=='update' for i in items),'unchanged':sum(i['action']=='unchanged' for i in items),'items':[{k:i[k] for k in ('event_id','title','action')} for i in items]}
            if preview_token!=digest: raise HTTPException(409,'미리보기 이후 일정이 변경되었습니다. 다시 미리보기해주세요.')
            completed=0
            try:
                for item in items:
                    if item['action']=='create':
                        response=http.post(path,params={'sendUpdates':'none'},json={**item['body'],'id':item['google_id']})
                    elif item['action']=='update':
                        response=http.patch(path+'/'+quote(item['google_id'],safe=''),params={'sendUpdates':'none'},headers={'If-Match':item['etag']},json=item['body'])
                    else: response=None
                    remote=g.checked(response) if response is not None else {'etag':item['etag']}
                    with connection() as db:
                        db.execute('''INSERT INTO google_event_links VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id,calendar_id,google_id) DO UPDATE SET etag=excluded.etag,fingerprint=excluded.fingerprint''',(account_id,calendar_id,item['google_id'],item['event_id'],remote.get('etag'),item['fingerprint'],'local'));db.commit()
                    completed+=1
            except (HTTPException,httpx.HTTPError) as exc:
                raise HTTPException(409,f'{completed}건 처리 후 중단되었습니다. 완료된 사본은 유지됩니다. 다시 미리보기해 남은 일정을 내보내세요.') from exc
        return {'exported':completed}
    finally: g.sync_lock.release()
