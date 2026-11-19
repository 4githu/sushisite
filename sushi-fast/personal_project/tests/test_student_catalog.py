import os
import tempfile
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='student-tests-'))/'calendar.db'))
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from personal_project import snu_catalog as catalog, student_services as student, student_meals as meals
from personal_project.db import connection

TERM='2026_U000200002U000300001'

def test_real_course_search_and_filters():
    result=catalog.search(TERM,'자료구조 강유')
    assert result['total']==1
    c=result['courses'][0]
    assert c['sbjt_cd']=='M1522.000900'
    assert [(s['day_index'],s['start_time'],s['end_time']) for s in c['slots']]==[(0,'09:30','10:45'),(2,'09:30','10:45')]
    assert catalog.search(TERM,department='컴퓨터공학부',classification='전필',day=0)['total']>0
    assert catalog.search(TERM,'definitely no matching class')['total']==0
    with pytest.raises(HTTPException):catalog.courses('../index')
    assert len(catalog.courses(TERM))==8652

def test_all_snapshot_files_and_curriculum_sources():
    for term in catalog.metadata()['terms']: assert len(catalog.courses(term['id']))==term['count']
    rule=catalog.curriculum('cse_2026')
    double=next(t for t in rule['tracks'] if t['key']=='double')
    assert double['major_min_credits']==39
    assert any(c['name']=='자료구조' for c in double['required']['all'])
    assert rule['source'] and len(catalog.curricula()['rules'])==200

def test_private_draft_revision_and_invalid_course():
    c=catalog.search(TERM,'자료구조 강유')['courses'][0]
    d=student.TimetableDraft(course_ids=[c['id']],starts_on='2026-09-01',ends_on='2026-12-20')
    with connection() as db:db.execute('DELETE FROM student_timetable_drafts WHERE user_id IN (7801,7802)');db.commit()
    assert student.save_draft(7801,TERM,d)['revision']==1
    assert student.draft(7802,TERM)['draft'] is None
    assert student.draft(7801,TERM)['courses'][0]['name']=='자료구조'
    with pytest.raises(HTTPException) as error:student.save_draft(7801,TERM,d)
    assert error.value.status_code==409
    with pytest.raises(HTTPException):student.save_draft(7802,TERM,d.model_copy(update={'course_ids':[-1]}))

def test_growing_timetable_import_does_not_duplicate_existing_classes():
    with connection() as db:
        db.execute('DELETE FROM events WHERE user_id=7803');db.execute('DELETE FROM student_timetable_imports WHERE user_id=7803');db.commit()
    student.save_profile(7803,student.Profile(is_student=True,school='서울대학교'))
    lesson={'title':'자료구조','weekday':0,'start':'09:30','end':'10:45','location':'301-118'}
    base={'name':'2026 2학기','starts_on':'2026-09-07','ends_on':'2026-09-14','lessons':[lesson]}
    assert student.import_timetable(7803,student.Timetable(**base))['created']==2
    base['lessons'].append({**lesson,'title':'논리설계','weekday':1})
    assert student.import_timetable(7803,student.Timetable(**base))['created']==1
    assert student.import_timetable(7803,student.Timetable(**base))['alreadyImported']
    with connection() as db:assert db.execute('SELECT count(*) FROM events WHERE user_id=7803').fetchone()[0]==3

def test_meal_parser_real_official_html():
    parser=meals.MenuParser();parser.feed((Path(__file__).parent/'fixtures/snu-menu-2026-09-27.html').read_text())
    assert parser.page_date=='2026-09-27'
    assert parser.rows[0]['title']=='기숙사식당 (881-9072)'
    assert parser.rows[0]['lunch']=='추석연휴 휴무'
    assert all('<br' not in r.get('lunch','') for r in parser.rows)

