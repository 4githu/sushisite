"""Atomically preserve manually saved AI output during background generation."""
import json

from . import repository


def save_if_missing(user_id, report_id, output, model):
    # The conditional update is one SQLite statement: a manual save committed
    # while the provider was running wins and can never be overwritten here.
    with repository.connection() as conn:
        result = conn.execute("""
            UPDATE aura_target_reports
            SET generated_report_json=?, ai_model=?, has_user_edits=1,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND (generated_report_json IS NULL
                OR TRIM(generated_report_json) IN ('', 'null', '{}'))
              AND EXISTS (
                SELECT 1 FROM aura_round_targets t
                JOIN aura_clinic_rounds r ON r.id=t.round_id
                WHERE t.id=aura_target_reports.target_id AND r.user_id=?
              )
        """, (json.dumps(output, ensure_ascii=False), model, report_id, user_id))
        conn.commit()
        return bool(result.rowcount)
