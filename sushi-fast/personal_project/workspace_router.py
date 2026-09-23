import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Literal

from auth import JMT, userdb
from .router import current_user_id
from . import workspace, google_calendar, google_transfer
from .db import connection

router=APIRouter(prefix='/api/personal',tags=['calendar-workspace'])


class ProjectCreate(BaseModel):
    name: str=Field(min_length=1,max_length=80)
    parent_id: int | None=None
    isolate_tasks: bool=False
class Invite(BaseModel):
    email: str=Field(min_length=3,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
class Token(BaseModel):
    token: str=Field(min_length=16,max_length=200)
class Selection(BaseModel):
    calendar_ids: list[str]=Field(max_length=100)
class Export(BaseModel):
    calendar_id: str=Field(max_length=500)
    event_id: int
class Transfer(BaseModel):
    calendar_id: str=Field(min_length=1,max_length=500)
    starts_on: date
    ends_on: date
    preview_token: str | None=Field(default=None,min_length=64,max_length=64)

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
    return workspace.create_project(user_id,data.name.strip(),data.parent_id,data.isolate_tasks)

@router.put('/calendar/projects/{project_id}')
def update_project(project_id: int,data: ProjectCreate,user_id: int=Depends(current_user_id)):
    return workspace.update_project(user_id,project_id,data.name,data.parent_id,data.isolate_tasks)

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

@router.post('/google/accounts/{account_id}/transfer')
def transfer(account_id: int,data: Transfer,user_id: int=Depends(current_user_id)):
    return google_transfer.transfer(user_id,account_id,data.calendar_id,data.starts_on,data.ends_on,data.preview_token)

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
def feed(request: Request, view: Literal['upcoming','day','week','month','tasks']='upcoming'):
    token=request.headers.get('authorization','').removeprefix('Bearer ')
    with connection() as db:
        row=db.execute('SELECT user_id FROM widget_devices WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise HTTPException(401,'위젯을 다시 연결해주세요.')
    now=datetime.now(timezone.utc)
    local=now.astimezone(ZoneInfo('Asia/Seoul'))
    start=local.replace(hour=0,minute=0,second=0,microsecond=0)
    end=start+timedelta(days=7)
    if view=='month':
        start=start.replace(day=1)
        end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    elif view=='day': end=start+timedelta(days=1)
    elif view=='week':
        start-=timedelta(days=(start.weekday()+1)%7)
        end=start+timedelta(days=7)
    elif view=='upcoming': start=now-timedelta(days=1)
    items=workspace.list_events(row['user_id'],tasks=True) if view=='tasks' else workspace.list_events(row['user_id'],start.isoformat(),end.isoformat())
    def include(e):
        if e['status']=='done': return False
        if view!='upcoming': return True
        ending=datetime.fromisoformat((e['endTime'] or e['startTime']).replace('Z','+00:00'))
        if ending.tzinfo is None: ending=ending.replace(tzinfo=ZoneInfo('Asia/Seoul'))
        if not e['endTime']: ending+=timedelta(hours=1)
        return ending>=now
    return {'events':[{k:e[k] for k in ('id','title','startTime','endTime','isAllDay','status')} for e in items if include(e)][:500], 'timezone':'Asia/Seoul'}

@router.delete('/calendar/widget/devices',status_code=204)
def revoke_widgets(user_id: int=Depends(current_user_id)):
    with connection() as db:
        db.execute('DELETE FROM widget_devices WHERE user_id=?',(user_id,)); db.commit()
    return Response(status_code=204)


class DailyNote(BaseModel):
    content: str = Field(max_length=100000)
    drawing: str = Field(default='', max_length=2_000_000)
    rich_document: str = Field(default='', max_length=500000)

@router.get('/calendar/daily-notes/{day}')
def daily_note(day: date, user_id: int=Depends(current_user_id)):
    with connection() as db:
        row = db.execute('SELECT content,drawing,rich_document FROM calendar_daily_notes WHERE user_id=? AND day=?', (user_id,day.isoformat())).fetchone()
        if row:
            return {'content': row['content'], 'drawing': row['drawing'], 'richDocument':row['rich_document'], 'inheritedFrom': None}
        previous = db.execute(
            'SELECT day,content,drawing,rich_document FROM calendar_daily_notes WHERE user_id=? AND day=?',
            (user_id, (day - timedelta(days=1)).isoformat()),
        ).fetchone()
        return {'content': previous['content'] if previous else '', 'drawing': previous['drawing'] if previous else '', 'richDocument':previous['rich_document'] if previous else '', 'inheritedFrom': previous['day'] if previous else None}

@router.put('/calendar/daily-notes/{day}')
def save_daily_note(day: date, data: DailyNote, user_id: int=Depends(current_user_id)):
    with connection() as db:
        db.execute('INSERT INTO calendar_daily_notes(user_id,day,content,drawing,rich_document) VALUES(?,?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET content=excluded.content,drawing=excluded.drawing,rich_document=excluded.rich_document', (user_id,day.isoformat(),data.content,data.drawing,data.rich_document))
        db.commit()
    return {'content': data.content, 'drawing': data.drawing}


from . import student_services as student

@router.get('/student/profile')
def student_profile(user_id: int=Depends(current_user_id)):
    return student.profile(user_id)

@router.put('/student/profile')
def update_student_profile(data: student.Profile,user_id: int=Depends(current_user_id)):
    return student.save_profile(user_id,data)

@router.post('/student/timetable/preview')
def preview_timetable(data: student.Timetable,user_id: int=Depends(current_user_id)):
    return student.preview(data)

@router.post('/student/timetable/import')
def import_timetable(data: student.Timetable,user_id: int=Depends(current_user_id)):
    return student.import_timetable(user_id,data)


from . import project_connectors as connectors
from .schemas import EventCreate

class ConnectorCreate(BaseModel):
    name: str=Field(min_length=1,max_length=80)

@router.get('/calendar/projects/{project_id}/connectors')
def list_connectors(project_id:int,user_id:int=Depends(current_user_id)):
    return connectors.list_connectors(user_id,project_id)

@router.post('/calendar/projects/{project_id}/connectors')
def create_connector(project_id:int,data:ConnectorCreate,user_id:int=Depends(current_user_id)):
    return connectors.create(user_id,project_id,data.name)

@router.delete('/calendar/projects/{project_id}/connectors/{connector_id}',status_code=204)
def revoke_connector(project_id:int,connector_id:int,user_id:int=Depends(current_user_id)):
    connectors.revoke(user_id,project_id,connector_id)
    return Response(status_code=204)

@router.put('/calendar/integrations/events/{external_id}')
def integration_event(external_id:str,data:EventCreate,request:Request):
    if not 1<=len(external_id)<=160: raise HTTPException(400,'외부 일정 ID는 1~160자입니다.')
    return connectors.upsert(request.headers.get('authorization','').removeprefix('Bearer '),external_id,data)

@router.delete('/calendar/integrations/events/{external_id}',status_code=204)
def remove_integration_event(external_id:str,request:Request):
    connectors.remove(request.headers.get('authorization','').removeprefix('Bearer '),external_id)
    return Response(status_code=204)

from . import student_community as community

@router.get('/student/curriculum')
def curriculum(cohort:int,track:Literal['major','double','minor']='major',user_id:int=Depends(current_user_id)):
    return community.curriculum(user_id,cohort,track)

@router.post('/student/curriculum')
def revise_curriculum(data:community.CurriculumEdit,user_id:int=Depends(current_user_id)):
    return community.revise(user_id,data)

@router.get('/student/board')
def department_posts(user_id:int=Depends(current_user_id)):
    return community.posts(user_id)

@router.post('/student/board')
def department_post(data:community.Post,user_id:int=Depends(current_user_id)):
    return community.post(user_id,data)

@router.delete('/student/board/{post_id}',status_code=204)
def hide_department_post(post_id:int,user_id:int=Depends(current_user_id)):
    community.hide_post(user_id,post_id)
    return Response(status_code=204)

@router.post('/student/board/{post_id}/calendar')
def add_department_calendar(post_id:int,user_id:int=Depends(current_user_id)):
    return community.add_to_calendar(user_id,post_id)
