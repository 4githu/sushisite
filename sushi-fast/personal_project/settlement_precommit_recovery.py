"""Audited DB-only recovery for one proven Kakao precommit failure.

This command never imports or instantiates the production bridge and never sends.
It only changes one retryable request and its matching receipt after verifying the
redacted operation log, bridge commit/uncertainty invariant, immutable snapshot,
plan hash, and exact invoice digest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import sqlite3
from typing import Any

from .settlement_requests import SettlementRequests

HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-f0-9]{32}$")
FIELD = re.compile(r"([a-z_]+)=([^ ]+)")


class RecoveryRefused(RuntimeError):
    pass


def _log_evidence(log_path: Path, operation_id: str, room_key: str) -> dict[str, str]:
    matches: list[dict[str, str]] = []
    for line in log_path.read_text(errors="replace").splitlines():
        fields = dict(FIELD.findall(line))
        if fields.get("operation") == operation_id:
            matches.append(fields)
    if len(matches) != 1:
        raise RecoveryRefused("operation_log_match_count")
    evidence = matches[0]
    expected = {"room_key": room_key, "command": "send", "outcome": "error",
                "error_code": "bridge_error", "uncertain": "False"}
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise RecoveryRefused("operation_log_evidence_mismatch")
    if "committed" in evidence and evidence["committed"] != "False":
        raise RecoveryRefused("operation_log_committed_not_false")
    return evidence


def _bridge_proves_commit_equivalence(source_path: Path) -> bool:
    source = source_path.read_text(errors="replace")
    required = ("var committed=false", "committed=true // A posted mouse click",
                '"committed":committed,"uncertain":committed')
    return all(marker in source for marker in required)


def _utc_time(value: str, *, require_zone: bool) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    if parsed.tzinfo is None:
        if require_zone:
            raise RecoveryRefused("operation_log_timestamp_has_no_timezone")
        # SQLite CURRENT_TIMESTAMP is UTC in this application's request schema.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _invoice_and_room(conn: sqlite3.Connection, request: sqlite3.Row,
                      invoice_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = conn.execute(
        "SELECT id,user_id,year,month,data_json FROM aura_settlement_snapshots WHERE id=? AND user_id=?",
        (request["snapshot_id"], request["user_id"]),
    ).fetchone()
    if not snapshot:
        raise RecoveryRefused("receipt_request_snapshot_missing")
    payload = json.loads(snapshot["data_json"])
    service = object.__new__(SettlementRequests)
    messages, _ = service._messages(payload, "김지후")
    recipient_hash = request["recipient_key_hash"] or ""
    if recipient_hash:
        messages = [m for m in messages if SettlementRequests._digest(m["studentKey"]) == recipient_hash]
    matches = []
    for message in messages:
        candidate = SettlementRequests._digest({
            "owner": request["user_id"], "year": snapshot["year"], "month": snapshot["month"],
            "studentKey": message["studentKey"], "room": message["room"],
            "textDigest": SettlementRequests._digest(message["text"]),
            "amount": message["parentCharge"],
        })
        if candidate == invoice_digest:
            matches.append((snapshot, message))
    if len(matches) != 1:
        raise RecoveryRefused("invoice_not_linked_to_request")
    return matches[0]


def _validate_origin_request(conn: sqlite3.Connection, *, invoice_digest: str,
                             receipt_request_id: str, user_id: int, room_key: str,
                             log_at_utc: datetime) -> None:
    origin = conn.execute(
        "SELECT id,user_id,snapshot_id,status,sent_count,message_count,recipient_key_hash,created_at "
        "FROM aura_settlement_request_outbox WHERE id=?", (receipt_request_id,),
    ).fetchone()
    if not origin or origin["user_id"] != user_id:
        raise RecoveryRefused("receipt_request_owner_mismatch")
    if origin["status"] not in {"manual_check", "retryable"} or origin["sent_count"] != 0 or origin["message_count"] != 1:
        raise RecoveryRefused("receipt_request_not_recoverable")
    _, message = _invoice_and_room(conn, origin, invoice_digest)
    actual_room_key = hashlib.sha256(str(message["room"]).encode()).hexdigest()[:16]
    if actual_room_key != room_key:
        raise RecoveryRefused("room_key_not_linked_to_invoice")
    created_at = _utc_time(origin["created_at"], require_zone=False)
    age_seconds = (log_at_utc - created_at).total_seconds()
    if age_seconds < 0 or age_seconds > 600:
        raise RecoveryRefused("operation_outside_request_window")


def _validate_target(conn: sqlite3.Connection, *, invoice_digest: str,
                     receipt_request_id: str, retry_request_id: str,
                     room_key: str) -> tuple[int, str, str]:
    receipt = conn.execute(
        "SELECT user_id,request_id,state FROM aura_settlement_message_receipts WHERE invoice_digest=?",
        (invoice_digest,),
    ).fetchone()
    if not receipt or receipt["request_id"] != receipt_request_id:
        raise RecoveryRefused("receipt_identity_mismatch")
    if receipt["state"] not in {"manual_check", "retryable"}:
        raise RecoveryRefused("receipt_state_not_recoverable")

    request = conn.execute(
        "SELECT id,user_id,snapshot_id,snapshot_digest,plan_digest,status,sent_count,message_count,recipient_key_hash "
        "FROM aura_settlement_request_outbox WHERE id=?", (retry_request_id,),
    ).fetchone()
    if not request or request["user_id"] != receipt["user_id"]:
        raise RecoveryRefused("request_identity_mismatch")
    if request["status"] not in {"manual_check", "retryable"}:
        raise RecoveryRefused("request_state_not_recoverable")
    if request["sent_count"] != 0 or request["message_count"] != 1:
        raise RecoveryRefused("request_counts_not_recoverable")

    snapshot = conn.execute(
        "SELECT id,user_id,year,month,data_json,generated_at,pricing_version "
        "FROM aura_settlement_snapshots WHERE id=? AND user_id=?",
        (request["snapshot_id"], request["user_id"]),
    ).fetchone()
    if not snapshot:
        raise RecoveryRefused("snapshot_missing")
    payload = json.loads(snapshot["data_json"])
    snapshot_digest = SettlementRequests._digest({
        "id": snapshot["id"], "user_id": snapshot["user_id"],
        "year": snapshot["year"], "month": snapshot["month"],
        "data_json": snapshot["data_json"], "generated_at": snapshot["generated_at"],
        "pricing_version": snapshot["pricing_version"],
    })
    if snapshot_digest != request["snapshot_digest"]:
        raise RecoveryRefused("snapshot_changed_since_preview")

    # Confirm defaults senderName to 김지후; recompute the deterministic plan locally.
    service = object.__new__(SettlementRequests)
    messages, _ = service._messages(payload, "김지후")
    recipient_hash = request["recipient_key_hash"] or ""
    if recipient_hash:
        messages = [m for m in messages if SettlementRequests._digest(m["studentKey"]) == recipient_hash]
    plan_digest = SettlementRequests._digest({
        "snapshotId": request["snapshot_id"], "snapshotDigest": snapshot_digest,
        "senderName": "김지후",
        "messages": [{"room": m["room"], "textDigest": SettlementRequests._digest(m["text"]),
                      "parentCharge": m["parentCharge"]} for m in messages],
    })
    if plan_digest != request["plan_digest"] or len(messages) != 1:
        raise RecoveryRefused("plan_digest_mismatch")

    matching_invoices = []
    for message in messages:
        candidate = SettlementRequests._digest({
            "owner": request["user_id"], "year": snapshot["year"], "month": snapshot["month"],
            "studentKey": message["studentKey"], "room": message["room"],
            "textDigest": SettlementRequests._digest(message["text"]),
            "amount": message["parentCharge"],
        })
        if candidate == invoice_digest:
            matching_invoices.append(candidate)
    if len(matching_invoices) != 1:
        raise RecoveryRefused("invoice_digest_not_in_current_plan")
    actual_room_key = hashlib.sha256(str(messages[0]["room"]).encode()).hexdigest()[:16]
    if actual_room_key != room_key:
        raise RecoveryRefused("room_key_not_linked_to_invoice")
    return int(request["user_id"]), str(request["plan_digest"]), str(snapshot_digest)


def recover(*, db_path: Path, log_path: Path, bridge_source: Path,
            invoice_digest: str, receipt_request_id: str, retry_request_id: str,
            operation_id: str, room_key: str) -> dict[str, Any]:
    if not HEX64.fullmatch(invoice_digest):
        raise RecoveryRefused("invalid_invoice_digest")
    if not IDENTIFIER.fullmatch(receipt_request_id) or not IDENTIFIER.fullmatch(retry_request_id):
        raise RecoveryRefused("invalid_request_id")
    if not IDENTIFIER.fullmatch(operation_id) or not re.fullmatch(r"[a-f0-9]{16}", room_key):
        raise RecoveryRefused("invalid_operation_evidence_id")
    evidence = _log_evidence(log_path, operation_id, room_key)
    if not _bridge_proves_commit_equivalence(bridge_source):
        raise RecoveryRefused("bridge_commit_evidence_unavailable")

    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        audit_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='aura_settlement_recovery_audit'"
        ).fetchone()
        prior = conn.execute(
            "SELECT invoice_digest,receipt_request_id,retry_request_id,room_key,committed,uncertain "
            "FROM aura_settlement_recovery_audit WHERE operation_id=?", (operation_id,),
        ).fetchone() if audit_table else None
        if prior:
            expected_prior = (invoice_digest, receipt_request_id, retry_request_id, room_key, 0, 0)
            actual_prior = tuple(prior[key] for key in (
                "invoice_digest", "receipt_request_id", "retry_request_id", "room_key", "committed", "uncertain"
            ))
            if actual_prior != expected_prior:
                raise RecoveryRefused("audit_operation_id_conflict")
            current_receipt = conn.execute(
                "SELECT state FROM aura_settlement_message_receipts WHERE invoice_digest=? AND request_id=?",
                (invoice_digest, receipt_request_id),
            ).fetchone()
            current_request = conn.execute(
                "SELECT status FROM aura_settlement_request_outbox WHERE id=?",
                (retry_request_id,),
            ).fetchone()
            if (not current_receipt or current_receipt["state"] not in {"retryable", "succeeded"}
                    or not current_request or current_request["status"] not in {"retryable", "succeeded"}):
                raise RecoveryRefused("audit_state_conflict")
            conn.commit()
            return {"status": "already_applied", "retryRequestId": retry_request_id,
                    "requestStatus": current_request["status"],
                    "receiptState": current_receipt["state"], "operationId": operation_id}

        log_at_utc = _utc_time(evidence.get("at_utc", ""), require_zone=True)
        user_id, plan_digest, snapshot_digest = _validate_target(
            conn, invoice_digest=invoice_digest, receipt_request_id=receipt_request_id,
            retry_request_id=retry_request_id, room_key=room_key,
        )
        _validate_origin_request(
            conn, invoice_digest=invoice_digest, receipt_request_id=receipt_request_id,
            user_id=user_id, room_key=room_key, log_at_utc=log_at_utc,
        )
        conn.execute("""CREATE TABLE IF NOT EXISTS aura_settlement_recovery_audit (
            operation_id TEXT PRIMARY KEY, invoice_digest TEXT NOT NULL,
            receipt_request_id TEXT NOT NULL, retry_request_id TEXT NOT NULL,
            room_key TEXT NOT NULL, error_code TEXT NOT NULL,
            committed INTEGER NOT NULL CHECK(committed=0),
            uncertain INTEGER NOT NULL CHECK(uncertain=0),
            plan_digest TEXT NOT NULL, snapshot_digest TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute(
            "UPDATE aura_settlement_message_receipts SET state='retryable' "
            "WHERE invoice_digest=? AND user_id=? AND request_id=? AND state='manual_check'",
            (invoice_digest, user_id, receipt_request_id),
        )
        conn.execute(
            "UPDATE aura_settlement_request_outbox SET status='retryable' "
            "WHERE id=? AND user_id=? AND status='manual_check' AND sent_count=0 AND message_count=1",
            (retry_request_id, user_id),
        )
        current_receipt = conn.execute(
            "SELECT state FROM aura_settlement_message_receipts WHERE invoice_digest=? AND user_id=?",
            (invoice_digest, user_id),
        ).fetchone()
        current_request = conn.execute(
            "SELECT status FROM aura_settlement_request_outbox WHERE id=? AND user_id=?",
            (retry_request_id, user_id),
        ).fetchone()
        if (not current_receipt or current_receipt["state"] != "retryable"
                or not current_request or current_request["status"] != "retryable"):
            raise RecoveryRefused("target_state_transition_failed")
        conn.execute(
            "INSERT INTO aura_settlement_recovery_audit "
            "(operation_id,invoice_digest,receipt_request_id,retry_request_id,room_key,error_code,committed,uncertain,plan_digest,snapshot_digest) "
            "VALUES(?,?,?,?,?,?,0,0,?,?)",
            (operation_id, invoice_digest, receipt_request_id, retry_request_id,
             room_key, evidence["error_code"], plan_digest, snapshot_digest),
        )
        conn.commit()
        return {"status": "recovered", "retryRequestId": retry_request_id,
                "receiptState": "retryable", "operationId": operation_id}
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover one audited, proven precommit failure; DB only.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--bridge-source", type=Path, required=True)
    parser.add_argument("--invoice-digest", required=True)
    parser.add_argument("--receipt-request-id", required=True)
    parser.add_argument("--retry-request-id", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--room-key", required=True)
    args = parser.parse_args()
    try:
        result = recover(
            db_path=args.db, log_path=args.log, bridge_source=args.bridge_source,
            invoice_digest=args.invoice_digest, receipt_request_id=args.receipt_request_id,
            retry_request_id=args.retry_request_id, operation_id=args.operation_id,
            room_key=args.room_key,
        )
    except (OSError, sqlite3.Error, ValueError, RecoveryRefused) as exc:
        print(json.dumps({"status": "refused", "code": str(exc) or type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
