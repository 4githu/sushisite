"""Opt-in university profile and semester timetable imports; no provider credentials."""
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from .db import connection


class Profile(BaseModel):
    admission_year: int | None = Field(default=None, ge=1950, le=2100)
    academic_offset: int = Field(default=0, ge=-20, le=20)
    is_student: bool = False
    school: str = Field(default='', max_length=120)
    department: str = Field(default='', max_length=120)

    @model_validator(mode='after')
    def validate_school(self):
        self.school = ' '.join(self.school.split())
        from .campuses import normalize
        self.school = normalize(self.school)
        from .campus_directory import normalize_department
        self.department = normalize_department(self.school,self.department)
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
        CREATE TABLE IF NOT EXISTS student_course_exclusions(user_id INTEGER NOT NULL,code TEXT NOT NULL,PRIMARY KEY(user_id,code));
        CREATE TABLE IF NOT EXISTS student_profiles(user_id INTEGER PRIMARY KEY, is_student INTEGER NOT NULL, school TEXT NOT NULL, department TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS student_timetable_imports(user_id INTEGER NOT NULL, fingerprint TEXT NOT NULL, event_ids TEXT NOT NULL, PRIMARY KEY(user_id,fingerprint));
        CREATE TABLE IF NOT EXISTS student_major_plans(user_id INTEGER PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL);
        ''')
        event_cols={r[1] for r in db.execute('PRAGMA table_info(events)')}
        if 'location' not in event_cols:db.execute("ALTER TABLE events ADD COLUMN location TEXT NOT NULL DEFAULT ''")
        if 'hide_in_month' not in event_cols:db.execute('ALTER TABLE events ADD COLUMN hide_in_month INTEGER NOT NULL DEFAULT 0')
        cols = {r[1] for r in db.execute('PRAGMA table_info(student_profiles)')}
        for name, declaration in [('admission_year','INTEGER'), ('academic_offset','INTEGER NOT NULL DEFAULT 0')]:
            if name not in cols: db.execute(f'ALTER TABLE student_profiles ADD COLUMN {name} {declaration}')
        db.execute('CREATE TABLE IF NOT EXISTS student_timetable_events(user_id INTEGER NOT NULL,term TEXT NOT NULL,occurrence TEXT NOT NULL,event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,PRIMARY KEY(user_id,term,occurrence))')
        db.commit()


def profile(user_id):
    with connection() as db:
        row = db.execute('SELECT * FROM student_profiles WHERE user_id=?', (user_id,)).fetchone()
    return dict(row) if row else {'is_student':False,'school':'','department':'','configured':False}


def save_profile(user_id, data):
    from .campuses import register
    with connection() as db:
        register(db,user_id,data.school,data.department)
        db.execute('INSERT INTO student_profiles(user_id,is_student,school,department,admission_year,academic_offset) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET is_student=excluded.is_student,school=excluded.school,department=excluded.department,admission_year=excluded.admission_year,academic_offset=excluded.academic_offset',
                   (user_id,int(data.is_student),data.school,data.department,data.admission_year,data.academic_offset))
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
        if previous:
            ids=json.loads(previous['event_ids'])
            db.executemany('UPDATE events SET hide_in_month=1 WHERE id=? AND user_id=?',[(i,user_id) for i in ids]);db.commit()
            return {'created':0,'alreadyImported':True,'eventIds':ids}
        ids=[]
        for event in plan['events']:
            existing = db.execute("SELECT id FROM events WHERE user_id=? AND title=? AND start_time=? AND end_time=? AND location=? AND category_name='수업'", (user_id,event['title'],event['startTime'],event['endTime'],event['location'])).fetchone()
            if existing:
                db.execute('UPDATE events SET hide_in_month=1 WHERE id=?',(existing['id'],))
                continue
            row = db.execute('''INSERT INTO events(user_id,title,start_time,end_time,status,type,category_name,location,group_name,hide_in_month)
                              VALUES(?,?,?,?,?,?,?,?,?,1)''',(user_id,event['title'],event['startTime'],event['endTime'],'passive','personal','수업',event['location'],data.name))
            ids.append(row.lastrowid)
        db.execute('INSERT INTO student_timetable_imports VALUES(?,?,?)',(user_id,fingerprint,json.dumps(ids)))
        db.commit()
    return {'created':len(ids),'alreadyImported':False,'eventIds':ids}

init()

class MajorSelection(BaseModel):
    rule_id: str = Field(max_length=120)
    batch: str = Field(max_length=20)
    track: str = Field(max_length=40)

class MajorPlan(BaseModel):
    items: list[MajorSelection] = Field(default_factory=list, max_length=8)
    revision: int = Field(default=0, ge=0)

def major_plan(user_id):
    with connection() as db:
        row = db.execute('SELECT data,revision FROM student_major_plans WHERE user_id=?',(user_id,)).fetchone()
    return {'items': json.loads(row['data']) if row else [], 'revision': row['revision'] if row else 0}

def save_major_plan(user_id, data):
    from .snu_catalog import curricula, curriculum
    seen = set()
    for item in data.items:
        key = (item.rule_id,item.batch,item.track)
        rule = curriculum(item.rule_id)
        if key in seen or not any(e['id']==item.rule_id and e['batch']==item.batch for e in curricula()['index']) or not any(t['key']==item.track for t in rule['tracks']):
            raise HTTPException(400,'학과·학번·전공 유형을 확인해주세요. 중복 전공은 추가할 수 없습니다.')
        seen.add(key)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision FROM student_major_plans WHERE user_id=?',(user_id,)).fetchone()
        revision = row['revision'] if row else 0
        if revision != data.revision:
            raise HTTPException(409,'다른 화면에서 전공 목록이 변경되었습니다. 새로고침 후 다시 시도해주세요.')
        items = [i.model_dump() for i in data.items]
        db.execute('INSERT INTO student_major_plans VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data,revision=excluded.revision',(user_id,json.dumps(items),revision+1))
        db.commit()
    return {'items':items,'revision':revision+1}

class TimetableDraft(BaseModel):
    course_ids: list[int] = Field(default_factory=list, max_length=60)
    manual_lessons: list[Lesson] = Field(default_factory=list, max_length=60)
    starts_on: date
    ends_on: date
    skip_holidays: bool = True
    excluded_dates: list[date] = Field(default_factory=list, max_length=200)
    revision: int = Field(default=0, ge=0)
    sync_calendar: bool = False

    @model_validator(mode='after')
    def validate_dates(self):
        if not 0 <= (self.ends_on-self.starts_on).days <= 200:
            raise ValueError('학기는 1~201일 범위로 입력해주세요.')
        self.course_ids = list(dict.fromkeys(self.course_ids))
        return self

with connection() as db:
    db.execute('CREATE TABLE IF NOT EXISTS student_completed_courses(user_id INTEGER NOT NULL, code TEXT NOT NULL, PRIMARY KEY(user_id,code))')
    db.execute('CREATE TABLE IF NOT EXISTS student_timetable_drafts(user_id INTEGER NOT NULL, term TEXT NOT NULL, data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(user_id,term))')
    db.commit()

def draft_key(term, slot):
    if slot and not re.fullmatch(r'(?:[1-6]-[12]|explore-[a-zA-Z0-9-]{1,45})',slot):
        raise HTTPException(400,'학년·학기는 1-1부터 6-2까지 지정해주세요.')
    return term + ('::'+slot if slot else '')

def draft(user_id, term, slot=''):
    from .campuses import courses
    catalog = {c['id']:c for c in courses(user_id,term)}
    with connection() as db:
        row = db.execute('SELECT data,revision FROM student_timetable_drafts WHERE user_id=? AND term=?', (user_id,draft_key(term,slot))).fetchone()
    data = json.loads(row['data']) if row else None
    if data: data['revision'] = row['revision']
    with connection() as db:
        alternatives=[{'slot':r['term'].split('::',1)[1],'courses':len(json.loads(r['data']).get('course_ids',[]))} for r in db.execute('SELECT term,data FROM student_timetable_drafts WHERE user_id=? AND term LIKE ?', (user_id,term+'::explore-legacy-%'))]
    return {'alternatives':alternatives,'draft': data, 'courses': [catalog[i] for i in data['course_ids'] if i in catalog] if data else []}

def save_draft(user_id, term, data, slot=''):
    storage_key=draft_key(term,slot)
    should_sync = data.sync_calendar and not slot
    if should_sync and not profile(user_id)['is_student']:
        raise HTTPException(400,'학생 서비스를 먼저 설정해주세요.')
    from .campuses import courses
    catalog = {c['id']:c for c in courses(user_id,term)}
    valid_ids = set(catalog)
    if any(i not in valid_ids for i in data.course_ids):
        raise HTTPException(400, '선택한 강의가 이 학기의 강의 목록에 없습니다.')
    # File imports use the same conflict rules as interactive course selection.
    intervals = [(l.weekday,l.start.strftime('%H:%M'),l.end.strftime('%H:%M'),f'manual-{i}') for i,l in enumerate(data.manual_lessons)]
    for course_id in data.course_ids:
        for slot in catalog[course_id].get('slots', []):
            if slot.get('day_index') is not None and slot.get('start_time') and slot.get('end_time'):
                intervals.append((slot['day_index'],slot['start_time'],slot['end_time'],course_id))
    for i, (day,start,end,key) in enumerate(intervals):
        if any(key != other_key and day == other_day and start < other_end and other_start < end for other_day,other_start,other_end,other_key in intervals[i+1:]):
            raise HTTPException(400, '시간이 겹치는 수업이 있습니다. 수업 시간을 확인해주세요.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision FROM student_timetable_drafts WHERE user_id=? AND term=?',(user_id,storage_key)).fetchone()
        revision = row['revision'] if row else 0
        if data.revision != revision:
            raise HTTPException(409, '다른 창에서 시간표가 변경되었습니다. 새로고침 후 다시 확인해주세요.')
        db.execute('INSERT INTO student_timetable_drafts VALUES(?,?,?,?) ON CONFLICT(user_id,term) DO UPDATE SET data=excluded.data,revision=excluded.revision',
                   (user_id,storage_key,data.model_dump_json(),revision+1))
        if should_sync:
            reconcile_timetable(db,user_id,term,data,catalog)
        db.commit()
    return {'revision': revision+1, 'calendarSynced': should_sync}


class CourseCompletion(BaseModel):
    completed: bool

def course_history(user_id):
    from .snu_catalog import supplements, metadata as snu_metadata
    from .campuses import courses as campus_courses, metadata as campus_metadata, is_snu
    today=datetime.now(ZoneInfo('Asia/Seoul')).date()
    terms={t['id']:t for t in (snu_metadata() if is_snu(user_id) else campus_metadata(user_id))['terms']}
    canon=supplements().get('code_equiv',{}).get('canon',{}) if is_snu(user_id) else {}
    with connection() as db:
        excluded={r[0] for r in db.execute('SELECT code FROM student_course_exclusions WHERE user_id=?',(user_id,))}
        drafts=db.execute('SELECT term,data FROM student_timetable_drafts WHERE user_id=? ORDER BY term',(user_id,)).fetchall()
    history=[];completed={};planned={}
    for row in drafts:
        if '::' in row['term']:continue
        info=terms.get(row['term'])
        if not info:continue
        data=json.loads(row['data']);ids=set(data.get('course_ids',[]))
        rows=[c for c in campus_courses(user_id,row['term']) if c['id'] in ids]
        end=data.get('ends_on')
        finished=bool(end and date.fromisoformat(end)<today)
        for c in rows:
            code=c.get('sbjt_cd','').strip().upper()
            if code and canon.get(code,code) not in excluded:(completed if finished else planned)[canon.get(code,code)]=c
        history.append({'term':row['term'],'label':info['label'],'ends_on':end,'finished':finished,'courses':rows})
    return {'semesters':history,'completed':list(completed.values()),'planned':list(planned.values()),'excluded':sorted(excluded | {c['sbjt_cd'] for h in history for c in h['courses'] if canon.get(c['sbjt_cd'],c['sbjt_cd']) in excluded})}

def course_progress(user_id):
    history=course_history(user_id)
    return {'completed':sorted({c['sbjt_cd'].strip().upper() for c in history['completed']}),
            'planned':sorted({c['sbjt_cd'].strip().upper() for c in history['planned']}),
            'basis':'past_timetables'}

def set_course_completion(user_id,code,data):
    code=code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,49}',code):
        raise HTTPException(400,'과목코드를 확인해주세요.')
    with connection() as db:
        if data.completed:
            db.execute('INSERT OR IGNORE INTO student_completed_courses VALUES(?,?)',(user_id,code))
        else: db.execute('DELETE FROM student_completed_courses WHERE user_id=? AND code=?',(user_id,code))
        db.commit()
    return course_progress(user_id)


def reconcile_timetable(db, user_id, term, data, catalog):
    """Only mutate owned occurrences, in the draft's transaction; never match personal titles."""
    expected = {}
    lessons = []
    for course_id in data.course_ids:
        course = catalog[course_id]
        for index, slot in enumerate(course.get('slots', [])):
            if slot.get('day_index') is not None and slot.get('start_time') and slot.get('end_time'):
                lessons.append((f'course:{course_id}:{index}', Lesson(title=course['name'], weekday=slot['day_index'], start=slot['start_time'], end=slot['end_time'], location=course.get('room') or '')))
    for index, lesson in enumerate(data.manual_lessons):
        lessons.append((f'manual:{index}', lesson))
    for source, lesson in lessons:
        for event in preview(Timetable(name=term, starts_on=data.starts_on,ends_on=data.ends_on,skip_holidays=data.skip_holidays,excluded_dates=data.excluded_dates,lessons=[lesson]))['events']:
            expected[source+':'+event['startTime'][:10]] = event
    owned = {r['occurrence']: r['event_id'] for r in db.execute('SELECT occurrence,event_id FROM student_timetable_events WHERE user_id=? AND term=?',(user_id,term))}
    # Old imports have explicit ownership records. Claim only recorded, exact matching events.
    legacy_ids = {i for r in db.execute('SELECT event_ids FROM student_timetable_imports WHERE user_id=?',(user_id,)) for i in json.loads(r['event_ids'])}
    for key, event in expected.items():
        values = (event['title'],event['startTime'],event['endTime'],event['location'],term)
        event_id = owned.get(key)
        if not event_id:
            matches = db.execute("SELECT id FROM events WHERE user_id=? AND title=? AND start_time=? AND end_time=? AND location=?",(user_id,*values[:4])).fetchall()
            event_id = next((r['id'] for r in matches if r['id'] in legacy_ids and not db.execute('SELECT 1 FROM student_timetable_events WHERE event_id=?',(r['id'],)).fetchone()),None)
        if event_id:
            db.execute('UPDATE events SET title=?,start_time=?,end_time=?,location=?,group_name=?,hide_in_month=1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',(*values,event_id,user_id))
        else:
            event_id = db.execute("INSERT INTO events(title,start_time,end_time,location,group_name,user_id,status,type,category_name,hide_in_month) VALUES(?,?,?,?,?,?,'passive','personal','수업',1)",(*values,user_id)).lastrowid
        db.execute('INSERT OR REPLACE INTO student_timetable_events VALUES(?,?,?,?)',(user_id,term,key,event_id))
    for key,event_id in owned.items():
        if key not in expected:
            db.execute('DELETE FROM events WHERE id=? AND user_id=?',(event_id,user_id))


def migrate_legacy_drafts():
    """Preserve every conflicting old plan; merge only identical alternatives."""
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS student_draft_migration_backup(user_id INTEGER,term TEXT,data TEXT,revision INTEGER,PRIMARY KEY(user_id,term))')
        rows=db.execute('SELECT * FROM student_timetable_drafts').fetchall()
        grouped={}
        for row in rows:
            if '::' in row['term'] and re.fullmatch(r'[1-6]-[12]',row['term'].split('::')[1]):
                grouped.setdefault((row['user_id'],row['term'].split('::')[0]),[]).append(row)
        def signature(raw):
            data=json.loads(raw);data.pop('revision',None);data.pop('sync_calendar',None);data['course_ids']=sorted(data.get('course_ids',[]));return json.dumps(data,sort_keys=True)
        for (uid,term),old in grouped.items():
            actual=db.execute('SELECT * FROM student_timetable_drafts WHERE user_id=? AND term=?',(uid,term)).fetchone()
            distinct={signature(r['data']):r for r in old}
            if not actual and len(distinct)==1:
                chosen=next(iter(distinct.values()));db.execute('INSERT INTO student_timetable_drafts VALUES(?,?,?,?)',(uid,term,chosen['data'],chosen['revision']))
                actual=chosen
            seen={signature(actual['data'])} if actual else set()
            for row in old:
                db.execute('INSERT OR IGNORE INTO student_draft_migration_backup VALUES(?,?,?,?)',(uid,row['term'],row['data'],row['revision']))
                sig=signature(row['data'])
                if sig not in seen:
                    target=term+'::explore-legacy-'+row['term'].split('::')[1]
                    db.execute('INSERT OR IGNORE INTO student_timetable_drafts VALUES(?,?,?,?)',(uid,target,row['data'],row['revision']));seen.add(sig)
                db.execute('DELETE FROM student_timetable_drafts WHERE user_id=? AND term=?',(uid,row['term']))
        db.commit()
migrate_legacy_drafts()
