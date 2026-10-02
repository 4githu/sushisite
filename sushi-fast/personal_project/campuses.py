"""User-contributed school directory; links never trigger server-side fetches."""
import hashlib
from datetime import date
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from .db import connection
from .router import current_user_id
from .community_v2 import write_origin
from .campus_directory import ALIASES, SCHOOLS, departments, capabilities
from . import campus_catalog

router=APIRouter(prefix='/student',dependencies=[Depends(write_origin)])
def normalize(name):
    name=' '.join(name.split())
    return ALIASES.get(name.casefold(),name)
def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS campuses(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,creator_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS campus_departments(school_id INTEGER NOT NULL, name TEXT NOT NULL,creator_id INTEGER,PRIMARY KEY(school_id,name));
        CREATE TABLE IF NOT EXISTS campus_links(id INTEGER PRIMARY KEY,school_id INTEGER NOT NULL,user_id INTEGER NOT NULL,label TEXT NOT NULL,url TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        for name in SCHOOLS:
            db.execute('INSERT OR IGNORE INTO campuses(name) VALUES(?)',(name,))
        for row in db.execute("SELECT user_id,school,department FROM student_profiles WHERE school<>''").fetchall():
            register(db,row['user_id'],row['school'],row['department'])
        db.commit()
def register(db,uid,school,department=''):
    school=normalize(school)
    if not school:return
    if db.execute('SELECT count(*) FROM campuses WHERE creator_id=?',(uid,)).fetchone()[0]>=20 and not db.execute('SELECT 1 FROM campuses WHERE name=?',(school,)).fetchone():raise HTTPException(429,'새 학교 등록 한도에 도달했습니다.')
    if department.strip() and db.execute('SELECT count(*) FROM campus_departments WHERE creator_id=?',(uid,)).fetchone()[0]>=100 and not db.execute('SELECT 1 FROM campus_departments d JOIN campuses c ON c.id=d.school_id WHERE c.name=? AND d.name=?',(school,department.strip())).fetchone():raise HTTPException(429,'학과 등록 한도에 도달했습니다.')
    db.execute('INSERT OR IGNORE INTO campuses(name,creator_id) VALUES(?,?)',(school,uid))
    sid=db.execute('SELECT id FROM campuses WHERE name=?',(school,)).fetchone()[0]
    if department.strip():db.execute('INSERT OR IGNORE INTO campus_departments VALUES(?,?,?)',(sid,department.strip(),uid))
    return sid
init()

def school(uid):
    from .student_services import profile
    return normalize(profile(uid)['school'])
def is_snu(uid):return school(uid) in ('','서울대학교')
def metadata(uid):
    from .student_services import profile
    p=profile(uid); name=school(uid)
    key=hashlib.sha256(name.encode()).hexdigest()[:12]
    start=p.get('admission_year') or date.today().year-3
    terms=[]
    for year in range(max(2000,start),min(2100,max(date.today().year+2,start+6))+1):
        for code,label in [('U000200001U000300001','1학기'),('U000200001U000300002','여름 계절'),('U000200002U000300001','2학기'),('U000200002U000300002','겨울 계절')]:
            terms.append({'id':f'campus-{key}-{year}_{code}','year':str(year),'term':code,'label':f'{year} {label}','count':0})
    meta=campus_catalog.index(name)
    if meta:
        merged={t['id']:t for t in terms}
        merged.update({t['id']:t for t in meta['terms']})
        return meta | {'terms':sorted(merged.values(),key=lambda t:t['id'])}
    return {'revision':f'campus-{key}-manual-v1','terms':terms,'source':'','sourceUpdatedAt':'','importedAt':'','school':name,'supported':False}
def courses(uid,term):
    if is_snu(uid):
        from .snu_catalog import courses as snu_courses
        return snu_courses(term)
    if term not in {t['id'] for t in metadata(uid)['terms']}:raise HTTPException(400,'현재 학교의 학기를 선택해주세요.')
    return campus_catalog.courses(school(uid),term)

@router.get('/schools')
def schools(uid:int=Depends(current_user_id)):
    with connection() as db:
        result=[]
        for r in db.execute('SELECT * FROM campuses ORDER BY id'):
            known=set(departments(r['name']))
            known.update(d[0] for d in db.execute('SELECT name FROM campus_departments WHERE school_id=?',(r['id'],)))
            result.append({'id':r['id'],'name':r['name'],'departments':sorted(known),**capabilities(r['name'])})
        return sorted(result,key=lambda r:(SCHOOLS.index(r['name']) if r['name'] in SCHOOLS else len(SCHOOLS),r['name']))

class SchoolCreate(BaseModel):
    name:str=Field(min_length=1,max_length=120)
@router.post('/schools')
def create_school(data:SchoolCreate,uid:int=Depends(current_user_id)):
    name=normalize(data.name)
    if not name:raise HTTPException(400,'학교 이름을 입력해주세요.')
    with connection() as db:
        if db.execute('SELECT count(*) FROM campuses WHERE creator_id=?',(uid,)).fetchone()[0]>=20 and not db.execute('SELECT 1 FROM campuses WHERE name=?',(name,)).fetchone():raise HTTPException(429,'새 학교 등록 한도에 도달했습니다. 관리자에게 문의해주세요.')
        sid=register(db,uid,name);db.commit()
    return {'id':sid,'name':name}

class ServiceLink(BaseModel):
    label:str=Field(min_length=1,max_length=80)
    url:str=Field(max_length=2000)
    kind:str=Field(pattern='^(portal|timetable|meals|rules|other)$')
    @field_validator('url')
    @classmethod
    def safe_url(cls,value):
        p=urlsplit(value)
        if p.scheme!='https' or not p.hostname or p.username or p.password or any(ord(c)<33 for c in value) or '\\' in value:raise ValueError('HTTPS 서비스 주소를 입력해주세요.')
        return value
@router.get('/school-services')
def services(uid:int=Depends(current_user_id)):
    name=school(uid)
    with connection() as db:
        row=db.execute('SELECT id FROM campuses WHERE name=?',(name,)).fetchone()
        links=[dict(r)|{'canDelete':r['user_id']==uid} for r in db.execute('SELECT * FROM campus_links WHERE school_id=? ORDER BY id',(row[0],))] if row else []
    return {'school':name,**capabilities(name),'links':links}
@router.post('/school-services')
def add_service(data:ServiceLink,uid:int=Depends(current_user_id)):
    name=school(uid)
    if not name:raise HTTPException(400,'학교를 먼저 저장해주세요.')
    with connection() as db:
        sid=register(db,uid,name)
        if db.execute('SELECT count(*) FROM campus_links WHERE school_id=? AND user_id=?',(sid,uid)).fetchone()[0]>=20:raise HTTPException(429,'학교별 링크는 20개까지 등록할 수 있습니다.')
        db.execute('INSERT INTO campus_links(school_id,user_id,label,url,kind) VALUES(?,?,?,?,?)',(sid,uid,data.label.strip(),data.url,data.kind));db.commit()
    return services(uid)
@router.delete('/school-services/{lid}')
def remove_service(lid:int,uid:int=Depends(current_user_id)):
    with connection() as db:
        if not db.execute('DELETE FROM campus_links WHERE id=? AND user_id=?',(lid,uid)).rowcount:raise HTTPException(403,'등록한 사람만 링크를 삭제할 수 있습니다.')
        db.commit()
    return services(uid)
