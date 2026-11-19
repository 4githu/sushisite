import os,tempfile,json
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH',str(Path(tempfile.mkdtemp())/'oauth.sqlite'))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'
from urllib.parse import urlsplit,parse_qs
from fastapi import FastAPI
from fastapi.testclient import TestClient
from auth import google_oauth as g
from personal_project.db import connection

def test_handoff_nonce_purpose_one_use_and_host_only_cookie(monkeypatch):
    monkeypatch.setenv('GOOGLE_TOKEN_ENCRYPTION_KEY','unit-test-only')
    monkeypatch.setattr(g.JMT,'SECRET_KEY','test-secret')
    monkeypatch.setattr(g.JMT,'ALGORITHM','HS256')
    monkeypatch.setattr(g,'credentials',lambda kind:('test-client','test-secret'))
    app=FastAPI();app.include_router(g.router)
    client=TestClient(app,base_url='https://netaq.chobab.app',follow_redirects=False)
    assert client.get('/auth/google/start?return_to=//evil.test').status_code==400
    begin=client.get('/auth/google/start');assert begin.status_code==307
    parent=begin.headers['location'];ident=parse_qs(urlsplit(parent).query)['handoff'][0]
    stranger=TestClient(app,base_url='https://chobab.app',follow_redirects=False)
    assert stranger.get(parent).status_code==400
    assert client.get(parent.replace('purpose=login','purpose=calendar')).status_code==400
    google=client.get(parent);assert google.status_code==307
    assert parse_qs(urlsplit(google.headers['location']).query)['redirect_uri']==['https://chobab.app/auth/google/callback']
    token=g.JMT.make_jwt(99661,{'id':99661},['id'])
    with connection() as db:
        db.execute('UPDATE google_netaq_handoffs SET token=?,result=? WHERE id=?',(g.cipher().encrypt(token.encode()).decode(),json.dumps({'google':'signed_in'}),ident));db.commit()
    url='/auth/google/netaq-finish?id='+ident
    assert stranger.get('https://netaq.chobab.app'+url).status_code==400
    done=client.get(url);assert done.status_code==303
    cookie=next(c for c in done.headers.get_list('set-cookie') if c.startswith('mainauth='))
    assert 'Domain=' not in cookie and 'HttpOnly' in cookie and 'Secure' in cookie
    assert token not in done.headers['location']
    assert client.get(url).status_code==400

def test_google_error_never_issues_session(monkeypatch):
    monkeypatch.setenv('GOOGLE_TOKEN_ENCRYPTION_KEY','unit-test-only')
    app=FastAPI();app.include_router(g.router)
    c=TestClient(app,base_url='https://netaq.chobab.app',follow_redirects=False)
    begin=c.get('/auth/google/start');ident=parse_qs(urlsplit(begin.headers['location']).query)['handoff'][0]
    with connection() as db:db.execute('UPDATE google_netaq_handoffs SET result=? WHERE id=?',(json.dumps({'google_error':'cancelled'}),ident));db.commit()
    done=c.get('/auth/google/netaq-finish?id='+ident)
    assert done.status_code==303 and 'google_error=cancelled' in done.headers['location']
    assert not any(h.startswith('mainauth=') for h in done.headers.get_list('set-cookie'))
