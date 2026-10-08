"""Browser relay invariants; no real logins or messages."""
import os,tempfile,json
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'relay.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'
import pytest
from fastapi import HTTPException
from personal_project import workspace_router,dshs_sync as relay,community_v2 as community
from personal_project.db import connection
@pytest.fixture
def route(monkeypatch,tmp_path):
 config=tmp_path/'config.json';config.write_text('{}');monkeypatch.setattr(relay,'CONFIG',config)
 monkeypatch.setattr(community,'ROOT',tmp_path/'assets')
 with connection() as db:
  for table in ('dshs_relay_state','dshs_relay_seen','dshs_relay_outbox','kakao_board_routes'):db.execute(f'DELETE FROM {table}')
  db.execute("INSERT OR IGNORE INTO community_boards(id,name) VALUES(4,'Relay')")
  db.execute("UPDATE community_boards SET restricted=1,parent_id=NULL,school='' WHERE id=4")
  db.execute("INSERT OR REPLACE INTO community_acl VALUES(99699,'board:4','read',1)")
  db.execute("INSERT INTO kakao_board_routes(user_id,board_id,room,mention,enabled) VALUES(99699,4,'fixture','fixture',1)");db.commit()
 return 99699
def test_status_requires_admin(monkeypatch):
 monkeypatch.setattr(community,'admin',lambda uid:False)
 with pytest.raises(HTTPException) as e:relay.status(1)
 assert e.value.status_code==403
def test_baseline_import_and_no_echo(route,monkeypatch):
 monkeypatch.setattr(relay,'invoke',lambda job:{'complete':True,'ids':['old'],'posts':[]});relay.tick()
 def newer(job):
  assert not job['baseline'] and job['seen']==['old']
  return {'complete':True,'ids':['old','new'],'posts':[{'id':'new','title':'자료','text':'본문','url':'https://test.dshs.app/board/nSW86Tx/post/new','images':[],'files':[]}]}
 monkeypatch.setattr(relay,'invoke',newer);relay.tick()
 with connection() as db:
  assert db.execute("SELECT COUNT(*) FROM dshs_relay_seen WHERE remote_id='new'").fetchone()[0]==1
  assert db.execute('SELECT COUNT(*) FROM dshs_relay_outbox').fetchone()[0]==0
def test_incomplete_scan_never_advances_baseline(route,monkeypatch):
 monkeypatch.setattr(relay,'invoke',lambda job:{'complete':False,'ids':['partial'],'posts':[]})
 with pytest.raises(RuntimeError):relay.tick()
 with connection() as db:assert db.execute('SELECT COUNT(*) FROM dshs_relay_state').fetchone()[0]==0
def test_uncertain_publish_is_not_retried(route,monkeypatch):
 monkeypatch.setattr(relay,'invoke',lambda job:{'complete':True,'ids':[],'posts':[]});relay.tick()
 with connection() as db:
  pid=db.execute("INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(4,?,'new',?,'body')",(route,json.dumps({'blocks':[]}))).lastrowid;db.commit()
 calls=[]
 def invoke(job):
  if job['command']=='publish':calls.append(job);raise RuntimeError('submission uncertain')
  return {'complete':True,'ids':[],'posts':[]}
 monkeypatch.setattr(relay,'invoke',invoke);relay.tick();relay.tick()
 assert len(calls)==1
 with connection() as db:assert db.execute('SELECT state FROM dshs_relay_outbox WHERE post_id=?',(pid,)).fetchone()[0]=='unknown'

def test_private_destination_is_required(route,monkeypatch):
 with connection() as db:db.execute('UPDATE community_boards SET restricted=0 WHERE id=4');db.commit()
 monkeypatch.setattr(relay,'invoke',lambda job:pytest.fail('must stop before browser login'))
 with pytest.raises(HTTPException) as e:relay.tick()
 assert e.value.status_code==403
