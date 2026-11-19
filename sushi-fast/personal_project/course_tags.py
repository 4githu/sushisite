"""Personal, additive course classifications; never mutates official curriculum."""
import json,re
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from typing import Literal
from .db import connection
from .router import current_user_id
from .community_v2 import write_origin
router=APIRouter(prefix='/student/course-tags',dependencies=[Depends(write_origin)])
_legacy_migrated = False


def _migrate_legacy(db):
    global _legacy_migrated
    if _legacy_migrated or not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_profiles'").fetchone():
        return
    db.execute("INSERT OR IGNORE INTO student_course_tags_v2 SELECT t.user_id,COALESCE(p.school,'서울대학교'),t.code,t.data FROM student_course_tags t LEFT JOIN student_profiles p ON p.user_id=t.user_id")
    db.commit()
    _legacy_migrated = True


with connection() as db:
    db.execute('CREATE TABLE IF NOT EXISTS student_course_tags(user_id INTEGER,code TEXT,data TEXT NOT NULL,PRIMARY KEY(user_id,code))')
    db.execute('CREATE TABLE IF NOT EXISTS student_course_tags_v2(user_id INTEGER,school TEXT,code TEXT,data TEXT NOT NULL,PRIMARY KEY(user_id,school,code))')
    _migrate_legacy(db)
    db.commit()
class Tag(BaseModel):
    kind:Literal['major_select','major_required','general']
    major:str=Field(default='',max_length=120)
    area:str=Field(default='',max_length=80)
class Tags(BaseModel):
    tags:list[Tag]=Field(default_factory=list,max_length=20)
@router.get('')
def get_tags(uid:int=Depends(current_user_id)):
    with connection() as db:
        _migrate_legacy(db)
        p=db.execute('SELECT school FROM student_profiles WHERE user_id=?',(uid,)).fetchone();school=p['school'] if p else '서울대학교'
        return {r['code']:json.loads(r['data']) for r in db.execute('SELECT code,data FROM student_course_tags_v2 WHERE user_id=? AND school=?',(uid,school))}
@router.put('/{code}')
def put_tags(code:str,data:Tags,uid:int=Depends(current_user_id)):
    code=code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,49}',code):raise HTTPException(400,'과목코드를 확인해주세요.')
    if any(t.kind.startswith('major') and not t.major.strip() for t in data.tags):raise HTTPException(400,'인정할 전공을 입력해주세요.')
    tags=[]
    for t in data.tags:
        tag={'kind':t.kind,'major':t.major.strip(), 'area':t.area.strip() if t.kind=='general' else ''}
        if t.kind=='general' and not tag['area']:raise HTTPException(400,'교양 영역을 선택해주세요.')
        if t.kind=='general' and not tag['major']:raise HTTPException(400,'교양 분류를 적용할 전공을 선택해주세요.')
        if tag not in tags:tags.append(tag)
    with connection() as db:
        _migrate_legacy(db)
        p=db.execute('SELECT school FROM student_profiles WHERE user_id=?',(uid,)).fetchone();school=p['school'] if p else '서울대학교'
        db.execute('INSERT OR REPLACE INTO student_course_tags_v2 VALUES(?,?,?,?)',(uid,school,code,json.dumps(tags,ensure_ascii=False)));db.commit()
    return {'tags':tags}
