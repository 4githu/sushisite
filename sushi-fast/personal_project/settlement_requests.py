"""Owner-scoped settlement-request preview and explicit text-only delivery.

This candidate deliberately stores only opaque digests, counts, IDs, and state in
its durable outbox. Snapshot contents are read from the existing immutable
settlement snapshot and message text is rebuilt in memory for each request.
"""
from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Protocol
from uuid import uuid4


class SettlementRequestError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class TextBridge(Protocol):
    def search_exact(self, room: str) -> dict[str, Any]: ...
    def send_text(self, room: str, text: str) -> dict[str, Any]: ...


# Keep in sync with personal_project.schemas.ProgressStage, including legacy
# values that remain valid for stored clinic rounds.
_VALID_PROGRESS_STAGES = frozenset({
    "accepted",
    "grade1_semester1", "grade1_semester2", "grade2_semester1",
    "grade2_semester2", "grade3_semester1",
    "grade1_winter", "grade1_semester1_midterm", "grade1_semester1_final",
    "grade1_summer", "grade1_semester2_midterm", "grade1_semester2_final",
    "grade2_winter", "grade2_semester1_midterm", "grade2_semester1_final",
    "grade2_summer", "grade2_semester2_midterm", "grade2_semester2_final",
    "grade3_winter", "grade3_semester1_midterm", "grade3_semester1_final",
    "deep",
})


class KakaoBridgeTextOnly:
    """Narrow, injected adapter for redacted exact search + generic text send.

    Pass privacy-safe wrappers around kakao_bridge.invoke('search', room=...)
    and invoke('send', room=..., text=..., files=[]). This class never calls the
    report-specific native_kakao job APIs and never logs payloads itself.
    """

    def __init__(self, search_exact, send_text, operation_lock=None):
        self._search_exact = search_exact
        self._send_text = send_text
        self.operation_lock = operation_lock or threading.Lock()

    def search_exact(self, room: str) -> dict[str, Any]:
        return self._search_exact(room)

    def send_text(self, room: str, text: str) -> dict[str, Any]:
        return self._send_text(room, text)


