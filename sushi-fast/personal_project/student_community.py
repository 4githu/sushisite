"""Department community data. Official reviews and community edits are separate revisions."""
import os
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from fastapi import HTTPException
from .db import connection
from .student_services import profile

class CurriculumEdit(BaseModel):
    cohort: int = Field(ge=2000,le=2100)
    track: Literal['major','double','minor']='major'
    edition: Literal['community','official']='community'
    content: str=Field(min_length=1,max_length=30000)
    source_url: str=Field(default='',max_length=2000,pattern=r'^(https://[^\s\\]+)?$')
    base_revision: int=Field(default=0,ge=0)

class Post(BaseModel):
    title: str=Field(min_length=1,max_length=120)
    content: str=Field(default='',max_length=5000)
    start: datetime | None=None
    end: datetime | None=None
    @model_validator(mode='after')
    def times(self):
        if self.start and not self.start.tzinfo: raise ValueError('시간대가 필요합니다.')
        if self.end and (not self.start or not self.end.tzinfo or self.end<=self.start): raise ValueError('종료 시간은 시작 이후여야 합니다.')
        return self


def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS student_curriculum_revisions(id INTEGER PRIMARY KEY,school TEXT NOT NULL,department TEXT NOT NULL,cohort INTEGER NOT NULL,track TEXT NOT NULL,edition TEXT NOT NULL,revision INTEGER NOT NULL,content TEXT NOT NULL,source_url TEXT NOT NULL,author_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(school,department,cohort,track,edition,revision));
        CREATE TABLE IF NOT EXISTS student_board(id INTEGER PRIMARY KEY,school TEXT NOT NULL,department TEXT NOT NULL,author_id INTEGER NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,start_time TEXT,end_time TEXT,deleted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS student_board_calendar(post_id INTEGER NOT NULL REFERENCES student_board(id),user_id INTEGER NOT NULL,event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,PRIMARY KEY(post_id,user_id));
        ''')
        db.commit()


def department(user_id):
    p=profile(user_id)
    if not p['is_student'] or not p['school'] or not p['department']:
        raise HTTPException(400,'학교와 학과를 먼저 저장해주세요.')
    return p['school'],p['department']


def curriculum(user_id,cohort,track):
    school,dept=department(user_id)
    with connection() as db:
        rows=db.execute('''SELECT * FROM student_curriculum_revisions WHERE school=? AND department=? AND cohort=? AND track=? ORDER BY revision DESC,id DESC''',(school,dept,cohort,track)).fetchall()
    latest={}
    for row in rows:
        latest.setdefault(row['edition'],dict(row))
    return {'versions':list(latest.values()),'canPublishOfficial':str(user_id) in os.getenv('STUDENT_CURRICULUM_EDITORS','').split(',')}


def revise(user_id,data):
    school,dept=department(user_id)
    if data.edition=='official' and str(user_id) not in os.getenv('STUDENT_CURRICULUM_EDITORS','').split(','):
        raise HTTPException(403,'사이트 검토본은 지정된 검토자만 발행할 수 있습니다.')
    if data.edition=='official' and not data.source_url: raise HTTPException(400,'검토본에는 원문 출처가 필요합니다.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        revision=db.execute('SELECT COALESCE(MAX(revision),0) FROM student_curriculum_revisions WHERE school=? AND department=? AND cohort=? AND track=? AND edition=?',(school,dept,data.cohort,data.track,data.edition)).fetchone()[0]
        if revision!=data.base_revision: raise HTTPException(409,'다른 사람이 먼저 수정했습니다. 최신 버전을 확인한 뒤 다시 저장해주세요.')
        db.execute('INSERT INTO student_curriculum_revisions(school,department,cohort,track,edition,revision,content,source_url,author_id) VALUES(?,?,?,?,?,?,?,?,?)',(school,dept,data.cohort,data.track,data.edition,revision+1,data.content,data.source_url,user_id))
        db.commit()
    return curriculum(user_id,data.cohort,data.track)


def posts(user_id):
    school,dept=department(user_id)
    with connection() as db:
        return [dict(row) | {'canDelete':row['author_id']==user_id} for row in db.execute('SELECT * FROM student_board WHERE school=? AND department=? AND deleted=0 ORDER BY id DESC LIMIT 100',(school,dept))]


def post(user_id,data):
    school,dept=department(user_id)
    if not data.title.strip(): raise HTTPException(400,'제목을 입력해주세요.')
    with connection() as db:
        db.execute('INSERT INTO student_board(school,department,author_id,title,content,start_time,end_time) VALUES(?,?,?,?,?,?,?)',(school,dept,user_id,data.title.strip(),data.content,data.start.isoformat() if data.start else None,data.end.isoformat() if data.end else None))
        db.commit()
    return posts(user_id)


def hide_post(user_id,post_id):
    with connection() as db:
        if not db.execute('UPDATE student_board SET deleted=1 WHERE id=? AND author_id=?',(post_id,user_id)).rowcount:
            raise HTTPException(403,'본인이 작성한 글만 삭제할 수 있습니다.')
        db.commit()


def add_to_calendar(user_id,post_id):
    school,dept=department(user_id)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        post=db.execute('SELECT * FROM student_board WHERE id=? AND school=? AND department=? AND deleted=0',(post_id,school,dept)).fetchone()
        if not post or not post['start_time']: raise HTTPException(404,'학과 일정을 찾을 수 없습니다.')
        previous=db.execute('SELECT event_id FROM student_board_calendar WHERE post_id=? AND user_id=?',(post_id,user_id)).fetchone()
        if previous and previous['event_id']: return {'eventId':previous['event_id'],'alreadyAdded':True}
        event=db.execute("INSERT INTO events(user_id,title,description,start_time,end_time,status,category_name) VALUES(?,?,?,?,?,'passive','학과 일정')",(user_id,post['title'],post['content'],post['start_time'],post['end_time']))
        db.execute('INSERT INTO student_board_calendar VALUES(?,?,?) ON CONFLICT(post_id,user_id) DO UPDATE SET event_id=excluded.event_id',(post_id,user_id,event.lastrowid))
        db.commit()
    return {'eventId':event.lastrowid,'alreadyAdded':False}

init()
