from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from auth import JMT, router as routes, userdb
import sqlite3
import time

def test_login_duration_renewal_and_expired_rejection(monkeypatch, tmp_path):
    monkeypatch.setattr(JMT,'SECRET_KEY','unit-test-secret-not-production')
    monkeypatch.setattr(JMT,'ALGORITHM','HS256')
    monkeypatch.setattr(userdb, 'DB_PATH', tmp_path / 'synthetic-users.db')
    with sqlite3.connect(userdb.DB_PATH) as db:
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT, email_verified INTEGER)')
        db.execute('INSERT INTO users VALUES (1, ?, ?, 0)', ('test@example.invalid', 'test'))
    # A login service result must carry the authoritative verification state.
    monkeypatch.setattr(routes.service,'login_with_password',lambda *args:(True,userdb.get_user(user_id=1)))
    app=FastAPI();app.include_router(routes.router)
    client=TestClient(app,base_url='https://example.com')
    response=client.post('/auth/login',json={'email':'test@example.invalid','password':'test'})
    assert response.status_code == 200 and response.json()['success'] is True
    assert 'Max-Age=2592000' in response.headers['set-cookie']
    token = client.cookies.get('mainauth')
    assert token is not None
    assert JMT.SECRET_KEY is not None
    assert jwt.decode(token, JMT.SECRET_KEY, algorithms=[JMT.ALGORITHM])['data']['email_verified'] is False
    payload=client.get('/auth/isjwt?key=mainauth').json()
    assert payload['data']['email_verified'] is False
    assert payload['exp'] > time.time()+29*86400
    old=JMT.make_jwt(1,{'id':1},['id'],lifetime_seconds=3600)
    response=client.get('/auth/isjwt?key=mainauth',headers={'cookie':f'mainauth={old}'})
    assert response.status_code==200 and 'Max-Age=2592000' in response.headers['set-cookie']
    assert response.json()['data']['email_verified'] is False
    expired=JMT.make_jwt(1,{'id':1},['id'],lifetime_seconds=-10)
    response=client.get('/auth/isjwt?key=mainauth',headers={'cookie':f'mainauth={expired}'})
    assert response.status_code==401
    assert 'set-cookie' not in response.headers
