"""Owner-scoped, idempotent actions shared by desktop and Android widgets."""
import hashlib
import json
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from .db import connection


def owner(request: Request) -> int:
    token = request.headers.get('authorization', '').removeprefix('Bearer ')
    with connection() as db:
        row = db.execute('SELECT user_id FROM widget_devices WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row:
        raise HTTPException(401, '위젯을 다시 연결해주세요.')
    return row['user_id']


def extras(uid: int, day: str, all_tasks=False) -> dict:
    with connection() as db:
        row = db.execute("SELECT data FROM personal_documents WHERE user_id=? AND document_key='netaq-captures-v1'", (uid,)).fetchone()
        items = json.loads(row['data']).get('items', []) if row else []
        note = db.execute('SELECT day,content FROM calendar_daily_notes WHERE user_id=? AND day<=? ORDER BY day DESC LIMIT 1', (uid, day)).fetchone()
    return {
        'captures': [i for i in items if i.get('kind') == 'task' and not i.get('done') and (all_tasks or i.get('today') == day)][:100],
        'note': note['content'][:2000] if note else '',
        'noteDate': note['day'] if note else None,
        'date': day, 'updatedAt': datetime.now(timezone.utc).isoformat()
    }


def change_capture(uid: int, change):
    from .community_v2 import document, save_document, DocumentWrite
    for attempt in range(3):
        old = document('netaq-captures-v1', uid)
        data = old.get('data') or {'items': []}
        data['items'] = change(data.get('items', []))
        try:
            return save_document('netaq-captures-v1', DocumentWrite(revision=old['revision'], data=data), uid)
        except HTTPException as error:
            if error.status_code != 409 or attempt == 2:
                raise


def complete(uid: int, source: str, item_id: str, done: bool):
    if source == 'event':
        from . import workspace
        from .schemas import EventUpdate
        try:
            event_id = int(item_id)
        except ValueError:
            raise HTTPException(422, '할 일을 찾을 수 없습니다.')
        event = workspace.get_event(uid, event_id)
        if event.get('canEdit') is False or event.get('completionSource') == 'external' or event['status'] not in ('todo', 'done'):
            raise HTTPException(403, '연결된 서비스에서 완료해주세요.')
        workspace.update_event(uid, event_id, EventUpdate(status='done' if done else 'todo'))
    else:
        def update(items):
            if not any(i['id'] == item_id and i.get('kind') == 'task' for i in items):
                raise HTTPException(404, '할 일을 찾을 수 없습니다.')
            return [{**i, 'done': done} if i['id'] == item_id else i for i in items]
        change_capture(uid, update)
    return {'ok': True}


def capture(uid: int, item_id: str, text: str):
    value = text.strip()
    if not value:
        raise HTTPException(422, '내용을 입력해주세요.')
    item = {'id': item_id, 'text': value, 'createdAt': datetime.now(timezone.utc).isoformat(), 'kind': 'inbox', 'today': None, 'done': False}
    change_capture(uid, lambda items: items if any(i['id'] == item_id for i in items) else [*items, item])
    return {'ok': True}


def recent_notes(uid: int) -> list:
    """Most recently saved account notes; never exposes another user's documents."""
    with connection() as db:
        row = db.execute("SELECT data FROM personal_documents WHERE user_id=? AND document_key='notes:library:v1'", (uid,)).fetchone()
        if not row: return []
        try: catalog = json.loads(row['data'])
        except (ValueError, TypeError): return []
        if not isinstance(catalog, dict): return []
        saved = {r['document_key']: r['updated_at'] for r in db.execute(
            "SELECT document_key,updated_at FROM personal_documents WHERE user_id=? AND document_key LIKE 'note:%:v2' AND document_key NOT LIKE '%:p:%'", (uid,))}
    result=[]
    for book in catalog.get('notebooks', []):
        if not isinstance(book, dict): continue
        for section in book.get('sections', []):
            if not isinstance(section, dict): continue
            for note in section.get('notes', []):
                if not isinstance(note, dict) or note.get('deleted'): continue
                nid = note.get('id')
                if not isinstance(nid, str) or not nid or len(nid)>200: continue
                stamp=saved.get('note:'+nid+':v2')
                if not stamp: continue
                result.append({'id':nid,'title':str(note.get('title') or '제목 없는 노트')[:120], 'notebook':str(book.get('title') or '')[:120], 'updatedAt':stamp})
    return sorted(result,key=lambda n:n['updatedAt'],reverse=True)[:10]
