"""Project-scoped write-only integrations with hashed, revocable keys and idempotent IDs."""
import hashlib
import secrets
from fastapi import HTTPException
from .db import connection
from . import workspace


def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS project_connectors(id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES calendar_projects(id) ON DELETE CASCADE, name TEXT NOT NULL, token_hash TEXT UNIQUE, owner_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS project_connector_events(connector_id INTEGER NOT NULL REFERENCES project_connectors(id) ON DELETE CASCADE, external_id TEXT NOT NULL, event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, PRIMARY KEY(connector_id,external_id));
        ''')
        db.commit()


def owner(db,user_id,project_id):
    if not db.execute('SELECT 1 FROM calendar_projects WHERE id=? AND owner_id=?',(project_id,user_id)).fetchone():
        raise HTTPException(403,'프로젝트 소유자만 연동을 관리할 수 있습니다.')


def list_connectors(user_id,project_id):
    with connection() as db:
        owner(db,user_id,project_id)
        return [dict(r) for r in db.execute("SELECT id,name,token_hash IS NOT NULL AS active FROM project_connectors WHERE project_id=?",(project_id,))]


def create(user_id,project_id,name):
    if not name.strip(): raise HTTPException(400,'연동 이름을 입력해주세요.')
    token=secrets.token_urlsafe(32)
    with connection() as db:
        owner(db,user_id,project_id)
        row=db.execute('INSERT INTO project_connectors(project_id,name,token_hash,owner_id) VALUES(?,?,?,?)',(project_id,name.strip(),hashlib.sha256(token.encode()).hexdigest(),user_id))
        db.commit()
        return {'id':row.lastrowid,'token':token}


def revoke(user_id,project_id,connector_id):
    with connection() as db:
        owner(db,user_id,project_id)
        db.execute('UPDATE project_connectors SET token_hash=NULL WHERE id=? AND project_id=?',(connector_id,project_id))
        db.commit()


def authenticated(db,token):
    row=db.execute('SELECT c.* FROM project_connectors c JOIN calendar_projects p ON p.id=c.project_id AND p.owner_id=c.owner_id WHERE c.token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise HTTPException(401,'유효한 프로젝트 연동 키가 필요합니다.')
    return row


def upsert(token,external_id,data):
    values=data.model_dump(mode='json')
    keys=['title','description','start_time','end_time','is_all_day','status','location','web_url','task_available_from','task_due_at']
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        connector=authenticated(db,token)
        link=db.execute('SELECT event_id FROM project_connector_events WHERE connector_id=? AND external_id=?',(connector['id'],external_id)).fetchone()
        if link:
            event_id=link['event_id']
            db.execute(f"UPDATE events SET {','.join(k+'=?' for k in keys)},updated_at=CURRENT_TIMESTAMP WHERE id=?", [values[k] for k in keys]+[event_id])
        else:
            row=db.execute(f"INSERT INTO events(user_id,project_id,type,completion_source,category_name,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+5))})",[connector['owner_id'],connector['project_id'],'integration','external',connector['name']]+[values[k] for k in keys])
            event_id=row.lastrowid
            db.execute('INSERT INTO project_connector_events VALUES(?,?,?)',(connector['id'],external_id,event_id))
        db.commit()
    return {'eventId':event_id}


def remove(token,external_id):
    with connection() as db:
        connector=authenticated(db,token)
        row=db.execute('SELECT event_id FROM project_connector_events WHERE connector_id=? AND external_id=?',(connector['id'],external_id)).fetchone()
        if row: db.execute('DELETE FROM events WHERE id=?',(row['event_id'],))
        db.commit()

init()
