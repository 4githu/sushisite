import os,tempfile,time
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'api.sqlite'))
os.environ['DISABLE_TREND_REFRESH']='1'
os.environ['DISABLE_KAKAO_BRIDGE']='1'
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace_router as r
from personal_project.db import connection
app=FastAPI();app.include_router(r.router)
UID=99571
app.dependency_overrides[r.current_user_id]=lambda:UID
client=TestClient(app)
BASE='/api/personal/board-api'
def token(scopes):
    res=client.post(BASE+'/tokens',json={'name':'test','board_ids':[1],'scopes':scopes})
    assert res.status_code==200,res.text
    assert res.headers['cache-control']=='no-store'
    return res.json()
def test_scope_idempotency_revoke_and_live_acl():
    key=token(['read','post','comment']);headers={'Authorization':'Bearer '+key['token'],'Idempotency-Key':'board-api-test-001'}
    payload={'title':'API test','document':{'blocks':[{'children':[{'text':'hello'}]}]}}
    a=client.post(BASE+'/boards/1/posts',headers=headers,json=payload);assert a.status_code==200,a.text
    b=client.post(BASE+'/boards/1/posts',headers=headers,json=payload);assert a.json()==b.json()
    assert client.post(BASE+'/boards/1/posts',headers=headers,json={**payload,'title':'different'}).status_code==409
    assert client.get(BASE+'/boards/999/posts',headers=headers).status_code==403
    pid=a.json()['id'];comment=client.post(BASE+f'/posts/{pid}/comments',headers=headers,json={'content':'reply'})
    assert comment.status_code==200,comment.text
    assert client.post(BASE+f'/posts/{pid}/comments',headers=headers,json={'content':'reply'}).json()==comment.json()
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO community_acl(user_id,scope,action,allowed) VALUES(?,'board:1','read',0)",(UID,));db.commit()
    assert client.get(BASE+f'/posts/{pid}',headers=headers).status_code==403
    with connection() as db:db.execute('DELETE FROM community_acl WHERE user_id=?',(UID,));db.commit()
    client.delete(BASE+'/tokens/'+key['id'])
    assert client.get(BASE+'/boards/1/posts',headers=headers).status_code==401

def test_origin_expiry_and_no_cookie_fallback():
    assert client.post(BASE+'/tokens',headers={'Origin':'https://evil.example'},json={'name':'bad','board_ids':[1]}).status_code==403
    assert client.get(BASE+'/boards/1/posts').status_code==401
    key=token(['read']);headers={'Authorization':'Bearer '+key['token']}
    assert client.post(BASE+'/boards/1/posts',headers=headers,json={'title':'no'}).status_code==403
    with connection() as db:db.execute('UPDATE board_api_tokens SET expires_at=0 WHERE id=?',(key['id'],));db.commit()
    assert client.get(BASE+'/boards/1/posts',headers=headers).status_code==401

def test_upload_download_and_private_file_boundary():
    key=token(['read','upload']);headers={'Authorization':'Bearer '+key['token'],'Content-Type':'text/plain'}
    result=client.post(BASE+'/boards/1/resources?name=api.txt',headers=headers,content=b'board attachment')
    assert result.status_code==200,result.text
    rid=result.json()['id']
    assert client.get(BASE+'/resources/'+rid,headers=headers).content==b'board attachment'
    private=client.post('/api/personal/resources?name=private.txt',content=b'private',headers={'Content-Type':'text/plain'})
    assert private.status_code==200,private.text
    assert client.get(BASE+'/resources/'+private.json()['id'],headers=headers).status_code==403

def test_rate_limit_and_hashed_storage():
    import hashlib
    key=token(['read']);headers={'Authorization':'Bearer '+key['token']}
    with connection() as db:
        row=db.execute('SELECT digest FROM board_api_tokens WHERE id=?',(key['id'],)).fetchone()
        assert row[0]==hashlib.sha256(key['token'].encode()).hexdigest()
        db.execute('INSERT INTO board_api_limits VALUES(?,?,120)',(key['id'],int(time.time())//60));db.commit()
    result=client.get(BASE+'/boards/1/posts',headers=headers)
    assert result.status_code==429 and result.headers['Retry-After']=='60'
