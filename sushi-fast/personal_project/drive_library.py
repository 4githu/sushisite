"""Folder organization and revocable, expiring file links. File bytes stay in drive.py."""
import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException
from .db import connection
from . import drive


def init():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS drive_folders(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,parent_id TEXT,bucket TEXT NOT NULL,name TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS drive_folders_owner ON drive_folders(user_id,bucket,parent_id);
        CREATE TABLE IF NOT EXISTS drive_file_folders(item_id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,folder_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drive_share_links(token_hash TEXT PRIMARY KEY,item_id TEXT NOT NULL,user_id INTEGER NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS drive_links_owner ON drive_share_links(user_id,item_id);
        ''')
        db.commit()


def folder(db, uid, fid, bucket=None):
    if not fid:
        return None
    row = db.execute('SELECT * FROM drive_folders WHERE id=? AND user_id=?', (fid,uid)).fetchone()
    if not row or (bucket and row['bucket'] != bucket):
        raise HTTPException(404,'폴더를 찾을 수 없습니다.')
    return dict(row)


def library(uid, bucket, fid=None):
    if bucket not in ('archive','transfer'):
        raise HTTPException(422,'보관 위치를 확인해주세요.')
    with connection() as db:
        folder(db,uid,fid,bucket)
        trail=[]; cursor=fid
        while cursor:
            entry=folder(db,uid,cursor,bucket)
            trail.insert(0,entry);cursor=entry['parent_id']
            if len(trail)>32:raise HTTPException(409,'폴더 구조를 확인해주세요.')
        folders=[dict(r) for r in db.execute('SELECT * FROM drive_folders WHERE user_id=? AND bucket=? AND parent_id IS ? ORDER BY name',(uid,bucket,fid))]
        # Ignore placements in another tray after the existing transfer/archive action.
        placements={r['item_id']:r['folder_id'] for r in db.execute('SELECT p.* FROM drive_file_folders p JOIN drive_folders f ON f.id=p.folder_id WHERE p.user_id=? AND f.bucket=?',(uid,bucket))}
        shared=[r['item_id'] for r in db.execute('SELECT DISTINCT item_id FROM drive_share_links WHERE user_id=? AND expires_at>?',(uid,drive.now().isoformat()))]
        all_folders=[dict(r) for r in db.execute('SELECT * FROM drive_folders WHERE user_id=? AND bucket=? ORDER BY name',(uid,bucket))]
    return {'folders':folders,'allFolders':all_folders,'trail':trail,'placements':placements,'shared':shared}


def create_folder(uid,name,bucket,parent=None):
    name=name.strip()
    if not name or bucket not in ('archive','transfer'):raise HTTPException(422,'폴더 이름과 보관 위치를 확인해주세요.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');folder(db,uid,parent,bucket)
        depth=0;cursor=parent
        while cursor:
            depth+=1;cursor=folder(db,uid,cursor,bucket)['parent_id']
            if depth>=20:raise HTTPException(400,'폴더는 20단계까지 만들 수 있어요.')
        if db.execute('SELECT 1 FROM drive_folders WHERE user_id=? AND bucket=? AND parent_id IS ? AND name=?',(uid,bucket,parent,name)).fetchone():raise HTTPException(409,'같은 이름의 폴더가 있어요.')
        fid=uuid4().hex
        db.execute('INSERT INTO drive_folders VALUES(?,?,?,?,?,?)',(fid,uid,parent,bucket,name,drive.now().isoformat()));db.commit()
    return {'id':fid}


def delete_folder(uid,fid):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');folder(db,uid,fid)
        if db.execute('SELECT 1 FROM drive_folders WHERE user_id=? AND parent_id=?',(uid,fid)).fetchone() or db.execute('SELECT 1 FROM drive_file_folders p JOIN personal_drive_items i ON i.id=p.item_id JOIN drive_folders f ON f.id=p.folder_id WHERE p.user_id=? AND p.folder_id=? AND i.bucket=f.bucket AND (i.expires_at IS NULL OR i.expires_at>?)',(uid,fid,drive.now().isoformat())).fetchone():
            raise HTTPException(409,'파일과 하위 폴더를 먼저 옮겨주세요.')
        db.execute('DELETE FROM drive_file_folders WHERE user_id=? AND folder_id=?',(uid,fid))
        db.execute('DELETE FROM drive_folders WHERE id=? AND user_id=?',(fid,uid));db.commit()


def organize(uid,item_id,name,parent=None):
    item=drive.item_for(uid,item_id);name=name.strip()
    if not name:raise HTTPException(422,'파일 이름을 입력해주세요.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');folder(db,uid,parent,item['bucket'])
        db.execute('UPDATE personal_drive_items SET name=? WHERE id=? AND user_id=?',(name,item_id,uid))
        db.execute('DELETE FROM drive_file_folders WHERE item_id=? AND user_id=?',(item_id,uid))
        if parent:db.execute('INSERT INTO drive_file_folders VALUES(?,?,?)',(item_id,uid,parent))
        db.commit()


def share(uid,item_id,days):
    item=drive.item_for(uid,item_id)
    expires=drive.now()+timedelta(days=days)
    if item['expires_at']:expires=min(expires,datetime.fromisoformat(item['expires_at']))
    token=secrets.token_urlsafe(32)
    with connection() as db:
        db.execute('INSERT INTO drive_share_links VALUES(?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),item_id,uid,expires.isoformat(),drive.now().isoformat()));db.commit()
    return {'token':token,'expiresAt':expires.isoformat()}


def revoke(uid,item_id):
    drive.item_for(uid,item_id)
    with connection() as db:
        db.execute('DELETE FROM drive_share_links WHERE user_id=? AND item_id=?',(uid,item_id));db.commit()


def shared_item(token):
    if len(token)>100:raise HTTPException(404,'공유 링크를 찾을 수 없습니다.')
    with connection() as db:
        link=db.execute('SELECT * FROM drive_share_links WHERE token_hash=? AND expires_at>?',(hashlib.sha256(token.encode()).hexdigest(),drive.now().isoformat())).fetchone()
    if not link:raise HTTPException(404,'만료되었거나 해제된 공유 링크입니다.')
    return drive.item_for(link['user_id'],link['item_id'])


init()