def test_meals_cache_failure_and_changed_source(monkeypatch):
    import httpx
    from datetime import date
    day=date(2026,9,27);calls=[];meals._cache.clear()
    def fetch(*a,**kw):
        calls.append(kw);return httpx.Response(200,text=(Path(__file__).parent/'fixtures/snu-menu-2026-09-27.html').read_text(),request=httpx.Request('GET',meals.URL))
    monkeypatch.setattr(meals.httpx,'get',fetch)
    assert not meals.menus(day)['stale'];assert not meals.menus(day)['stale'];assert len(calls)==1
    _,data=meals._cache[str(day)];meals._cache[str(day)]=(-10000,data)
    def fail(*a,**kw):raise httpx.ConnectError('offline')
    monkeypatch.setattr(meals.httpx,'get',fail)
    assert meals.menus(day)['stale']
    with pytest.raises(HTTPException) as err:meals.menus(date(2026,9,28))
    assert err.value.status_code==503

def test_widget_week_navigation_uses_requested_seoul_date():
    from personal_project import workspace_router as r, workspace as w
    from personal_project.schemas import EventCreate
    app=FastAPI();app.include_router(r.router);app.dependency_overrides[r.current_user_id]=lambda:7804;c=TestClient(app)
    with connection() as db:db.execute('DELETE FROM events WHERE user_id=7804');db.commit()
    for day in ('2026-09-21','2026-09-28'):w.create_event(7804,EventCreate(title=day,start_time=day+'T09:00:00+09:00',end_time=day+'T10:00:00+09:00'))
    code=c.post('/api/personal/calendar/widget/pair').json()['code'];token=c.post('/api/personal/calendar/widget/claim',json={'token':code}).json()['token']
    headers={'Authorization':'Bearer '+token}
    assert [e['title'] for e in c.get('/api/personal/calendar/widget/feed?view=week&anchor=2026-09-21',headers=headers).json()['events']]==['2026-09-21']
    assert [e['title'] for e in c.get('/api/personal/calendar/widget/feed?view=week&anchor=2026-09-28',headers=headers).json()['events']]==['2026-09-28']

def test_imported_draft_rejects_time_conflicts_without_overwriting():
    course=catalog.search(TERM,'자료구조 강유')['courses'][0]
    with connection() as db:db.execute('DELETE FROM student_timetable_drafts WHERE user_id=7805');db.commit()
    conflicting=student.TimetableDraft(course_ids=[course['id']],manual_lessons=[{'title':'겹침','weekday':0,'start':'10:00','end':'11:00'}],starts_on='2026-09-01',ends_on='2026-12-20')
    with pytest.raises(HTTPException) as error:student.save_draft(7805,TERM,conflicting)
    assert error.value.status_code==400
    assert student.draft(7805,TERM)['draft'] is None

def test_major_comparison_is_private_validated_and_revision_guarded():
    with connection() as db:db.execute('DELETE FROM student_major_plans WHERE user_id IN (7901,7902)');db.commit()
    items=[dict(rule_id='cse_2026',batch='2026',track=t) for t in ('multi','double')]
    result=student.save_major_plan(7901,student.MajorPlan(items=items))
    assert result['revision']==1 and result['items']==items
    assert student.major_plan(7902)=={'items':[],'revision':0}
    with pytest.raises(HTTPException) as e:student.save_major_plan(7901,student.MajorPlan(items=[]))
    assert e.value.status_code==409
    with pytest.raises(HTTPException):student.save_major_plan(7901,student.MajorPlan(items=[{**items[0],'batch':'1900'}],revision=1))
    with pytest.raises(HTTPException):student.save_major_plan(7901,student.MajorPlan(items=[items[0],items[0]],revision=1))
    assert len(student.major_plan(7901)['items'])==2

