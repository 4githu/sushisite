"""Account storage accounting for revisioned notebook data, without scanning ink on each save."""
from fastapi import HTTPException


def is_notebook_key(key: str) -> bool:
    return key.startswith(('note:', 'pdf:')) or key == 'notes:library:v1'


def init_sizes(db):
    fresh = not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='personal_notebook_sizes'").fetchone()
    db.execute('''CREATE TABLE IF NOT EXISTS personal_notebook_sizes(
        user_id INTEGER NOT NULL, document_key TEXT NOT NULL, revision INTEGER NOT NULL,
        byte_size INTEGER NOT NULL, PRIMARY KEY(user_id,document_key,revision))''')
    for table, marker in [('personal_documents', '-1'), ('personal_document_history', 'NEW.revision')]:
        suffix = 'current' if table == 'personal_documents' else 'history'
        for action in ('INSERT', 'UPDATE'):
            db.executescript(f'''CREATE TRIGGER IF NOT EXISTS notebook_size_{suffix}_{action.lower()}
                AFTER {action} ON {table}
                WHEN NEW.document_key LIKE 'note:%' OR NEW.document_key LIKE 'pdf:%' OR NEW.document_key='notes:library:v1'
                BEGIN
                    INSERT INTO personal_notebook_sizes(user_id,document_key,revision,byte_size)
                    VALUES(NEW.user_id,NEW.document_key,{marker},length(CAST(NEW.data AS BLOB)))
                    ON CONFLICT(user_id,document_key,revision) DO UPDATE SET byte_size=excluded.byte_size;
                END;''')
        old_marker = '-1' if table == 'personal_documents' else 'OLD.revision'
        db.executescript(f'''CREATE TRIGGER IF NOT EXISTS notebook_size_{suffix}_delete
            AFTER DELETE ON {table} BEGIN
                DELETE FROM personal_notebook_sizes WHERE user_id=OLD.user_id AND document_key=OLD.document_key AND revision={old_marker};
            END;''')
    if fresh:
        for table, marker in [('personal_documents', '-1'), ('personal_document_history', 'revision')]:
            db.execute(f'''INSERT OR REPLACE INTO personal_notebook_sizes(user_id,document_key,revision,byte_size)
                SELECT user_id,document_key,{marker},length(CAST(data AS BLOB)) FROM {table}
                WHERE document_key LIKE 'note:%' OR document_key LIKE 'pdf:%' OR document_key='notes:library:v1' ''')


def private_usage(db, user_id: int) -> dict:
    def exists(table):
        return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    current = history = attachments = 0
    if exists('personal_notebook_sizes'):
        row = db.execute('''SELECT COALESCE(SUM(CASE WHEN revision=-1 THEN byte_size ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN revision<>-1 THEN byte_size ELSE 0 END),0)
            FROM personal_notebook_sizes WHERE user_id=?''', (user_id,)).fetchone()
        current, history = map(int, row)
    if exists('personal_resources'):
        attachments = int(db.execute('SELECT COALESCE(SUM(size),0) FROM personal_resources WHERE user_id=? AND board_id IS NULL', (user_id,)).fetchone()[0])
    return {'noteCurrentBytes': current, 'noteHistoryBytes': history,
            'noteBytes': current + history, 'attachmentBytes': attachments}


def check_document_capacity(db, user_id: int, key: str, encoded: str, old):
    if not is_notebook_key(key):
        return
    from .drive import used, quota
    old_size = len(old['data'].encode('utf-8')) if old else 0
    history_size = 0
    if old and not db.execute('SELECT 1 FROM personal_document_history WHERE user_id=? AND document_key=? AND revision=?', (user_id, key, old['revision'])).fetchone():
        history_size = old_size
    before = used(db, user_id)
    projected = before - old_size + len(encoded.encode('utf-8')) + history_size
    if projected > quota(db, user_id) and projected > before:
        raise HTTPException(413, '개인 저장 공간이 부족합니다. 드라이브에서 노트·첨부파일 용량을 확인해주세요.')
