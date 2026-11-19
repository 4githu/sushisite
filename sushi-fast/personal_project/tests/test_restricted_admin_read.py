"""Synthetic HTTP regression for normal board reads vs administrator inspection."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp()) / 'restricted-admin.sqlite'))
os.environ['DISABLE_TREND_REFRESH'] = '1'
os.environ['DISABLE_KAKAO_BRIDGE'] = '1'

from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import workspace_router
from personal_project.db import connection

ADMIN = 9974101
OTHER = 9974102
app = FastAPI()
app.include_router(workspace_router.router)
identity = {'uid': ADMIN}
app.dependency_overrides[workspace_router.current_user_id] = lambda: identity['uid']
client = TestClient(app)
BASE = '/api/personal'


def test_restricted_board_admin_needs_personal_explicit_read(monkeypatch):
    monkeypatch.setenv('COMMUNITY_ADMINS', str(ADMIN))
    identity['uid'] = ADMIN
    created = client.post(BASE + '/boards', json={'name': 'synthetic ACL board'})
    assert created.status_code == 200, created.text
    bid = created.json()['id']
    with connection() as db:
        pid = db.execute(
            'INSERT INTO community_posts(board_id,author_id,title,document,plain) VALUES(?,?,?,?,?)',
            (bid, OTHER, 'synthetic post', '{}', 'synthetic post'),
        ).lastrowid
        db.commit()
    try:
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 200
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 200
        identity['uid'] = OTHER
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 200
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 200
        identity['uid'] = ADMIN
        assert client.put(BASE + f'/admin/boards/{bid}/restriction', json={'restricted': True}).status_code == 200
        # A realm-level grant is not a board-specific read grant.
        assert client.put(BASE + '/boards/permissions', json={
            'user_id': ADMIN, 'scope': 'other', 'action': 'read', 'allowed': True,
        }).status_code == 200
        assert bid not in [b['id'] for b in client.get(BASE + '/boards').json()['boards']]
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 403
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 403
        # Inspection is an independent audited administrator endpoint.
        inspection = client.get(BASE + f'/admin/boards/{bid}/posts')
        assert inspection.status_code == 200 and inspection.json()['posts'][0]['id'] == pid
        assert client.put(BASE + '/boards/permissions', json={
            'user_id': ADMIN, 'scope': f'board:{bid}', 'action': 'read', 'allowed': True,
        }).status_code == 200
        assert bid in [b['id'] for b in client.get(BASE + '/boards').json()['boards']]
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 200
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 200
        identity['uid'] = OTHER
        assert bid not in [b['id'] for b in client.get(BASE + '/boards').json()['boards']]
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 403
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 403
        assert client.get(BASE + f'/admin/boards/{bid}/posts').status_code == 403
        identity['uid'] = ADMIN
        assert client.put(BASE + '/boards/permissions', json={
            'user_id': OTHER, 'scope': f'board:{bid}', 'action': 'read', 'allowed': True,
        }).status_code == 200
        identity['uid'] = OTHER
        assert client.get(BASE + f'/boards/posts/{pid}').status_code == 200
        identity['uid'] = ADMIN
        assert client.put(BASE + '/boards/permissions', json={
            'user_id': ADMIN, 'scope': f'board:{bid}', 'action': 'read', 'allowed': False,
        }).status_code == 200
        assert client.get(BASE + f'/boards/{bid}/posts').status_code == 403
    finally:
        identity['uid'] = ADMIN
        with connection() as db:
            db.execute('DELETE FROM community_posts WHERE id=?', (pid,))
            db.execute('DELETE FROM community_acl WHERE scope=?', (f'board:{bid}',))
            db.execute("DELETE FROM community_acl WHERE user_id=? AND scope='other' AND action='read'", (ADMIN,))
            db.execute('DELETE FROM community_boards WHERE id=?', (bid,))
            db.commit()
