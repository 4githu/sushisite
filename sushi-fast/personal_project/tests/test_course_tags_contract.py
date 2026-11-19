"""Synthetic course-tag import and HTTP contract regressions."""
import os
import subprocess
import sys


def test_import_before_profiles_defers_legacy_school_migration(tmp_path):
    db_path = tmp_path / 'tags.sqlite'
    script = '''
from personal_project import course_tags
from personal_project.db import connection
from fastapi import HTTPException
try:
    course_tags.put_tags('OLD101', course_tags.Tags(tags=[course_tags.Tag(kind='general', area='수학')]), 42)
except HTTPException as exc:
    assert exc.status_code == 400
else:
    raise AssertionError('missing general target must be rejected before profile schema exists')
with connection() as db:
    db.execute("INSERT INTO student_course_tags VALUES(?,?,?)", (42, 'OLD101', '[{"kind":"general","major":"*","area":"수학"}]'))
    db.commit()
from personal_project import student_services
with connection() as db:
    db.execute("INSERT INTO student_profiles(user_id,is_student,school,department) VALUES(42,1,'KAIST','수학과')")
    db.commit()
assert course_tags.get_tags(42)['OLD101'] == [{'kind':'general','major':'*','area':'수학'}]
assert course_tags.get_tags(42)['OLD101'] == [{'kind':'general','major':'*','area':'수학'}]
with connection() as db:
    assert db.execute('SELECT count(*) FROM student_course_tags_v2 WHERE user_id=42').fetchone()[0] == 1
'''
    env = {**os.environ, 'PERSONAL_PROJECT_DB_PATH': str(db_path), 'DISABLE_KAKAO_BRIDGE': '1', 'DISABLE_TREND_REFRESH': '1'}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_legacy_migration_preserves_existing_school_data(tmp_path):
    db_path = tmp_path / 'existing.sqlite'
    script = '''
from personal_project import student_services
from personal_project.db import connection
with connection() as db:
    db.execute("INSERT INTO student_profiles VALUES(42,1,'KAIST','수학과',NULL,0)")
    db.execute('CREATE TABLE student_course_tags(user_id INTEGER,code TEXT,data TEXT NOT NULL,PRIMARY KEY(user_id,code))')
    db.execute('CREATE TABLE student_course_tags_v2(user_id INTEGER,school TEXT,code TEXT,data TEXT NOT NULL,PRIMARY KEY(user_id,school,code))')
    db.execute("INSERT INTO student_course_tags VALUES(42,'OLD101','[]')")
    db.execute("INSERT INTO student_course_tags_v2 VALUES(?,?,?,?)", (42, 'KAIST', 'OLD101', '[{"kind":"general","major":"*","area":"수학"}]'))
    db.commit()
from personal_project import course_tags
expected = [{'kind':'general','major':'*','area':'수학'}]
assert course_tags.get_tags(42)['OLD101'] == expected
assert course_tags.get_tags(42)['OLD101'] == expected
with connection() as db:
    assert db.execute('SELECT count(*) FROM student_course_tags_v2 WHERE user_id=42').fetchone()[0] == 1
'''
    env = {**os.environ, 'PERSONAL_PROJECT_DB_PATH': str(db_path), 'DISABLE_KAKAO_BRIDGE': '1', 'DISABLE_TREND_REFRESH': '1'}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_general_tag_requires_target_and_area_over_http():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project import student_services, course_tags
    from personal_project.db import connection

    app = FastAPI()
    app.include_router(course_tags.router)
    app.dependency_overrides[course_tags.current_user_id] = lambda: 99308
    client = TestClient(app)
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO student_profiles(user_id,is_student,school,department) VALUES(99308,1,'서울대학교','수학과')")
        db.commit()
    path = '/student/course-tags/MATH101'
    missing_major = client.put(path, json={'tags': [{'kind': 'general', 'area': '수학'}]})
    assert missing_major.status_code == 400
    missing_area = client.put(path, json={'tags': [{'kind': 'general', 'major': '*'}]})
    assert missing_area.status_code == 400
    assert client.get('/student/course-tags').json() == {}
    for target in ('*', '수학과'):
        response = client.put(path, json={'tags': [{'kind': 'general', 'major': target, 'area': '수학'}]})
        assert response.status_code == 200, response.text
        assert response.json()['tags'] == [{'kind': 'general', 'major': target, 'area': '수학'}]
        assert client.get('/student/course-tags').json()['MATH101'] == response.json()['tags']
