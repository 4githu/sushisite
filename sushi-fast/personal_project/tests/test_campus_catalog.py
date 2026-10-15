"""Public catalog normalization and school-scoped draft/calendar integration."""
import importlib.util
import os
import tempfile
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'campus.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'
import pytest
from fastapi import HTTPException
from personal_project import workspace_router, campuses, campus_directory, campus_catalog, student_services as student
from personal_project.db import connection

spec=importlib.util.spec_from_file_location('hanyang_import',Path(__file__).resolve().parents[3]/'ops/import_hanyang_catalog.py')
importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)

def test_cross_listing_is_one_stable_course():
    a=dict(suupYear='2026',suupTerm='20',campusNm='서울',campusCd='H',suupNo='1',bunbanNo='00',
        banSosokNm='컴퓨터소프트웨어학부',isuGbNm='전공핵심',gwamokNm='자료구조',haksuNo='CSE101',hakjeom=3,
        suupTimes='월(09:00-10:30) 수(09:00-10:30)',suupRoomNms='공학관')
    rows=importer.normalize([a,a|{'banSosokNm':'전기공학전공'}],2026,'20')
    assert len(rows)==1 and len(rows[0]['departments'])==2 and len(rows[0]['slots'])==2
    assert importer.normalize([a],2026,'20')[0]['id']==rows[0]['id']<2**53
    assert importer.normalize([a|{'campusCd':'Y','campusNm':'ERICA'}],2026,'20')[0]['id']!=rows[0]['id']
    with pytest.raises(ValueError):importer.normalize([a,a|{'hakjeom':2}],2026,'20')
    with pytest.raises(ValueError):importer.normalize([a],2025,'20')

def test_directory_and_actual_capabilities():
    available={s['name']:s for s in campuses.schools(99681)}
    assert set(campus_directory.SCHOOLS)<=set(available)
    assert available['한양대학교']['catalog'] and not available['한양대학교']['meals']
    assert available['KAIST']['catalog'] is False
    assert '전산학부' in available['KAIST']['departments']
    assert '컴퓨터학과' in available['고려대학교']['departments']
    assert student.Profile(school='유니스트',department='컴퓨터 공학과').department=='컴퓨터공학과'

def test_hanyang_search_save_sync_and_school_isolation():
    uid=99682
    student.save_profile(uid,student.Profile(is_student=True,school='한양대',admission_year=2026))
    meta=campuses.metadata(uid)
    term=campus_catalog.term_id('한양대학교',2026,'20')
    courses=campuses.courses(uid,term)
    course=next(c for c in courses if c['slots'] and len(c['slots'])==2)
    assert meta['supported'] and len(courses)>1000
    hits=campus_catalog.search('한양대학교',term,course['sbjt_cd'],department=course['departments'][0])
    assert course['id'] in [c['id'] for c in hits['courses']]
    draft=student.TimetableDraft(course_ids=[course['id']],starts_on='2026-09-01',ends_on='2026-12-31',revision=0,sync_calendar=True)
    student.save_draft(uid,term,draft)
    with connection() as db:n=db.execute('SELECT count(*) FROM student_timetable_events WHERE user_id=? AND term=?',(uid,term)).fetchone()[0]
    assert n>20
    student.save_draft(uid,term,draft.model_copy(update={'revision':1}))
    with connection() as db:assert db.execute('SELECT count(*) FROM student_timetable_events WHERE user_id=? AND term=?',(uid,term)).fetchone()[0]==n
    assert student.course_history(uid)['semesters'][0]['courses'][0]['id']==course['id']
    student.save_profile(uid,student.Profile(is_student=True,school='KAIST'))
    with pytest.raises(HTTPException):campuses.courses(uid,term)
    assert student.course_history(uid)['semesters']==[]
