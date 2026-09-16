import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Literal

from auth import JMT, userdb
from .router import current_user_id
from . import workspace, google_calendar
from .db import connection

router=APIRouter(prefix='/api/personal',tags=['calendar-workspace'])


class ProjectCreate(BaseModel):
    name: str=Field(min_length=1,max_length=80)
class Invite(BaseModel):
    email: str=Field(min_length=3,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
class Token(BaseModel):
    token: str=Field(min_length=16,max_length=200)
class Selection(BaseModel):
    calendar_ids: list[str]=Field(max_length=100)
class Export(BaseModel):
    calendar_id: str=Field(max_length=500)
    event_id: int
class ConflictChoice(BaseModel):
    calendar_id: str
    google_id: str
    choice: Literal['local','google']


@router.get('/calendar/tasks')
def tasks(user_id: int=Depends(current_user_id)):
    return workspace.list_events(user_id,tasks=True)

@router.get('/calendar/projects')
def projects(user_id: int=Depends(current_user_id)):
    return workspace.projects(user_id)

@router.post('/calendar/projects')
def create_project(data: ProjectCreate,user_id: int=Depends(current_user_id)):
    return workspace.create_project(user_id,data.name.strip())

@router.post('/calendar/projects/{project_id}/invites')
def invite(project_id: int,data: Invite,user_id: int=Depends(current_user_id)):
    return workspace.invite(user_id,project_id,data.email)

@router.post('/calendar/invites/accept')
def accept(data: Token,user_id: int=Depends(current_user_id)):
    user=userdb.get_user(user_id=user_id)
    return workspace.accept(user_id,data.token,user['email'])

@router.get('/google/accounts')
def accounts(user_id: int=Depends(current_user_id)):
    return google_calendar.list_accounts(user_id)

@router.get('/google/accounts/{account_id}/calendars')
def calendars(account_id: int,user_id: int=Depends(current_user_id)):
    return google_calendar.calendars(user_id,account_id)

@router.put('/google/accounts/{account_id}/calendars')
def selection(account_id: int,data: Selection,user_id: int=Depends(current_user_id)):
    return google_calendar.select_calendars(user_id,account_id,data.calendar_ids)

@router.post('/google/accounts/{account_id}/sync')
def sync(account_id: int,user_id: int=Depends(current_user_id)):
    return google_calendar.sync_account(user_id,account_id)

@router.post('/google/accounts/{account_id}/export')
def export(account_id: int,data: Export,user_id: int=Depends(current_user_id)):
    return google_calendar.export_event(user_id,account_id,data.calendar_id,data.event_id)

@router.delete('/google/accounts/{account_id}',status_code=204)
def disconnect(account_id: int,user_id: int=Depends(current_user_id)):
    google_calendar.disconnect(user_id,account_id)
    return Response(status_code=204)

@router.get('/google/accounts/{account_id}/conflicts')
def conflicts(account_id: int,user_id: int=Depends(current_user_id)):
    return google_calendar.conflicts_for(user_id,account_id)

@router.post('/google/accounts/{account_id}/conflicts')
def resolve(account_id: int,data: ConflictChoice,user_id: int=Depends(current_user_id)):
    return google_calendar.resolve_conflict(user_id,account_id,data.calendar_id,data.google_id,data.choice)

@router.post('/calendar/widget/pair')
def pair(user_id: int=Depends(current_user_id)):
    code=secrets.token_urlsafe(24)
    with connection() as db:
        db.execute('DELETE FROM widget_pairs WHERE expires<?',(datetime.now(timezone.utc).isoformat(),))
        db.execute('INSERT INTO widget_pairs VALUES(?,?,?)',(hashlib.sha256(code.encode()).hexdigest(),user_id,(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())); db.commit()
    return {'code':code,'expiresIn':300}

@router.post('/calendar/widget/claim')
def claim(data: Token):
    token=secrets.token_urlsafe(32)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM widget_pairs WHERE code_hash=?',(hashlib.sha256(data.token.encode()).hexdigest(),)).fetchone()
        if not row or row['expires']<datetime.now(timezone.utc).isoformat(): raise HTTPException(400,'연결 코드가 만료되었습니다.')
        db.execute('DELETE FROM widget_pairs WHERE code_hash=?',(row['code_hash'],))
        db.execute('INSERT INTO widget_devices VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['user_id'],datetime.now(timezone.utc).isoformat(),'Android 위젯')); db.commit()
    return {'token':token}

@router.get('/calendar/widget/feed')
def feed(request: Request):
    token=request.headers.get('authorization','').removeprefix('Bearer ')
    with connection() as db:
        row=db.execute('SELECT user_id FROM widget_devices WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise HTTPException(401,'위젯을 다시 연결해주세요.')
    now=datetime.now(timezone.utc)
    items=workspace.list_events(row['user_id'],(now-timedelta(days=1)).isoformat(),(now+timedelta(days=7)).isoformat())
    def upcoming(e):
        end=datetime.fromisoformat((e['endTime'] or e['startTime']).replace('Z','+00:00'))
        if end.tzinfo is None: end=end.replace(tzinfo=ZoneInfo('Asia/Seoul'))
        if not e['endTime']: end+=timedelta(hours=1)
        return end>=now and e['status']!='done'
    return {'events':[{k:e[k] for k in ('id','title','startTime','endTime','isAllDay','status')} for e in items if upcoming(e)][:20]}

@router.delete('/calendar/widget/devices',status_code=204)
def revoke_widgets(user_id: int=Depends(current_user_id)):
    with connection() as db:
        db.execute('DELETE FROM widget_devices WHERE user_id=?',(user_id,)); db.commit()
    return Response(status_code=204)
