"""Explicit, operator-invoked cleanup of attached images on submitted reports.

Never runs automatically. Preserves ambiguous files and live shared references.
"""
from collections import Counter
from . import attachment_cleanup, repository


def cleanup_submitted(expected_backups=None):
    counts = Counter()
    with repository.connection() as db:
        ids = [r[0] for r in db.execute("""SELECT a.id FROM aura_report_attachments a
            JOIN aura_target_reports rp ON rp.id=a.target_report_id
            WHERE rp.status='submitted' AND a.mime_type LIKE 'image/%' ORDER BY a.id""")]
    counts['examined'] = len(ids)
    for attachment_id in ids:
        with repository.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("""SELECT a.*, r.user_id AS report_owner FROM aura_report_attachments a
                JOIN aura_target_reports rp ON rp.id=a.target_report_id
                JOIN aura_round_targets t ON t.id=rp.target_id
                JOIN aura_clinic_rounds r ON r.id=t.round_id
                WHERE a.id=? AND rp.status='submitted' AND a.mime_type LIKE 'image/%'""", (attachment_id,)).fetchone()
            if row is None:
                counts['changed'] += 1
                db.commit()
                continue
            if row['user_id'] != row['report_owner']:
                counts['owner_mismatch'] += 1
                db.commit()
                continue
            if db.execute('SELECT 1 FROM aura_report_attachments WHERE storage_name=? AND id<>? LIMIT 1', (row['storage_name'], row['id'])).fetchone():
                counts['shared'] += 1
                db.commit()
                continue
            fingerprint = attachment_cleanup.snapshot(repository.ATTACHMENT_ROOT, row['user_id'], row['target_report_id'], row['storage_name'])
            try:
                info = attachment_cleanup._fingerprint(repository.ATTACHMENT_ROOT, row['user_id'], row['target_report_id'], row['storage_name']) if fingerprint else None
            except OSError:
                info = None
            if not info or info != (row['byte_size'], fingerprint):
                counts['unsafe_or_missing'] += 1
                db.commit()
                continue
            if expected_backups is not None and expected_backups.get(row['id']) != (row['user_id'], row['target_report_id'], row['storage_name'], row['byte_size'], fingerprint):
                counts['backup_mismatch'] += 1
                db.commit()
                continue
            journal_id = repository._journal_attachment(db, row, 'attachment')
            stored = db.execute('SELECT file_sha256 FROM aura_attachment_cleanup_journal WHERE id=?', (journal_id,)).fetchone()[0]
            if stored != fingerprint:
                db.rollback()
                counts['changed'] += 1
                continue
            db.execute('DELETE FROM aura_report_attachments WHERE id=?', (attachment_id,))
            db.commit()
        try:
            repository._remove_attachment_files([journal_id])
            counts['deleted'] += 1
        except Exception:
            counts['pending'] += 1
    return dict(counts)
