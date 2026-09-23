"""Calendar workspaces: membership is authoritative; completion belongs to the viewer."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .db import connection
from . import repository as legacy
from .schemas import ClinicRoundUpdate, SessionUpdate


def init_workspace():
    with connection() as db:
        columns = {r[1] for r in db.execute('PRAGMA table_info(events)')}
        for name, kind in [('location', "TEXT NOT NULL DEFAULT ''"), ('web_url', "TEXT NOT NULL DEFAULT ''"), ('project_id', 'INTEGER'), ('task_available_from', 'TEXT'), ('task_due_at', 'TEXT'), ('completion_source', "TEXT NOT NULL DEFAULT 'manual'")]:
            if name not in columns:
                db.execute(f'ALTER TABLE events ADD COLUMN {name} {kind}')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS calendar_daily_notes(user_id INTEGER NOT NULL, day TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', drawing TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,day));
        CREATE TABLE IF NOT EXISTS calendar_projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, owner_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS calendar_members(project_id INTEGER REFERENCES calendar_projects(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL, PRIMARY KEY(project_id,user_id));
        CREATE TABLE IF NOT EXISTS calendar_invites(token_hash TEXT PRIMARY KEY, project_id INTEGER REFERENCES calendar_projects(id) ON DELETE CASCADE,
            email TEXT NOT NULL, expires_at TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS calendar_completions(event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL, completed INTEGER NOT NULL, PRIMARY KEY(event_id,user_id));
        CREATE TABLE IF NOT EXISTS google_accounts(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL,
            email TEXT NOT NULL, client_kind TEXT NOT NULL, refresh_token TEXT NOT NULL, scopes TEXT NOT NULL,
            last_sync TEXT, error TEXT, UNIQUE(user_id,subject));
        CREATE TABLE IF NOT EXISTS google_calendars(account_id INTEGER REFERENCES google_accounts(id) ON DELETE CASCADE,
            calendar_id TEXT NOT NULL, name TEXT NOT NULL, writable INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(account_id,calendar_id));
        CREATE TABLE IF NOT EXISTS google_event_links(account_id INTEGER REFERENCES google_accounts(id) ON DELETE CASCADE,
            calendar_id TEXT NOT NULL, google_id TEXT NOT NULL, event_id INTEGER NOT NULL,
            etag TEXT, fingerprint TEXT, origin TEXT NOT NULL DEFAULT 'google',
            PRIMARY KEY(account_id,calendar_id,google_id), UNIQUE(account_id,calendar_id,event_id));
        CREATE TABLE IF NOT EXISTS google_oauth_states(state TEXT PRIMARY KEY, verifier TEXT NOT NULL, browser_hash TEXT NOT NULL,
            user_id INTEGER, purpose TEXT NOT NULL, client_kind TEXT NOT NULL, redirect_uri TEXT NOT NULL,
            return_to TEXT NOT NULL, expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS google_conflicts(account_id INTEGER REFERENCES google_accounts(id) ON DELETE CASCADE,
            calendar_id TEXT NOT NULL, google_id TEXT NOT NULL, event_id INTEGER NOT NULL, title TEXT NOT NULL,
            PRIMARY KEY(account_id,calendar_id,google_id));
        CREATE TABLE IF NOT EXISTS widget_devices(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS widget_pairs(code_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires TEXT NOT NULL);
        ''')
        project_columns = {r[1] for r in db.execute('PRAGMA table_info(calendar_projects)')}
        for name, kind in [('parent_id', 'INTEGER REFERENCES calendar_projects(id)'), ('isolate_tasks', 'INTEGER NOT NULL DEFAULT 0')]:
            if name not in project_columns:
                db.execute(f'ALTER TABLE calendar_projects ADD COLUMN {name} {kind}')
        note_columns = {row[1] for row in db.execute('PRAGMA table_info(calendar_daily_notes)')}
        if 'drawing' not in note_columns:
            db.execute("ALTER TABLE calendar_daily_notes ADD COLUMN drawing TEXT NOT NULL DEFAULT ''")
        if 'rich_document' not in note_columns:
            db.execute("ALTER TABLE calendar_daily_notes ADD COLUMN rich_document TEXT NOT NULL DEFAULT ''")
        from .aura_calendar import install
        install(db)
        db.commit()


def member(db, user_id, project_id):
    if not db.execute('SELECT 1 FROM calendar_members WHERE project_id=? AND user_id=?', (project_id,user_id)).fetchone():
        raise HTTPException(404, '프로젝트를 찾을 수 없습니다.')


def accessible(db, user_id, event_id):
    row = db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
    if not row:
        raise HTTPException(404, '일정을 찾을 수 없습니다.')
    if row['project_id']:
        member(db, user_id, row['project_id'])
    elif row['user_id'] != user_id:
        raise HTTPException(404, '일정을 찾을 수 없습니다.')
    return row


def event_dict(db, row, viewer):
    result = legacy._event_dict(row)
    result.update(location=row['location'], webUrl=row['web_url'], projectId=row['project_id'], canEdit=row['type'] not in ('integration','google'))
    result.update(taskAvailableFrom=row['task_available_from'], taskDueAt=row['task_due_at'], completionSource=row['completion_source'])
    if row['project_id'] and row['completion_source']=='manual' and row['status'] in ('todo','done'):
        done = db.execute('SELECT completed FROM calendar_completions WHERE event_id=? AND user_id=?', (row['id'],viewer)).fetchone()
        result['status'] = 'done' if done and done[0] else 'todo'
    link = db.execute('''SELECT g.email,c.name,c.writable FROM google_event_links l
        JOIN google_accounts g ON g.id=l.account_id JOIN google_calendars c ON c.account_id=l.account_id AND c.calendar_id=l.calendar_id
        WHERE l.event_id=? AND g.user_id=? LIMIT 1''', (row['id'],viewer)).fetchone()
    if link:
        result['googleAccount'] = link['email']
        result['googleCalendar'] = link['name']
        if row['type'] == 'google': result['canEdit'] = False
    return result


def list_events(user_id, start=None, end=None, event_type=None, status=None, tasks=False):
    query = '''SELECT e.* FROM events e WHERE (e.project_id IN
        (SELECT project_id FROM calendar_members WHERE user_id=?) OR (e.project_id IS NULL AND e.user_id=?))'''
    args = [user_id,user_id]
    if start and end:
        query += ' AND julianday(e.start_time)<julianday(?) AND julianday(COALESCE(e.end_time,e.start_time))>=julianday(?)'
        args += [end,start]
    if event_type: query += ' AND e.type=?'; args.append(event_type)
    if tasks: query += " AND e.status IN ('todo','done')"
    with connection() as db:
        items = [event_dict(db,r,user_id) for r in db.execute(query+' ORDER BY julianday(e.start_time)',args)]
    return [e for e in items if not status or e['status']==status]


def get_event(user_id, event_id):
    with connection() as db:
        return event_dict(db, accessible(db,user_id,event_id), user_id)


def create_event(user_id, data):
    values = data.model_dump(mode='json')
    if values['type'] != 'personal': raise HTTPException(400, '클리닉은 아우라의 새 회차로 등록해주세요.')
    with connection() as db:
        if values.get('project_id'): member(db,user_id,values['project_id'])
        if values.get('project_id') and values['status']=='done': values['status']='todo'
        keys = ['title','description','start_time','end_time','is_all_day','status','type','group_name','category_name','location','web_url','project_id','task_available_from','task_due_at']
        cursor = db.execute(f"INSERT INTO events(user_id,{','.join(keys)}) VALUES ({','.join('?' for _ in range(len(keys)+1))})", [user_id]+[values.get(k) for k in keys])
        db.commit()
        return event_dict(db,accessible(db,user_id,cursor.lastrowid),user_id)


def create_series(user_id, data):
    from uuid import uuid4
    from .schemas import EventCreate
    # Validate everything before writing; preserve the existing weekly repeat affordance.
    group = str(uuid4())
    count = data.repeat_count
    if data.repeat_until:
        count = min(365,int((data.repeat_until-data.start_time).days/(7*data.interval_weeks))+1)
    if count < 2: raise HTTPException(400,'반복 종료일을 확인해주세요.')
    if data.type!='personal': raise HTTPException(400,'클리닉은 아우라의 새 회차로 등록해주세요.')
    keys=['title','description','start_time','end_time','is_all_day','status','type','group_name','category_name','location','web_url','project_id','task_available_from','task_due_at']
    ids=[]
    with connection() as db:
        if data.project_id: member(db,user_id,data.project_id)
        for index in range(count):
            fields=data.model_dump()
            delta=timedelta(weeks=index*data.interval_weeks)
            fields.update(start_time=data.start_time+delta,end_time=data.end_time+delta if data.end_time else None)
            for key in ('task_available_from','task_due_at'):
                fields[key] = getattr(data,key)+delta if getattr(data,key) else None
            values=EventCreate(**fields).model_dump(mode='json')
            if data.project_id and values['status']=='done': values['status']='todo'
            cur=db.execute(f"INSERT INTO events(user_id,{','.join(keys)},recurrence_group_id,recurrence_index) VALUES({','.join('?' for _ in range(len(keys)+3))})",[user_id]+[values[k] for k in keys]+[group,index])
            ids.append(cur.lastrowid)
        db.commit()
        return [event_dict(db,accessible(db,user_id,i),user_id) for i in ids]


def update_event(user_id,event_id,data):
    fields=data.model_dump(exclude_unset=True,mode='json')
    scope=fields.pop('scope','this')
    with connection() as db:
        current=accessible(db,user_id,event_id)
        if not event_dict(db,current,user_id)['canEdit']: raise HTTPException(403,'연결된 서비스에서 관리하는 읽기 전용 일정입니다.')
        if current['completion_source'] != 'manual':
            for key in ('status','task_available_from','task_due_at'):
                fields.pop(key, None)
        elif fields.get('status') == 'done':
            available=fields.get('task_available_from',current['task_available_from'])
            if available and datetime.fromisoformat(available.replace('Z','+00:00')).timestamp() > datetime.now(timezone.utc).timestamp():
                raise HTTPException(400,'아직 시작할 수 없는 할 일입니다.')
        if 'project_id' in fields and fields['project_id'] != current['project_id']:
            raise HTTPException(400,'기존 일정의 프로젝트는 변경할 수 없습니다.')
        if current['project_id'] and 'status' in fields and fields['status'] in ('todo','done'):
            done=fields.pop('status')=='done'
            if current['status']=='passive': fields['status']='todo'
            db.execute('INSERT INTO calendar_completions VALUES(?,?,?) ON CONFLICT(event_id,user_id) DO UPDATE SET completed=excluded.completed',(event_id,user_id,done))
            db.commit()
        rows=[current]
        if scope=='following' and current['recurrence_group_id']:
            rows=db.execute('SELECT * FROM events WHERE recurrence_group_id=? AND recurrence_index>=?',(current['recurrence_group_id'],current['recurrence_index'])).fetchall()
        round_row=db.execute('SELECT id FROM aura_clinic_rounds WHERE event_id=?',(event_id,)).fetchone()
        session=db.execute('SELECT id FROM aura_sessions WHERE event_id=?',(event_id,)).fetchone()
    if current['type']=='aura':
        if fields.get('is_all_day') or fields.get('project_id'): raise HTTPException(400,'클리닉은 시간 지정 개인 일정으로 관리됩니다.')
        timing={k:v for k,v in fields.items() if k in ('start_time','end_time','description')}
        if round_row and timing: legacy.update_clinic_round(user_id,round_row['id'],ClinicRoundUpdate(**timing,scope=scope))
        elif session and timing: legacy.update_session(user_id,session['id'],SessionUpdate(**{k:v for k,v in timing.items() if k!='description'}))
        fields={k:v for k,v in fields.items() if k in ('location','web_url','category_name','description')}
    allowed={'title','description','start_time','end_time','is_all_day','status','category_name','group_name','location','web_url','task_available_from','task_due_at'}
    fields={k:v for k,v in fields.items() if k in allowed}
    def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
    with connection() as db:
        for row in rows:
            accessible(db,user_id,row['id'])
            update=dict(fields)
            if scope=='following' and ('start_time' in update or 'end_time' in update):
                start=dt(update.get('start_time') or current['start_time'])
                end=dt(update.get('end_time') or current['end_time']) if update.get('end_time',current['end_time']) else None
                shifted=dt(row['start_time'])+(start-dt(current['start_time']))
                update.update(start_time=shifted.isoformat(),end_time=(shifted+(end-start)).isoformat() if end else None)
            start=update.get('start_time',row['start_time']); end=update.get('end_time',row['end_time'])
            if end and dt(end)<dt(start): raise HTTPException(400,'종료 시간은 시작 이후여야 합니다.')
            available=update.get('task_available_from',row['task_available_from'])
            due=update.get('task_due_at',row['task_due_at'])
            if available and due and dt(due)<dt(available): raise HTTPException(400,'마감은 시작 가능일 이후여야 합니다.')
            if update: db.execute(f"UPDATE events SET {','.join(k+'=?' for k in update)},updated_at=CURRENT_TIMESTAMP WHERE id=?",[*update.values(),row['id']])
        db.commit()
    return get_event(user_id,event_id)


def delete_event(user_id,event_id,scope='this'):
    if scope not in ('this','following'): raise HTTPException(400,'잘못된 삭제 범위입니다.')
    with connection() as db:
        row=accessible(db,user_id,event_id)
        if not event_dict(db,row,user_id)['canEdit']: raise HTTPException(403,'연결된 서비스에서 관리하는 읽기 전용 일정입니다.')
        clinic=db.execute('SELECT id FROM aura_clinic_rounds WHERE event_id=?',(event_id,)).fetchone()
        session=db.execute('SELECT id FROM aura_sessions WHERE event_id=?',(event_id,)).fetchone()
    if clinic: return legacy.delete_clinic_round(user_id,clinic['id'])
    if session: return legacy.delete_session(user_id,session['id'])
    with connection() as db:
        if scope=='following' and row['recurrence_group_id']:
            db.execute('DELETE FROM events WHERE recurrence_group_id=? AND recurrence_index>=?',(row['recurrence_group_id'],row['recurrence_index']))
        else: db.execute('DELETE FROM events WHERE id=?',(event_id,))
        db.commit()


def projects(user_id):
    with connection() as db:
        return [dict(r) for r in db.execute('''SELECT p.*, (SELECT COUNT(*) FROM calendar_members m WHERE m.project_id=p.id) AS memberCount
            FROM calendar_projects p JOIN calendar_members m ON p.id=m.project_id WHERE m.user_id=?''',(user_id,))]


def create_project(user_id,name,parent_id=None,isolate_tasks=False):
    with connection() as db:
        validate_project_parent(db,user_id,None,parent_id)
        if not name.strip(): raise HTTPException(400,'프로젝트 이름을 입력해주세요.')
        cur=db.execute('INSERT INTO calendar_projects(name,owner_id,parent_id,isolate_tasks) VALUES(?,?,?,?)',(name.strip(),user_id,parent_id,int(isolate_tasks)))
        db.execute('INSERT INTO calendar_members VALUES(?,?)',(cur.lastrowid,user_id)); db.commit()
    return projects(user_id)



def validate_project_parent(db,user_id,project_id,parent_id):
    seen={project_id}
    while parent_id is not None:
        if parent_id in seen: raise HTTPException(400,'프로젝트를 자기 자신이나 하위 프로젝트에 넣을 수 없습니다.')
        seen.add(parent_id)
        row=db.execute('SELECT * FROM calendar_projects WHERE id=? AND owner_id=?',(parent_id,user_id)).fetchone()
        if not row: raise HTTPException(403,'소유한 프로젝트만 상위 프로젝트로 지정할 수 있습니다.')
        parent_id=row['parent_id']


def update_project(user_id,project_id,name,parent_id,isolate_tasks):
    with connection() as db:
        if not db.execute('SELECT 1 FROM calendar_projects WHERE id=? AND owner_id=?',(project_id,user_id)).fetchone():
            raise HTTPException(403,'프로젝트 소유자만 설정을 변경할 수 있습니다.')
        if not name.strip(): raise HTTPException(400,'프로젝트 이름을 입력해주세요.')
        validate_project_parent(db,user_id,project_id,parent_id)
        db.execute('UPDATE calendar_projects SET name=?,parent_id=?,isolate_tasks=? WHERE id=?',(name.strip(),parent_id,int(isolate_tasks),project_id))
        db.commit()
    return projects(user_id)


def invite(user_id,project_id,email):
    token=secrets.token_urlsafe(32)
    with connection() as db:
        project=db.execute('SELECT * FROM calendar_projects WHERE id=? AND owner_id=?',(project_id,user_id)).fetchone()
        if not project: raise HTTPException(403,'프로젝트 소유자만 초대할 수 있습니다.')
        db.execute('INSERT INTO calendar_invites VALUES(?,?,?,?,0)',(hashlib.sha256(token.encode()).hexdigest(),project_id,email.strip().lower(),(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()))
        db.commit()
    return {'token':token,'projectName':project['name']}


def accept(user_id,token,email):
    with connection() as db:
        row=db.execute('SELECT * FROM calendar_invites WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or row['accepted'] or row['expires_at']<datetime.now(timezone.utc).isoformat(): raise HTTPException(400,'초대가 만료되었거나 이미 사용되었습니다.')
        if row['email']!=email.strip().lower(): raise HTTPException(403,'초대받은 이메일의 계정으로 로그인해주세요.')
        db.execute('INSERT OR IGNORE INTO calendar_members VALUES(?,?)',(row['project_id'],user_id))
        db.execute('UPDATE calendar_invites SET accepted=1 WHERE token_hash=?',(row['token_hash'],)); db.commit()
    return projects(user_id)


init_workspace()