def test_curriculum_notes_are_readable_without_hiding_uncertainty(monkeypatch):
    raw=catalog.curricula()['rules']['philo_2023_2024']
    rule=catalog.curriculum('philo_2023_2024')
    assert rule['needs_verification']
    assert '임시 기준' in ' '.join(rule['notes'])
    assert 'SPA-blocked' not in ' '.join(rule['notes'])
    assert '필수 과목 목록은 제공되지 않으며' in ' '.join(rule['notes'])
    assert 'SPA-blocked' in ' '.join(raw['notes'])
    monkeypatch.setattr(catalog,'curricula',lambda:{'rules':{'sample':{'notes':['교양&#x20;3학점 &amp; 선택'],'tracks':[]}}})
    assert catalog.curriculum('sample')['notes']==['교양 3학점 & 선택']

def test_imported_classes_hidden_in_month_but_visible_in_week():
    from personal_project import workspace as w
    from personal_project.workspace_router import router
    import hashlib
    app=FastAPI();app.include_router(router);c=TestClient(app)
    student.save_profile(7903,student.Profile(is_student=True,school='서울대학교'))
    data=student.Timetable(name='테스트 학기',starts_on='2026-09-07',ends_on='2026-09-07',lessons=[{'title':'주간 전용 수업','weekday':0,'start':'09:00','end':'10:00'}])
    student.import_timetable(7903,data)
    assert all(e['hideInMonth'] for e in w.list_events(7903))
    token='test-week-month-7903'
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO widget_devices VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),7903,'2026-09-01','test'));db.commit()
    headers={'Authorization':'Bearer '+token}
    assert c.get('/api/personal/calendar/widget/feed?view=month&anchor=2026-09-07',headers=headers).json()['events']==[]
    assert len(c.get('/api/personal/calendar/widget/feed?view=week&anchor=2026-09-07',headers=headers).json()['events'])==1

def test_academic_semesters_and_course_completion_are_separate_and_private():
    users=(7951,7952)
    with connection() as db:
        for user in users:
            db.execute('DELETE FROM student_timetable_drafts WHERE user_id=?',(user,))
            db.execute('DELETE FROM student_completed_courses WHERE user_id=?',(user,))
        db.commit()
    c=catalog.search(TERM,'자료구조 강유')['courses'][0]
    d=student.TimetableDraft(course_ids=[c['id']],starts_on='2026-09-01',ends_on='2026-12-31')
    student.save_draft(7951,TERM,d,'1-1')
    assert student.draft(7951,TERM,'1-1')['courses'][0]['id']==c['id']
    assert student.draft(7951,TERM,'1-2')['draft'] is None
    assert student.draft(7951,TERM)['draft'] is None
    assert student.draft(7952,TERM,'1-1')['draft'] is None
    assert student.course_progress(7951)['planned']==[]  # legacy alternate is not a canonical semester
    assert student.course_progress(7951)['completed']==[]
    student.set_course_completion(7951,c['sbjt_cd'],student.CourseCompletion(completed=True))
    assert student.course_progress(7951)['completed']==[]  # manual checkbox no longer determines transcript
    assert student.course_progress(7952)=={'planned':[],'completed':[],'basis':'past_timetables'}
    student.set_course_completion(7951,c['sbjt_cd'].lower(),student.CourseCompletion(completed=False))
    assert student.course_progress(7951)['completed']==[]
    with pytest.raises(HTTPException): student.save_draft(7951,TERM,d,'1-1')
    with pytest.raises(HTTPException): student.draft(7951,TERM,'../')
    with pytest.raises(HTTPException): student.set_course_completion(7951,'<script>',student.CourseCompletion(completed=True))

def test_curriculum_display_removes_transport_diagnostics_and_keeps_codes():
    import json
    from personal_project.curriculum_display import text
    rule=catalog.curriculum('smsys_2026')
    rendered=json.dumps(rule,ensure_ascii=False)
    assert 'HTTP 200' not in rendered and '-k는' not in rendered and '인증서 무효' not in rendered
    assert rule['needs_verification'] and '임시' in rendered
    assert rule['source_links']
    math=catalog.curriculum('math_2026')
    assert math['general']=='자연과학대학 교양 기준(2025년)'
    assert math['major_required_known'][0]['code']=='M1407.000600'
    assert text('math / science / general')=='수학 / 과학 / 교양'
