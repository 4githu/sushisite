import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db, community_v2 as docs, drive, notebook_storage
from personal_project.router import current_user_id

@pytest.fixture
def account(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'tests-notebook.sqlite')
    monkeypatch.setattr(docs,'ROOT',tmp_path/'resources')
    db.init_db(); docs.init(); drive.init_drive()
    app=FastAPI(); app.include_router(docs.router)
    app.dependency_overrides[current_user_id]=lambda:81234
    return TestClient(app),81234

def test_usage_tracks_private_files_notes_and_history_without_cross_account_or_board_assets(account):
    client,uid=account
    a={'title':'한글 필기','pages':[]}
    assert client.put('/documents/note:test:v2',json={'revision':0,'data':a}).status_code==200
    b={'title':'수정한 필기','pages':[]}
    result=client.put('/documents/note:test:v2',json={'revision':1,'data':b}); assert result.status_code==200
    with db.connection() as conn:
        conn.execute("INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES('private',?,NULL,'a','image/png',10)",(uid,))
        conn.execute("INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES('board',?,1,'b','image/png',500)",(uid,))
        conn.execute("INSERT INTO personal_resources(id,user_id,board_id,name,mime,size) VALUES('other',?,NULL,'c','image/png',900)",(uid+1,))
        conn.execute("INSERT INTO personal_drive_items(id,user_id,bucket,provider,name,mime_type,byte_size,created_at) VALUES('file',?,'archive','local','f','text/plain',100,'2026-11-16')",(uid,));conn.commit()
    status=drive.status(uid)
    size_a=len(json.dumps(a,ensure_ascii=False).encode());size_b=len(json.dumps(b,ensure_ascii=False).encode())
    assert status['usedBytes']==110+size_a+size_b
    assert status['noteCurrentBytes']==size_b and status['noteHistoryBytes']==size_a
    assert client.put('/documents/note:test:v2',json={'revision':2,'data':b}).json()['revision']==2
    assert drive.status(uid)['usedBytes']==status['usedBytes']

def test_over_quota_note_save_does_not_replace_saved_content(account):
    client,uid=account
    original={'pages':[]}
    assert client.put('/documents/note:test:v2',json={'revision':0,'data':original}).status_code==200
    with db.connection() as conn:
        conn.execute('INSERT INTO personal_drive_quotas(user_id,quota_bytes) VALUES(?,200)',(uid,));conn.commit()
    response=client.put('/documents/note:test:v2',json={'revision':1,'data':{'text':'x'*400}})
    assert response.status_code==413
    assert client.get('/documents/note:test:v2').json()=={'data':original,'revision':1}

def test_private_attachments_share_drive_quota_and_failed_upload_is_removed(account):
    client,uid=account
    with db.connection() as conn:
        conn.execute('INSERT INTO personal_drive_quotas(user_id,quota_bytes) VALUES(?,20)',(uid,));conn.commit()
    response=client.post('/resources?name=test.bin',content=b'x'*30,headers={'content-type':'application/octet-stream'})
    assert response.status_code==413
    assert not list(docs.ROOT.iterdir())

def test_index_follows_deletion_and_initialization_does_not_double_count(account):
    client,uid=account
    client.put('/documents/note:test:v2',json={'revision':0,'data':{'title':'a'}})
    before=drive.status(uid)['noteBytes'];docs.init();assert drive.status(uid)['noteBytes']==before
    with db.connection() as conn:
        conn.execute('DELETE FROM personal_documents WHERE user_id=?',(uid,));conn.commit()
    assert drive.status(uid)['noteBytes']==0
