import base64
from datetime import datetime
from zoneinfo import ZoneInfo
import fitz
from personal_project import community_v2 as c, course_tags as tags, widget_plan
from personal_project.db import connection
from personal_project.tests.test_workspace_upgrade import client,BASE

def test_tags_are_additive_and_school_scoped():
 uid=99301
 with connection() as db:
  db.execute("INSERT OR REPLACE INTO student_profiles(user_id,is_student,school,department) VALUES(?,1,'서울대학교','수학과')",(uid,));db.commit()
 payload=tags.Tags(tags=[tags.Tag(kind='major_select',major='수학과'),tags.Tag(kind='major_required',major='물리학과'),tags.Tag(kind='general',area='수학')])
 tags.put_tags('M123',payload,uid)
 assert len(tags.get_tags(uid)['M123'])==3
 with connection() as db:db.execute("UPDATE student_profiles SET school='KAIST' WHERE user_id=?",(uid,));db.commit()
 assert tags.get_tags(uid)=={}

def test_day_preview_private_ink_and_place():
 stamp=datetime(2026,10,8,tzinfo=ZoneInfo('Asia/Seoul'))
 events=[{'title':'Study','location':'Room 301','startTime':'2026-10-08T09:00:00+09:00','endTime':'2026-10-08T10:00:00+09:00'}]
 empty=widget_plan.render(99302,stamp,events)
 import json
 with connection() as db:
  db.execute('INSERT OR REPLACE INTO personal_documents(user_id,document_key,revision,data) VALUES(?,?,1,?)',(99302,'pdf:day-ink:2026-10-08',json.dumps({'pages':[{'strokes':[{'color':'#ff0000','width':4,'kind':'pen','points':[{'x':100,'y':400},{'x':300,'y':400}]}]}]})));db.commit()
 own=widget_plan.render(99302,stamp,events)
 assert own!=empty and widget_plan.render(99303,stamp,events)==empty
 pix=fitz.Pixmap(base64.b64decode(own));assert (pix.width,pix.height)==(420,760)

def test_admin_inspection_does_not_grant_normal_access(monkeypatch):
 from personal_project.tests import test_workspace_upgrade as fixture
 uid=fixture.user
 monkeypatch.setenv('COMMUNITY_ADMINS',str(uid))
 bid=client.post(BASE+'/boards',json={'name':'inspect only'}).json()['id']
 pid=client.post(BASE+f'/boards/{bid}/posts',json={'title':'test','document':{'blocks':[]}}).json()['id']
 client.put(BASE+f'/admin/boards/{bid}/restriction',json={'restricted':True})
 assert client.get(BASE+f'/boards/{bid}/posts').status_code==403
 assert client.get(BASE+f'/admin/boards/{bid}/posts').json()['posts'][0]['id']==pid
 monkeypatch.setenv('COMMUNITY_ADMINS','')
 assert client.get(BASE+f'/admin/boards/{bid}/posts').status_code==403


def test_pytest_import_refuses_default_production_database():
 import subprocess,sys,os
 env=dict(os.environ);env.pop('PERSONAL_PROJECT_DB_PATH',None)
 result=subprocess.run([sys.executable,'-c','import pytest; import personal_project.db'],env=env,capture_output=True,text=True)
 assert result.returncode!=0 and 'explicit isolated' in result.stderr