class SettlementRequests:
    def __init__(self, db_path: str | Path, bridge: TextBridge):
        self.db_path = Path(db_path)
        self.bridge = bridge
        self.bridge_lock = getattr(bridge, "operation_lock", threading.Lock())
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with closing(self._connect()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS aura_settlement_request_outbox (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                snapshot_digest TEXT NOT NULL,
                plan_digest TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                sent_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, idempotency_key)
            )""")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_request_plan_dedupe "
                         "ON aura_settlement_request_outbox(user_id,snapshot_id,plan_digest) "
                         "WHERE status != 'blocked'")
            if "recipient_key_hash" not in {row[1] for row in conn.execute("PRAGMA table_info(aura_settlement_request_outbox)")}:
                conn.execute("ALTER TABLE aura_settlement_request_outbox ADD COLUMN recipient_key_hash TEXT NOT NULL DEFAULT ''")
            conn.execute("""CREATE TABLE IF NOT EXISTS aura_settlement_message_receipts(
                invoice_digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                request_id TEXT NOT NULL, state TEXT NOT NULL)
            """)
            conn.execute("UPDATE aura_settlement_message_receipts SET state='manual_check' WHERE state='sending'")
            # A process interruption after delivery starts is never replayed.
            conn.execute("UPDATE aura_settlement_request_outbox SET status='manual_check' WHERE status='sending'")

    @staticmethod
    def _digest(value: Any) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _sender_name(value: str) -> str:
        raw = str(value or "")
        if any(ord(char) < 32 for char in raw):
            raise SettlementRequestError(422, "invalid_sender_name", "보내는 조교 이름 형식이 올바르지 않습니다.")
        name = " ".join(raw.split()) or "김지후"
        if len(name) > 40:
            raise SettlementRequestError(422, "invalid_sender_name", "보내는 조교 이름 형식이 올바르지 않습니다.")
        return name

    def _snapshot(self, owner_id: int, snapshot_id: int):
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id,user_id,year,month,data_json,generated_at,pricing_version "
                "FROM aura_settlement_snapshots WHERE id=? AND user_id=?",
                (snapshot_id, owner_id),
            ).fetchone()
        if not row:
            raise SettlementRequestError(404, "snapshot_not_found", "정산 스냅샷을 찾을 수 없습니다.")
        if row["pricing_version"] < 6:
            raise SettlementRequestError(409, "snapshot_not_supported", "현재 정산 요청 계약과 호환되는 스냅샷이 아닙니다.")
        try:
            payload = json.loads(row["data_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise SettlementRequestError(409, "invalid_snapshot", "정산 스냅샷을 읽을 수 없습니다.") from exc
        snapshot_fingerprint = self._digest({
            "id": row["id"], "user_id": row["user_id"], "year": row["year"],
            "month": row["month"], "data_json": row["data_json"],
            "generated_at": row["generated_at"], "pricing_version": row["pricing_version"],
        })
        return row, payload, snapshot_fingerprint

    @staticmethod
    def _school_display_name(name: str) -> str:
        return re.sub(r"^(서울|경기|한성)(\d{2})(.*)$", r"\2\1\3", name)

    @staticmethod
    def _session_charge(item: dict[str, Any]) -> int:
        targets = item.get("targets") or []
        count = max(1, len(targets))
        if item.get("parentFreeForThreePlus") and count >= 3:
            return 0
        hourly = 40_000 if item.get("progressStage") == "deep" else 30_000 if count <= 3 else count * 10_000
        try:
            start = datetime.fromisoformat(str(item["startTime"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(item["endTime"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise SettlementRequestError(409, "invalid_snapshot", "정산 회차 시간이 올바르지 않습니다.") from exc
        seconds = max(0.0, (end - start).total_seconds())
        # The client contract uses Math.round; floor(x + .5) matches positive values.
        return math.floor((seconds / 3600) * hourly / count + 0.5)

    @staticmethod
    def _date_label(value: str) -> tuple[datetime, str]:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        date = date.replace(tzinfo=ZoneInfo("Asia/Seoul")) if date.tzinfo is None else date.astimezone(ZoneInfo("Asia/Seoul"))
        return date, f"{date.month}월 {date.day}일 {date.hour:02d}:{date.minute:02d}"

    @staticmethod
    def _hours_text(hours: float) -> str:
        minutes = math.floor(hours * 60 + 0.5)
        return f"{minutes // 60}시간 {minutes % 60}분" if minutes % 60 else f"{minutes // 60}시간"

    def _messages(self, snapshot: dict[str, Any], sender_name: str):
        grouped: dict[tuple[int, str, str], dict[str, Any]] = {}
        exclusions = {"acceptedStageStudents": 0, "unknownStageStudents": 0, "zeroParentChargeStudents": 0}
        accepted_keys: set[tuple[int, str, str]] = set()
        unknown_stage_keys: set[tuple[int, str, str]] = set()
        try:
            month = int(snapshot["month"])
            snapshot_items = snapshot.get("items", [])
            for item in snapshot_items:
                school_id = int(item["schoolId"])
                school = str(item["schoolName"]).strip()
                stage = item.get("progressStage")
                for target in item.get("targets") or []:
                    student = str(target["studentName"]).strip()
                    key = (school_id, school, student)
                    if stage == "accepted":
                        accepted_keys.add(key)
                    elif not isinstance(stage, str) or stage not in _VALID_PROGRESS_STAGES:
                        unknown_stage_keys.add(key)
            for item in snapshot_items:
                school_id = int(item["schoolId"])
                school = str(item["schoolName"]).strip()
                targets = item.get("targets") or []
                stage = item.get("progressStage")
                if stage == "accepted" or not isinstance(stage, str) or stage not in _VALID_PROGRESS_STAGES:
                    continue
                charge = self._session_charge(item)
                for target in targets:
                    student = str(target["studentName"]).strip()
                    if not school or not student:
                        raise ValueError("empty identity")
                    key = (school_id, school, student)
                    group = grouped.setdefault(key, {"school": school, "student": student, "billed": [], "charges": 0, "hours": {}})
                    if charge <= 0:
                        continue
                    start, start_label = self._date_label(str(item["startTime"]))
                    end, _ = self._date_label(str(item["endTime"]))
                    end_label = f"{end.hour:02d}:{end.minute:02d}"
                    ratio = f"{max(1, len(targets))}:1"
                    duration = max(0.0, (end - start).total_seconds() / 3600)
                    group["billed"].append((start, f"{start_label}~{end_label}"))
                    group["charges"] += charge
                    group["hours"][ratio] = group["hours"].get(ratio, 0.0) + duration
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, SettlementRequestError):
                raise
            raise SettlementRequestError(409, "invalid_snapshot", "정산 스냅샷의 학생·회차 항목이 올바르지 않습니다.") from exc

        exclusions["acceptedStageStudents"] = len(accepted_keys)
        exclusions["unknownStageStudents"] = len(unknown_stage_keys - accepted_keys)
        messages = []
        for (_school_id, school, student), group in sorted(grouped.items()):
            billed = group["billed"]
            amount = group["charges"]
            if not billed or amount <= 0:
                exclusions["zeroParentChargeStudents"] += 1
                continue
            billed.sort(key=lambda pair: pair[0])
            ratio_summary = " / ".join(
                f"{ratio} {self._hours_text(hours)}" for ratio, hours in group["hours"].items()
            )
            display_school = self._school_display_name(school)
            full_name = student if student.startswith(display_school) else f"{display_school} {student}"
            sessions = "\n".join(f"- {label}" for _, label in billed)
            body = (
                f"안녕하세요? {sender_name} 조교입니다. {month}월 클리닉 비용 안내드립니다.\n\n"
                f"[클리닉 시간]\n{sessions}\n\n[누적 시간]\n{ratio_summary}\n\n"
                f"입금해주셔야 할 금액은 {amount:,}원입니다.\n"
                f"학생 이름인 {full_name}(으)로 입금해주시면 감사하겠습니다.\n\n"
                "[클리닉 계좌]\n테라스터디 주식회사\n신한은행 140-015-133968"
            )
            messages.append({
                "studentKey": f"{_school_id}:{student}",
                "room": f"{school} {student} 생명클리닉",
                "text": body,
                "parentCharge": amount,
            })
        return messages, exclusions

    def _plan(self, snapshot_id: int, snapshot_fp: str, payload: dict[str, Any], sender_name: str, recipient_hash: str = ""):
        messages, exclusions = self._messages(payload, sender_name)
        if recipient_hash:
            messages = [item for item in messages if self._digest(item["studentKey"]) == recipient_hash]
            if not messages:
                raise SettlementRequestError(404, "recipient_not_billable", "선택한 학생은 이 월의 학부모 청구 대상이 아닙니다.")
        plan_fp = self._digest({
            "snapshotId": snapshot_id, "snapshotDigest": snapshot_fp, "senderName": sender_name,
            "messages": [{"room": item["room"], "textDigest": self._digest(item["text"]), "parentCharge": item["parentCharge"]} for item in messages],
        })
        return messages, plan_fp, exclusions

    @staticmethod
    def _exact_evidence(result: dict[str, Any], room: str) -> bool:
        return (isinstance(result, dict) and result.get("opened") is True and result.get("room") == room
                and result.get("searchEvidence") == "unique_exact")

    def create_for_month(self, *, owner_id: int, year: int, month: int, idempotency_key: str, sender_name: str = "김지후", student_key: str | None = None):
        if not 1 <= month <= 12:
            raise SettlementRequestError(422, "invalid_month", "정산 월이 올바르지 않습니다.")
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id FROM aura_settlement_snapshots WHERE user_id=? AND year=? AND month=? AND pricing_version>=6",
                (owner_id, year, month),
            ).fetchone()
        if not row:
            raise SettlementRequestError(404, "snapshot_not_found", "해당 월에 생성된 정산 스냅샷이 없습니다.")
        return self.create(owner_id=owner_id, snapshot_id=row["id"], idempotency_key=idempotency_key, sender_name=sender_name, student_key=student_key)

    def create(self, *, owner_id: int, snapshot_id: int, idempotency_key: str, sender_name: str = "김지후", student_key: str | None = None):
        sender_name = self._sender_name(sender_name)
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 100:
            raise SettlementRequestError(422, "invalid_idempotency_key", "요청 중복 방지 키 형식이 올바르지 않습니다.")
        row, payload, snapshot_fp = self._snapshot(owner_id, snapshot_id)
        recipient_hash = self._digest(student_key) if student_key is not None else ""
        messages, plan_fp, exclusions = self._plan(snapshot_id, snapshot_fp, payload, sender_name, recipient_hash)
        matched = []
        for message in messages:
            try:
                with self.bridge_lock:
                    evidence = self.bridge.search_exact(message["room"])
            except Exception as exc:
                raise SettlementRequestError(409, "recipient_unverified", "채팅방 확인이 불확실합니다. 전송하지 않았습니다.") from exc
            if not self._exact_evidence(evidence, message["room"]):
                raise SettlementRequestError(409, "recipient_unverified", f"{message['room']} 방을 확인하지 못했습니다. 최신 일정으로 정산을 다시 생성하거나 Mac 카카오톡의 방 이름을 확인해주세요. 전송하지 않았습니다.")
            matched.append({"room": message["room"], "evidence": "unique_exact", "parentCharge": message["parentCharge"]})
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM aura_settlement_request_outbox WHERE user_id=? AND idempotency_key=?",
                (owner_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["snapshot_digest"] != snapshot_fp or existing["plan_digest"] != plan_fp:
                    conn.rollback()
                    raise SettlementRequestError(409, "idempotency_conflict", "같은 요청 키가 다른 정산 내용에 이미 사용되었습니다.")
                request_id = existing["id"]
                status = existing["status"]
            else:
                prior_plan = conn.execute(
                    "SELECT * FROM aura_settlement_request_outbox "
                    "WHERE user_id=? AND snapshot_id=? AND plan_digest=? AND status != 'blocked'",
                    (owner_id, snapshot_id, plan_fp),
                ).fetchone()
                if prior_plan:
                    request_id = prior_plan["id"]
                    status = prior_plan["status"]
                else:
                    request_id = uuid4().hex
                    status = "awaiting_confirmation"
                    conn.execute(
                        "INSERT INTO aura_settlement_request_outbox "
                        "(id,user_id,snapshot_id,snapshot_digest,plan_digest,idempotency_key,status,message_count,recipient_key_hash) "
                        "VALUES(?,?,?,?,?,?,?,?,?)",
                        (request_id, owner_id, snapshot_id, snapshot_fp, plan_fp, idempotency_key, status, len(messages), recipient_hash),
                    )
            conn.commit()
        return {
            "requestId": request_id, "snapshotId": snapshot_id,
            "snapshotDigest": snapshot_fp, "planDigest": plan_fp,
            "status": status, "messageCount": len(messages), "matchedRooms": matched,
            "messagePreviews": [{"room": item["room"], "text": item["text"], "parentCharge": item["parentCharge"]} for item in messages],
            "exclusionSummary": exclusions,
            "excludedStudentCount": sum(exclusions.values()),
        }

    def confirm(self, *, owner_id: int, request_id: str, plan_digest: str, sender_name: str = "김지후"):
        sender_name = self._sender_name(sender_name)
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            request = conn.execute(
                "SELECT * FROM aura_settlement_request_outbox WHERE id=? AND user_id=?",
                (request_id, owner_id),
            ).fetchone()
            if not request:
                conn.rollback()
                raise SettlementRequestError(404, "request_not_found", "정산 요청을 찾을 수 없습니다.")
            if request["plan_digest"] != plan_digest:
                conn.rollback()
                raise SettlementRequestError(409, "approval_mismatch", "승인 내용이 미리보기와 일치하지 않습니다.")
            if request["status"] == "succeeded":
                conn.commit()
                return {"requestId": request_id, "status": "succeeded", "sentCount": request["sent_count"], "alreadySentCount": max(0, request["message_count"] - request["sent_count"])}
            if request["status"] == "manual_check":
                conn.rollback()
                raise SettlementRequestError(409, "manual_check_only", "전송 여부를 직접 확인해야 합니다. 자동 재시도하지 않습니다.")
            if request["status"] == "sending":
                conn.rollback()
                raise SettlementRequestError(409, "manual_check_only", "전송 처리 중이거나 상태가 불확실합니다. 자동 재시도하지 않습니다.")
            if request["status"] not in {"awaiting_confirmation", "retryable"}:
                conn.rollback()
                raise SettlementRequestError(409, "request_not_confirmable", "이 요청은 더 이상 확인할 수 없습니다.")
            row, payload, snapshot_fp = self._snapshot(owner_id, request["snapshot_id"])
            messages, actual_plan_fp, _exclusions = self._plan(request["snapshot_id"], snapshot_fp, payload, sender_name, request["recipient_key_hash"])
            if snapshot_fp != request["snapshot_digest"] or actual_plan_fp != request["plan_digest"]:
                conn.execute("UPDATE aura_settlement_request_outbox SET status='blocked' WHERE id=?", (request_id,))
                conn.commit()
                raise SettlementRequestError(409, "snapshot_changed", "승인 후 정산 스냅샷이 변경되었습니다. 새 미리보기가 필요합니다.")
            conn.execute(
                "UPDATE aura_settlement_request_outbox SET status='sending' "
                "WHERE id=? AND status IN ('awaiting_confirmation','retryable')",
                (request_id,),
            )
            conn.commit()

        sent_count = 0
        already_sent_count = 0
        for message in messages:
            invoice = self._digest({"owner": owner_id, "year": row["year"], "month": row["month"],
                                    "studentKey": message["studentKey"], "room": message["room"],
                                    "textDigest": self._digest(message["text"]), "amount": message["parentCharge"]})
            claimed = False
            try:
                with self.bridge_lock:
                    receipt = self._claim_invoice(owner_id, request_id, invoice)
                    if receipt == "succeeded":
                        already_sent_count += 1
                        self._set_status(request_id, "sending", sent_count)
                        continue
                    if receipt != "claimed":
                        self._set_status(request_id, "manual_check", sent_count)
                        return {"requestId": request_id, "status": "manual_check", "sentCount": sent_count}
                    claimed = True
                    evidence = self.bridge.search_exact(message["room"])
                    if not self._exact_evidence(evidence, message["room"]):
                        self._finish_invoice(owner_id, invoice, "blocked")
                        claimed = False
                        if sent_count:
                            self._set_status(request_id, "manual_check", sent_count)
                            return {"requestId": request_id, "status": "manual_check", "sentCount": sent_count}
                        self._set_status(request_id, "blocked", sent_count)
                        raise SettlementRequestError(409, "recipient_unverified", "확인 단계에서 정확한 고유 방을 재검증하지 못했습니다. 전송하지 않았습니다.")
                    result = self.bridge.send_text(message["room"], message["text"])
                    if isinstance(result, dict) and result.get("sent") is True:
                        receipt_state = "succeeded"
                    elif (
                        isinstance(result, dict)
                        and result.get("committed") is False
                        and result.get("uncertain") is False
                    ):
                        receipt_state = "retryable"
                    else:
                        receipt_state = "manual_check"
                    self._finish_invoice(owner_id, invoice, receipt_state)
                if receipt_state == "retryable":
                    self._set_status(request_id, "retryable", sent_count)
                    return {
                        "requestId": request_id,
                        "status": "retryable",
                        "sentCount": sent_count,
                        "retryable": True,
                    }
                if receipt_state != "succeeded":
                    self._set_status(request_id, "manual_check", sent_count)
                    return {"requestId": request_id, "status": "manual_check", "sentCount": sent_count}
                sent_count += 1
                self._set_status(request_id, "sending", sent_count)
            except SettlementRequestError:
                if claimed:
                    self._finish_invoice(owner_id, invoice, "manual_check")
                raise
            except Exception:
                if claimed:
                    self._finish_invoice(owner_id, invoice, "manual_check")
                self._set_status(request_id, "manual_check", sent_count)
                return {"requestId": request_id, "status": "manual_check", "sentCount": sent_count}
        self._set_status(request_id, "succeeded", sent_count)
        return {"requestId": request_id, "status": "succeeded", "sentCount": sent_count, "alreadySentCount": already_sent_count}

    def _claim_invoice(self, owner_id, request_id, invoice):
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT state FROM aura_settlement_message_receipts WHERE user_id=? AND invoice_digest=?", (owner_id, invoice)).fetchone()
            if row and row["state"] not in {"blocked", "retryable"}:
                conn.commit()
                return row["state"]
            conn.execute("INSERT INTO aura_settlement_message_receipts(invoice_digest,user_id,request_id,state) VALUES(?,?,?,'sending') ON CONFLICT(invoice_digest) DO UPDATE SET request_id=excluded.request_id,state=excluded.state", (invoice, owner_id, request_id))
            conn.commit()
            return "claimed"

    def _finish_invoice(self, owner_id, invoice, state):
        with closing(self._connect()) as conn:
            conn.execute("UPDATE aura_settlement_message_receipts SET state=? WHERE user_id=? AND invoice_digest=?", (state, owner_id, invoice))

    def _set_status(self, request_id: str, status: str, sent_count: int):
        with closing(self._connect()) as conn:
            conn.execute("UPDATE aura_settlement_request_outbox SET status=?,sent_count=? WHERE id=?",
                         (status, sent_count, request_id))


def build_router(service: SettlementRequests, owner_dependency):
    """Build FastAPI endpoints with the host's authenticated owner dependency."""
    from fastapi import APIRouter, Depends, HTTPException, Response
    from pydantic import BaseModel, Field

    router = APIRouter(prefix="/aura/settlement-requests", tags=["aura-settlement-requests"])

    class CreateRequest(BaseModel):
        year: int = Field(ge=2000, le=2100)
        month: int = Field(ge=1, le=12)
        idempotencyKey: str = Field(min_length=8, max_length=100)
        senderName: str = Field(default="김지후", max_length=40)
        studentKey: str | None = Field(default=None, min_length=1, max_length=300)

    class ConfirmRequest(BaseModel):
        planDigest: str = Field(min_length=64, max_length=64)
        senderName: str = Field(default="김지후", max_length=40)

    def translate_error(error: SettlementRequestError):
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})

    @router.post("/preview")
    def create_preview(data: CreateRequest, response: Response, owner_id: int = Depends(owner_dependency)):
        response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
        try:
            return service.create_for_month(owner_id=owner_id, year=data.year, month=data.month, idempotency_key=data.idempotencyKey, sender_name=data.senderName, student_key=data.studentKey)
        except SettlementRequestError as error:
            translate_error(error)

    @router.post("/{request_id}/confirm")
    def confirm_request(request_id: str, data: ConfirmRequest, owner_id: int = Depends(owner_dependency)):
        try:
            return service.confirm(owner_id=owner_id, request_id=request_id, plan_digest=data.planDigest, sender_name=data.senderName)
        except SettlementRequestError as error:
            translate_error(error)

    return router
