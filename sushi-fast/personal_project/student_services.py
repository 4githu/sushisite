"""Opt-in university profile and semester timetable imports; no provider credentials."""
import hashlib
import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from .db import connection


class Profile(BaseModel):
    is_student: bool = False
    school: str = Field(default='', max_length=120)
    department: str = Field(default='', max_length=120)

    @model_validator(mode='after')
    def validate_school(self):
        self.school = ' '.join(self.school.split())
        if self.school == '서울대': self.school = '서울대학교'
        self.department = self.department.strip()
        if self.is_student and not self.school:
            raise ValueError('학교를 입력해주세요.')
        return self


class Lesson(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    weekday: int = Field(ge=0, le=6)  # Monday=0
    start: time
    end: time
    location: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def validate_time(self):
        self.title = self.title.strip()
        if not self.title or self.start >= self.end or self.start.tzinfo or self.end.tzinfo:
            raise ValueError('수업 이름과 같은 날의 시작·종료 시간을 확인해주세요.')
        return self


class Timetable(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    starts_on: date
    ends_on: date
    skip_holidays: bool = True
    excluded_dates: list[date] = Field(default_factory=list, max_length=200)
    lessons: list[Lesson] = Field(min_length=1, max_length=60)

    @model_validator(mode='after')
    def validate_term(self):
        if not 0 <= (self.ends_on - self.starts_on).days <= 200:
            raise ValueError('학기는 1~201일 범위로 입력해주세요.')
        if self.starts_on.year < 2000 or self.ends_on.year > 2100:
            raise ValueError('2000~2100년을 지원합니다.')
        return self


def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS student_profiles(user_id INTEGER PRIMARY KEY, is_student INTEGER NOT NULL, school TEXT NOT NULL, department TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS student_timetable_imports(user_id INTEGER NOT NULL, fingerprint TEXT NOT NULL, event_ids TEXT NOT NULL, PRIMARY KEY(user_id,fingerprint));
        ''')
        db.commit()


def profile(user_id):
    with connection() as db:
        row = db.execute('SELECT * FROM student_profiles WHERE user_id=?', (user_id,)).fetchone()
    return dict(row) if row else {'is_student':False,'school':'','department':'','configured':False}


def save_profile(user_id, data):
    with connection() as db:
        db.execute('INSERT INTO student_profiles VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET is_student=excluded.is_student,school=excluded.school,department=excluded.department',
                   (user_id,int(data.is_student),data.school,data.department))
        db.commit()
    return profile(user_id)


def preview(data):
    excluded = set(data.excluded_dates)
    days = holidays.country_holidays('KR', years=range(data.starts_on.year,data.ends_on.year+1), language='ko') if data.skip_holidays else {}
    events, skipped, seen = [], [], set()
    day = data.starts_on
    while day <= data.ends_on:
        for lesson in data.lessons:
            if lesson.weekday != day.weekday(): continue
            if day in excluded or day in days:
                skipped.append({'date':str(day),'title':lesson.title,'reason':'직접 지정한 휴강일' if day in excluded else days[day]})
                continue
            start = datetime.combine(day,lesson.start,ZoneInfo('Asia/Seoul')).isoformat()
            end = datetime.combine(day,lesson.end,ZoneInfo('Asia/Seoul')).isoformat()
            key=(lesson.title,start,end,lesson.location)
            if key in seen: continue
            seen.add(key)
            events.append({'title':lesson.title,'startTime':start,'endTime':end,'location':lesson.location})
        day += timedelta(days=1)
    return {'events':sorted(events,key=lambda e:e['startTime']),'skipped':skipped,'holidaySource':'python-holidays KR (임시공휴일은 직접 휴강일 추가 가능)'}


def import_timetable(user_id,data):
    if not profile(user_id)['is_student']: raise HTTPException(400,'학생 서비스를 먼저 설정해주세요.')
    plan = preview(data)
    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT event_ids FROM student_timetable_imports WHERE user_id=? AND fingerprint=?',(user_id,fingerprint)).fetchone()
        if previous: return {'created':0,'alreadyImported':True,'eventIds':json.loads(previous['event_ids'])}
        ids=[]
        for event in plan['events']:
            row = db.execute('''INSERT INTO events(user_id,title,start_time,end_time,status,type,category_name,location,group_name)
                              VALUES(?,?,?,?,?,?,?,?,?)''',(user_id,event['title'],event['startTime'],event['endTime'],'passive','personal','수업',event['location'],data.name))
            ids.append(row.lastrowid)
        db.execute('INSERT INTO student_timetable_imports VALUES(?,?,?)',(user_id,fingerprint,json.dumps(ids)))
        db.commit()
    return {'created':len(ids),'alreadyImported':False,'eventIds':ids}

init()
