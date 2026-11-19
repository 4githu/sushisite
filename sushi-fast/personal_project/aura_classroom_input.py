"""Owner-scoped read adapter for the Aura classroom scheduler.

No scheduler, identity discovery, GUI bridge or operational configuration lives here.
The caller supplies an authenticated owner ID; tests use an isolated SQLite DB; classroom_delivery binds the production owner.
"""
from datetime import timedelta
from . import repository
from .aura_classroom_outbox import KST, _instant


def read_owner_rounds(user_id: int, now):
    """Read one consistent owner snapshot, filter by D+1 KST start instant.

    Deliberately avoid lexicographic SQL datetime filtering: legacy naive local
    strings and offset-aware strings may describe the same instant differently.
    """
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError('authenticated owner ID required')
    if now.tzinfo is None:
        raise ValueError('timezone-aware now required')
    target = now.astimezone(KST).date() + timedelta(days=1)
    with repository.connection() as conn:
        conn.execute('BEGIN')
        rows = conn.execute(repository._round_query() +
            ' WHERE r.user_id = ? ORDER BY r.id', (user_id,)).fetchall()
        selected = []
        for row in rows:
            # A cross-owner school/event reference is corruption, not an omission.
            owners = conn.execute('SELECT (SELECT user_id FROM aura_schools WHERE id=?), '
                                  '(SELECT user_id FROM events WHERE id=?)',
                                  (row['school_id'], row['event_id'])).fetchone()
            if tuple(owners) != (user_id, user_id):
                raise ValueError('cross_owner_reference')
            if _instant(row['start_time']).astimezone(KST).date() == target:
                selected.append(repository._round_dict(conn, row))
        return selected
