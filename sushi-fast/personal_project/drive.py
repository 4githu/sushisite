"""Private per-account transfer tray and archive, with optional app-owned Google files."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import uuid4
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException

from .db import connection

ROOT = Path(os.getenv('PERSONAL_DRIVE_ROOT', Path(__file__).resolve().parents[1] / 'storage' / 'personal_drive'))
DEFAULT_QUOTA = 500 * 1024 * 1024
MAX_UPLOAD = 500 * 1024 * 1024
MAX_CHUNK = 8 * 1024 * 1024
TRANSFER_DAYS = 15
DRIVE_API = 'https://www.googleapis.com/drive/v3/files'


def init_drive() -> None:
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS personal_drive_quotas (
            user_id INTEGER PRIMARY KEY, quota_bytes INTEGER NOT NULL DEFAULT 524288000
        );
        CREATE TABLE IF NOT EXISTS personal_drive_accounts (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL,
            email TEXT NOT NULL, client_kind TEXT NOT NULL, refresh_token TEXT NOT NULL,
            scopes TEXT NOT NULL, folder_id TEXT, UNIQUE(user_id,subject)
        );
        CREATE TABLE IF NOT EXISTS personal_drive_items (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            bucket TEXT NOT NULL CHECK(bucket IN ('transfer','archive')),
            provider TEXT NOT NULL CHECK(provider IN ('local','google')),
            account_id INTEGER REFERENCES personal_drive_accounts(id),
            remote_id TEXT, name TEXT NOT NULL, mime_type TEXT NOT NULL,
            byte_size INTEGER NOT NULL, created_at TEXT NOT NULL,
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_personal_drive_user
            ON personal_drive_items(user_id,bucket,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_personal_drive_expiry
            ON personal_drive_items(expires_at);
        CREATE TABLE IF NOT EXISTS personal_drive_uploads (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL,
            mime_type TEXT NOT NULL, bucket TEXT NOT NULL, provider TEXT NOT NULL,
            account_id INTEGER, total_bytes INTEGER NOT NULL,
            received_bytes INTEGER NOT NULL DEFAULT 0, expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE INDEX IF NOT EXISTS idx_personal_drive_uploads_user
            ON personal_drive_uploads(user_id,expires_at);
        ''')
        upload_columns={row['name'] for row in db.execute('PRAGMA table_info(personal_drive_uploads)')}
        if 'replace_item_id' not in upload_columns:
            db.execute('ALTER TABLE personal_drive_uploads ADD COLUMN replace_item_id TEXT')
        db.commit()


def now() -> datetime:
    return datetime.now(timezone.utc)


def quota(db: sqlite3.Connection, user_id: int) -> int:
    row = db.execute('SELECT quota_bytes FROM personal_drive_quotas WHERE user_id=?', (user_id,)).fetchone()
    return int(row['quota_bytes']) if row else DEFAULT_QUOTA


def used(db: sqlite3.Connection, user_id: int) -> int:
    from .notebook_storage import private_usage
    files = int(db.execute("""SELECT COALESCE(SUM(byte_size),0) FROM personal_drive_items
        WHERE user_id=? AND provider='local'""", (user_id,)).fetchone()[0])
    notes = private_usage(db,user_id)
    return files + notes['noteBytes'] + notes['attachmentBytes']


def status(user_id: int) -> dict:
    with connection() as db:
        accounts = [dict(row) for row in db.execute(
            'SELECT id,email FROM personal_drive_accounts WHERE user_id=? ORDER BY id DESC', (user_id,))]
        from .notebook_storage import private_usage
        extra=private_usage(db,user_id)
        total=used(db,user_id)
        return {'quotaBytes': quota(db,user_id), 'usedBytes': total, **extra,
                'fileBytes':total-extra['noteBytes']-extra['attachmentBytes'],
                'transferDays': TRANSFER_DAYS, 'googleAccounts': accounts}


def items(user_id: int, bucket: str) -> list[dict]:
    if bucket not in ('transfer','archive'):
        raise HTTPException(400,'보관 위치가 올바르지 않습니다.')
    with connection() as db:
        return [dict(row) for row in db.execute('''
            SELECT i.id,i.bucket,i.provider,i.account_id AS accountId,i.name,
                   i.mime_type AS mimeType,i.byte_size AS byteSize,
                   i.created_at AS createdAt,i.expires_at AS expiresAt,
                   a.email AS googleEmail
              FROM personal_drive_items i
              LEFT JOIN personal_drive_accounts a ON a.id=i.account_id
             WHERE i.user_id=? AND i.bucket=? AND (i.expires_at IS NULL OR i.expires_at>?)
             ORDER BY i.created_at DESC''', (user_id,bucket,now().isoformat()))]


def item_for(user_id: int, item_id: str) -> dict:
    with connection() as db:
        row = db.execute('SELECT * FROM personal_drive_items WHERE user_id=? AND id=?',
                         (user_id,item_id)).fetchone()
    if not row or (row['expires_at'] and row['expires_at'] <= now().isoformat()):
        raise HTTPException(404,'파일을 찾을 수 없습니다.')
    return dict(row)


def local_path(user_id: int, item_id: str) -> Path:
    return ROOT / str(user_id) / item_id


def pending_path(user_id: int, upload_id: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{32}',upload_id):
        raise HTTPException(404,'업로드를 찾을 수 없습니다.')
    return ROOT / '.pending' / str(user_id) / upload_id


def start_upload(user_id: int, name: str, bucket: str, provider: str,
                 account_id: int | None, total_bytes: int, replace_item_id: str | None = None) -> dict:
    if not name or len(name)>200 or name in ('.','..') or '/' in name or '\\' in name or any(ord(c)<32 for c in name):
        raise HTTPException(400,'파일 이름을 확인해주세요.')
    if bucket not in ('transfer','archive') or provider not in ('local','google'):
        raise HTTPException(400,'저장 위치가 올바르지 않습니다.')
    if total_bytes<=0 or total_bytes>MAX_UPLOAD:
        raise HTTPException(413,'파일 하나는 500MB 이하여야 합니다.')
    if provider=='google':
        if account_id is None: raise HTTPException(400,'Google 계정을 선택해주세요.')
        google_account(user_id,account_id)
    elif account_id is not None:
        raise HTTPException(400,'저장 위치가 올바르지 않습니다.')
    replacing = item_for(user_id,replace_item_id) if replace_item_id else None
    if replacing and (replacing['provider']!=provider or replacing['account_id']!=account_id or replacing['bucket']!=bucket):
        raise HTTPException(400,'같은 파일 위치에서만 수정본을 저장할 수 있습니다.')
    if replacing:
        name=replacing['name']
    upload_id=uuid4().hex
    expires=(now()+timedelta(hours=1)).isoformat()
    mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        reserved=db.execute('SELECT COALESCE(SUM(total_bytes),0) FROM personal_drive_uploads WHERE user_id=? AND provider=?',
                            (user_id,provider)).fetchone()[0]
        pending_bytes=db.execute('SELECT COALESCE(SUM(total_bytes-received_bytes),0) FROM personal_drive_uploads').fetchone()[0]
        if shutil.disk_usage(ROOT.parent).free < total_bytes+pending_bytes+2*1024*1024*1024:
            raise HTTPException(507,'서버 저장 공간이 부족합니다. 잠시 후 다시 시도해주세요.')
        replacing_bytes=int(replacing['byte_size']) if replacing and provider=='local' else 0
        if provider=='local' and used(db,user_id)-replacing_bytes+reserved+total_bytes>quota(db,user_id):
            raise HTTPException(413,'맥 저장 공간이 부족합니다. 파일을 지우거나 Google Drive에 저장해주세요.')
        if provider=='google' and reserved+total_bytes>MAX_UPLOAD*2:
            raise HTTPException(429,'진행 중인 업로드를 마친 뒤 다시 시도해주세요.')
        db.execute('''INSERT INTO personal_drive_uploads
            (id,user_id,name,mime_type,bucket,provider,account_id,total_bytes,expires_at,replace_item_id)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (upload_id,user_id,name,mime,bucket,provider,account_id,total_bytes,expires,replace_item_id))
        db.commit()
    target=pending_path(user_id,upload_id)
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.touch(mode=0o600,exist_ok=False)
    except Exception:
        with connection() as db:
            db.execute('DELETE FROM personal_drive_uploads WHERE id=? AND user_id=?',(upload_id,user_id))
            db.commit()
        raise
    return {'id':upload_id,'chunkBytes':MAX_CHUNK,'receivedBytes':0}


def upload_for(user_id: int, upload_id: str, db: sqlite3.Connection) -> sqlite3.Row:
    row=db.execute('SELECT * FROM personal_drive_uploads WHERE id=? AND user_id=?',
                   (upload_id,user_id)).fetchone()
    if not row or row['expires_at']<=now().isoformat():
        raise HTTPException(404,'업로드가 만료되었습니다. 다시 올려주세요.')
    return row


def append_chunk(user_id: int, upload_id: str, offset: int, chunk: bytes) -> dict:
    if not chunk or len(chunk)>MAX_CHUNK:
        raise HTTPException(413,'업로드 조각이 너무 큽니다.')
    path=pending_path(user_id,upload_id)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=upload_for(user_id,upload_id,db)
        if row['status']!='pending': raise HTTPException(409,'업로드 처리가 이미 진행 중입니다.')
        received=row['received_bytes']
        if offset!=received:
            raise HTTPException(409,{'message':'업로드 위치가 달라졌습니다. 다시 시도해주세요.','receivedBytes':received})
        if received+len(chunk)>row['total_bytes']:
            raise HTTPException(413,'파일 크기를 초과했습니다.')
        try:
            with path.open('r+b') as target:
                target.seek(received)
                target.write(chunk)
                target.flush()
            db.execute('UPDATE personal_drive_uploads SET received_bytes=?,expires_at=? WHERE id=?',
                       (received+len(chunk),(now()+timedelta(hours=1)).isoformat(),upload_id))
            db.commit()
        except Exception:
            with path.open('r+b') as target: target.truncate(received)
            raise
    return {'receivedBytes':received+len(chunk)}


def finish_upload(user_id: int, upload_id: str) -> dict:
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=upload_for(user_id,upload_id,db)
        if row['status']!='pending': raise HTTPException(409,'업로드 처리가 이미 진행 중입니다.')
        if row['received_bytes']!=row['total_bytes']:
            raise HTTPException(409,'업로드가 아직 끝나지 않았습니다.')
        data=dict(row)
        db.execute("UPDATE personal_drive_uploads SET status='finishing',expires_at=? WHERE id=?",
                   ((now()+timedelta(hours=2)).isoformat(),upload_id))
        db.commit()
    path=pending_path(user_id,upload_id)
    try:
        if not path.is_file() or path.stat().st_size!=data['total_bytes']:
            raise HTTPException(409,'업로드 파일을 확인할 수 없습니다. 다시 올려주세요.')
        if data.get('replace_item_id'):
            item=replace_upload(user_id,data['replace_item_id'],path,data['name'],data['mime_type'],
                                data['provider'],data['account_id'],data['total_bytes'])
        else:
            item=store(user_id,path,data['name'],data['mime_type'],data['bucket'],
                       data['provider'],data['account_id'],data['total_bytes'])
    except Exception:
        with connection() as db:
            db.execute("UPDATE personal_drive_uploads SET status='pending' WHERE id=? AND user_id=?",
                       (upload_id,user_id))
            db.commit()
        raise
    path.unlink(missing_ok=True)
    with connection() as db:
        db.execute('DELETE FROM personal_drive_uploads WHERE id=? AND user_id=?',(upload_id,user_id))
        db.commit()
    return item


def cancel_upload(user_id: int, upload_id: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM personal_drive_uploads WHERE id=? AND user_id=? AND status='pending'",
                   (upload_id,user_id))
        db.commit()
        still=db.execute('SELECT 1 FROM personal_drive_uploads WHERE id=? AND user_id=?',
                         (upload_id,user_id)).fetchone()
    if not still: pending_path(user_id,upload_id).unlink(missing_ok=True)


def cleanup_pending() -> int:
    with connection() as db:
        rows=[dict(row) for row in db.execute('SELECT id,user_id FROM personal_drive_uploads WHERE expires_at<=?',
                                             (now().isoformat(),))]
    for row in rows:
        with connection() as db:
            removed=db.execute('DELETE FROM personal_drive_uploads WHERE id=? AND user_id=? AND expires_at<=?',
                               (row['id'],row['user_id'],now().isoformat())).rowcount
            db.commit()
        if removed: pending_path(row['user_id'],row['id']).unlink(missing_ok=True)
    return len(rows)


def google_account(user_id: int, account_id: int) -> dict:
    with connection() as db:
        row = db.execute('SELECT * FROM personal_drive_accounts WHERE id=? AND user_id=?',
                         (account_id,user_id)).fetchone()
    if not row:
        raise HTTPException(404,'연결된 Google Drive가 없습니다.')
    return dict(row)


def save_google_account(user_id: int, subject: str, email: str, kind: str, tokens: dict) -> None:
    from auth.google_oauth import cipher
    with connection() as db:
        old = db.execute('SELECT refresh_token FROM personal_drive_accounts WHERE user_id=? AND subject=?',
                         (user_id,subject)).fetchone()
        refresh = cipher().encrypt(tokens['refresh_token'].encode()).decode() if tokens.get('refresh_token') else old['refresh_token'] if old else None
        if not refresh:
            raise HTTPException(409,'Google 재연결 권한을 받지 못했습니다.')
        db.execute('''INSERT INTO personal_drive_accounts(user_id,subject,email,client_kind,refresh_token,scopes)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,subject) DO UPDATE SET
            email=excluded.email,client_kind=excluded.client_kind,refresh_token=excluded.refresh_token,
            scopes=excluded.scopes''', (user_id,subject,email,kind,refresh,tokens.get('scope','')))
        db.commit()


def google_headers(account: dict) -> dict:
    from auth.google_oauth import access_token
    return {'Authorization':'Bearer '+access_token(account)}


def google_checked(response: httpx.Response) -> dict:
    if response.status_code == 401 or response.status_code == 403:
        raise HTTPException(409,'Google Drive 권한을 확인해주세요. 다시 연결해야 할 수 있습니다.')
    if response.status_code >= 400:
        raise HTTPException(502,'Google Drive 요청에 실패했습니다. 잠시 후 다시 시도해주세요.')
    return response.json() if response.content else {}


def google_folder(account: dict) -> str:
    if account['folder_id']:
        return account['folder_id']
    with httpx.Client(timeout=30) as client:
        response = client.post(DRIVE_API, headers=google_headers(account),
            params={'fields':'id'}, json={'name':'NETAQ Drive','mimeType':'application/vnd.google-apps.folder'})
    folder_id = google_checked(response)['id']
    with connection() as db:
        db.execute('UPDATE personal_drive_accounts SET folder_id=? WHERE id=? AND folder_id IS NULL',
                   (folder_id,account['id']))
        db.commit()
        actual = db.execute('SELECT folder_id FROM personal_drive_accounts WHERE id=?',(account['id'],)).fetchone()[0]
    return actual


def google_upload(account: dict, path: Path, name: str, mime: str) -> str:
    folder_id = google_folder(account)
    size=path.stat().st_size
    with httpx.Client(timeout=600) as client:
        start=client.post('https://www.googleapis.com/upload/drive/v3/files',
            params={'uploadType':'resumable','fields':'id'},
            headers={**google_headers(account),'X-Upload-Content-Type':mime,
                     'X-Upload-Content-Length':str(size)},
            json={'name':name,'parents':[folder_id]})
        google_checked(start)
        location=start.headers.get('Location','')
        parsed=urlsplit(location)
        if parsed.scheme!='https' or parsed.hostname!='www.googleapis.com':
            raise HTTPException(502,'Google Drive 업로드 주소가 올바르지 않습니다.')
        with path.open('rb') as source:
            response=client.put(location,headers={'Content-Type':mime,'Content-Length':str(size)},content=source)
    return google_checked(response)['id']


def google_delete(account: dict, remote_id: str) -> None:
    with httpx.Client(timeout=30) as client:
        response = client.delete(DRIVE_API+'/'+quote(remote_id,safe=''),headers=google_headers(account))
    if response.status_code != 404:
        google_checked(response)


def google_read(account: dict, remote_id: str, max_bytes: int | None = None) -> bytes:
    with httpx.Client(timeout=90) as client:
        with client.stream('GET',DRIVE_API+'/'+quote(remote_id,safe=''),
                           params={'alt':'media'},headers=google_headers(account)) as response:
            if response.status_code >= 400:
                raise HTTPException(502,'Google Drive 파일을 읽을 수 없습니다.')
            chunks=[]; size=0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if max_bytes is not None and size > max_bytes:
                    raise HTTPException(413,'미리보기 용량을 초과했습니다. 다운로드해서 확인해주세요.')
                chunks.append(chunk)
            return b''.join(chunks)


def store(user_id: int, source: Path, name: str, mime: str, bucket: str,
          provider: str, account_id: int | None, byte_size: int) -> dict:
    if bucket not in ('transfer','archive') or provider not in ('local','google'):
        raise HTTPException(400,'저장 위치가 올바르지 않습니다.')
    item_id=uuid4().hex
    created=now()
    expires=(created+timedelta(days=TRANSFER_DAYS)).isoformat() if bucket=='transfer' else None
    remote_id=None
    destination=None
    if provider=='google':
        if account_id is None: raise HTTPException(400,'Google 계정을 선택해주세요.')
        account=google_account(user_id,account_id)
        remote_id=google_upload(account,source,name,mime)
    else:
        if account_id is not None: raise HTTPException(400,'저장 위치가 올바르지 않습니다.')
        destination=local_path(user_id,item_id)
        destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if provider=='local' and used(db,user_id)+byte_size>quota(db,user_id):
                raise HTTPException(413,'500MB 기본 용량을 초과했습니다. 파일을 지우거나 Google Drive에 저장해주세요.')
            if destination:
                os.replace(source,destination)
            db.execute('''INSERT INTO personal_drive_items
                (id,user_id,bucket,provider,account_id,remote_id,name,mime_type,byte_size,created_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (item_id,user_id,bucket,provider,account_id,remote_id,name,mime,byte_size,created.isoformat(),expires))
            db.commit()
    except Exception:
        if destination: destination.unlink(missing_ok=True)
        if remote_id:
            try: google_delete(account,remote_id)
            except Exception: pass
        raise
    return {'id':item_id,'bucket':bucket,'provider':provider,'name':name,
            'mimeType':mime,'byteSize':byte_size,'createdAt':created.isoformat(),'expiresAt':expires}


def replace_upload(user_id: int, item_id: str, source: Path, name: str, mime: str,
                   provider: str, account_id: int | None, byte_size: int) -> dict:
    item=item_for(user_id,item_id)
    if item['provider']!=provider or item['account_id']!=account_id:
        raise HTTPException(400,'같은 파일 위치에서만 수정본을 저장할 수 있습니다.')
    old_remote=item['remote_id']
    new_remote=None
    account=None
    if provider=='google':
        account=google_account(user_id,account_id)
        new_remote=google_upload(account,source,name,mime)
    try:
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM personal_drive_items WHERE id=? AND user_id=?',(item_id,user_id)).fetchone()
            if not current:
                raise HTTPException(404,'파일을 찾을 수 없습니다.')
            if provider=='local' and used(db,user_id)-int(current['byte_size'])+byte_size>quota(db,user_id):
                raise HTTPException(413,'수정본이 500MB 기본 용량을 초과합니다.')
            if provider=='local':
                target=local_path(user_id,item_id)
                if not target.is_file():
                    raise HTTPException(404,'파일 데이터를 찾을 수 없습니다.')
                os.replace(source,target)
            db.execute('''UPDATE personal_drive_items SET remote_id=?,name=?,mime_type=?,byte_size=?
                          WHERE id=? AND user_id=?''',
                       (new_remote if provider=='google' else None,name,mime,byte_size,item_id,user_id))
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='personal_documents'").fetchone():
                document_key='pdf:drive-'+item_id
                db.execute('DELETE FROM personal_document_history WHERE user_id=? AND document_key=?',(user_id,document_key))
                db.execute('DELETE FROM personal_documents WHERE user_id=? AND document_key=?',(user_id,document_key))
            db.commit()
    except Exception:
        if new_remote and account:
            try: google_delete(account,new_remote)
            except Exception: pass
        raise
    if old_remote and account:
        try: google_delete(account,old_remote)
        except Exception: pass
    return {'id':item_id,'bucket':item['bucket'],'provider':provider,'name':name,
            'mimeType':mime,'byteSize':byte_size,'createdAt':item['created_at'],'expiresAt':item['expires_at']}


def update_text(user_id: int, item_id: str, text: str) -> dict:
    item=item_for(user_id,item_id)
    suffix=Path(item['name']).suffix.lower()
    if suffix not in ('.txt','.md','.markdown','.csv','.json','.log'):
        raise HTTPException(415,'이 파일은 바로 편집할 수 없습니다.')
    payload=text.encode('utf-8')
    if len(payload)>1024*1024:
        raise HTTPException(413,'텍스트 파일은 1MB 이하로 저장해주세요.')
    ROOT.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=ROOT,delete=False) as file:
        file.write(payload)
        source=Path(file.name)
    try:
        replace_upload(user_id,item_id,source,item['name'],item['mime_type'],item['provider'],item['account_id'],len(payload))
    finally:
        source.unlink(missing_ok=True)
    return {'saved':True,'byteSize':len(payload)}


def move(user_id: int, item_id: str, bucket: str) -> None:
    if bucket not in ('transfer','archive'):
        raise HTTPException(400,'보관 위치가 올바르지 않습니다.')
    item_for(user_id,item_id)
    expires=(now()+timedelta(days=TRANSFER_DAYS)).isoformat() if bucket=='transfer' else None
    with connection() as db:
        db.execute('UPDATE personal_drive_items SET bucket=?,expires_at=? WHERE id=? AND user_id=?',
                   (bucket,expires,item_id,user_id))
        db.commit()


def delete(user_id: int, item_id: str) -> None:
    item=item_for(user_id,item_id)
    if item['provider']=='google':
        google_delete(google_account(user_id,item['account_id']),item['remote_id'])
    else:
        local_path(user_id,item_id).unlink(missing_ok=True)
    with connection() as db:
        db.execute('DELETE FROM personal_drive_items WHERE id=? AND user_id=?',(item_id,user_id))
        db.commit()


def cleanup_expired() -> int:
    with connection() as db:
        rows=[dict(row) for row in db.execute('SELECT * FROM personal_drive_items WHERE expires_at<=?',
                                             (now().isoformat(),))]
    removed=0
    for item in rows:
        try:
            if item['provider']=='google':
                google_delete(google_account(item['user_id'],item['account_id']),item['remote_id'])
            else:
                local_path(item['user_id'],item['id']).unlink(missing_ok=True)
            with connection() as db:
                db.execute('DELETE FROM personal_drive_items WHERE id=? AND expires_at<=?',
                           (item['id'],now().isoformat()))
                db.commit()
            removed+=1
        except Exception:
            # Keep the row for the next pass so remote data is never silently orphaned.
            continue
    return removed


def content(item: dict, max_bytes: int | None = None) -> bytes:
    if max_bytes is not None and item['byte_size']>max_bytes:
        raise HTTPException(413,'미리보기 용량을 초과했습니다. 다운로드해서 확인해주세요.')
    if item['provider']=='google':
        return google_read(google_account(item['user_id'],item['account_id']),item['remote_id'],max_bytes)
    path=local_path(item['user_id'],item['id'])
    if not path.is_file(): raise HTTPException(404,'파일 데이터를 찾을 수 없습니다.')
    return path.read_bytes()


def word_preview(item: dict) -> str:
    if not item['name'].lower().endswith('.docx'):
        raise HTTPException(415,'DOCX 문서만 미리볼 수 있습니다.')
    import io
    payload=content(item,20*1024*1024)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as document:
            info=document.getinfo('word/document.xml')
            if info.file_size>8*1024*1024:
                raise HTTPException(413,'문서가 너무 커서 미리보기를 만들 수 없습니다.')
            root=ET.fromstring(document.read(info))
    except (zipfile.BadZipFile,KeyError,ET.ParseError):
        raise HTTPException(422,'Word 문서를 읽을 수 없습니다.')
    namespace='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paragraphs=[]
    for paragraph in root.iter(namespace+'p'):
        text=''.join(node.text or '' for node in paragraph.iter(namespace+'t'))
        if text.strip(): paragraphs.append(text)
    return '\n\n'.join(paragraphs)[:200000]


init_drive()
