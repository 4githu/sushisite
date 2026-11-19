from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_project.settlement_requests import SettlementRequests, SettlementRequestError, build_router


OWNER = 41
OTHER = 42


class FakeBridge:
    def __init__(self, failures=None):
        self.failures = failures or {}
        self.searches = []
        self.sent = []

    def search_exact(self, room):
        self.searches.append(room)
        result = self.failures.get(room, {"opened": True, "room": room, "searchEvidence": "unique_exact"})
        if isinstance(result, list):
            return result.pop(0) if result else {"opened": True, "room": room, "searchEvidence": "unique_exact"}
        return result

    def send_text(self, room, text):
        self.sent.append((room, text))
        failure = self.failures.get(("send", room), self.failures.get("send"))
        if failure:
            raise failure
        return {"sent": True}


def make_snapshot(path, owner=OWNER, snapshot_id=7, items=None):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aura_settlement_snapshots (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, year INTEGER NOT NULL,
            month INTEGER NOT NULL, data_json TEXT NOT NULL, generated_at TEXT NOT NULL,
            pricing_version INTEGER NOT NULL DEFAULT 6,
            UNIQUE(user_id, year, month))""")
        payload = {"year": 2026, "month": 9, "totalAmount": 77777,
            "items": items if items is not None else [
                {"id": 101, "schoolId": 1, "schoolName": "합성고", "roundLabel": "1회",
                 "startTime": "2026-09-02T09:00:00+09:00", "endTime": "2026-09-02T10:00:00+09:00",
                 "progressStage": "grade1_winter", "parentFreeForThreePlus": False, "amount": 77777,
                 "targets": [{"studentName": "가상학생"}]},
                {"id": 102, "schoolId": 1, "schoolName": "합성고", "roundLabel": "2회",
                 "startTime": "2026-09-03T09:00:00+09:00", "endTime": "2026-09-03T10:00:00+09:00",
                 "progressStage": "grade1_winter", "parentFreeForThreePlus": True, "amount": 22222,
                 "targets": [{"studentName": "가상학생"}, {"studentName": "무료1"}, {"studentName": "무료2"}]},
                {"id": 103, "schoolId": 1, "schoolName": "합성고", "roundLabel": "합자반 1회",
                 "startTime": "2026-09-04T09:00:00+09:00", "endTime": "2026-09-04T10:00:00+09:00",
                 "progressStage": "accepted", "parentFreeForThreePlus": False, "amount": 19999,
                 "targets": [{"studentName": "합자학생"}]}
            ]}
        conn.execute("INSERT OR REPLACE INTO aura_settlement_snapshots(id,user_id,year,month,data_json,generated_at,pricing_version) VALUES(?,?,?,?,?,?,6)",
                     (snapshot_id, owner, 2026, 9, json.dumps(payload, ensure_ascii=False), "2026-09-30T00:00:00+09:00"))
        conn.commit()


class SettlementRequestsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.sqlite"
        make_snapshot(self.path)
        self.bridge = FakeBridge()
        self.service = SettlementRequests(self.path, self.bridge)

    def tearDown(self):
        self.temp.cleanup()

    def test_http_preview_and_confirm_bind_json_bodies(self):
        app = FastAPI()
        app.include_router(build_router(self.service, lambda: OWNER), prefix="/api/personal")
        client = TestClient(app)

        preview_response = client.post(
            "/api/personal/aura/settlement-requests/preview",
            json={"year": 2026, "month": 9, "idempotencyKey": "integration-key-001", "senderName": "김지후"},
        )
        self.assertEqual(preview_response.status_code, 200, preview_response.text)
        self.assertEqual(preview_response.headers["cache-control"], "no-store, no-cache, max-age=0, must-revalidate")
        preview = preview_response.json()
        self.assertEqual(preview["messageCount"], 1)
        self.assertEqual(preview["exclusionSummary"], {
            "acceptedStageStudents": 1, "unknownStageStudents": 0, "zeroParentChargeStudents": 2
        })
        self.assertEqual(self.bridge.searches, ["합성고 가상학생 생명클리닉"])

        confirm_response = client.post(
            f"/api/personal/aura/settlement-requests/{preview['requestId']}/confirm",
            json={"planDigest": preview["planDigest"], "senderName": "김지후"},
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.text)
        self.assertEqual(confirm_response.json()["status"], "succeeded")
        self.assertEqual(len(self.bridge.sent), 1)

    def test_preview_and_confirm_send_only_positive_parent_charge_messages(self):
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0001")
        self.assertEqual(preview["messageCount"], 1)
        self.assertEqual(preview["exclusionSummary"], {
            "acceptedStageStudents": 1, "unknownStageStudents": 0, "zeroParentChargeStudents": 2
        })
        self.assertEqual(preview["matchedRooms"], [{"room": "합성고 가상학생 생명클리닉", "evidence": "unique_exact", "parentCharge": 30000}])
        self.assertEqual(self.bridge.searches, ["합성고 가상학생 생명클리닉"])
        result = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(result["status"], "succeeded")
        repeated = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(repeated["status"], "succeeded")
        self.assertEqual(self.bridge.sent, [("합성고 가상학생 생명클리닉", "안녕하세요? 김지후 조교입니다. 9월 클리닉 비용 안내드립니다.\n\n[클리닉 시간]\n- 9월 2일 09:00~10:00\n\n[누적 시간]\n1:1 1시간\n\n입금해주셔야 할 금액은 30,000원입니다.\n학생 이름인 합성고 가상학생(으)로 입금해주시면 감사하겠습니다.\n\n[클리닉 계좌]\n테라스터디 주식회사\n신한은행 140-015-133968")])

        with closing(sqlite3.connect(self.path)) as conn:
            saved = json.loads(conn.execute("SELECT data_json FROM aura_settlement_snapshots WHERE id=7").fetchone()[0])
        self.assertEqual(saved["totalAmount"], 77777)
        self.assertEqual([item["amount"] for item in saved["items"]], [77777, 22222, 19999])

    def test_snapshot_reads_are_owner_scoped(self):
        with self.assertRaises(SettlementRequestError) as error:
            self.service.create(owner_id=OTHER, snapshot_id=7, idempotency_key="foreign-snapshot-1")
        self.assertEqual(error.exception.code, "snapshot_not_found")
        self.assertEqual(self.bridge.searches, [])
        self.assertEqual(self.bridge.sent, [])

    def test_zero_parent_charge_only_snapshot_has_no_recipient_discovery_or_send(self):
        zero_round = {"id": 201, "schoolId": 1, "schoolName": "합성고", "roundLabel": "무료회차",
            "startTime": "2026-09-05T09:00:00+09:00", "endTime": "2026-09-05T10:00:00+09:00",
            "progressStage": "grade1_winter", "parentFreeForThreePlus": True, "amount": 12345,
            "targets": [{"studentName": "무료학생"}, {"studentName": "무료학생2"}, {"studentName": "무료학생3"}]}
        make_snapshot(self.path, items=[zero_round])
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="zero-only-key-01")
        self.assertEqual(preview["messageCount"], 0)
        self.assertEqual(preview["matchedRooms"], [])
        self.assertEqual(self.bridge.searches, [])
        result = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["sentCount"], 0)
        self.assertEqual(self.bridge.sent, [])
        with closing(sqlite3.connect(self.path)) as conn:
            saved = json.loads(conn.execute("SELECT data_json FROM aura_settlement_snapshots WHERE id=7").fetchone()[0])
        self.assertEqual(saved["totalAmount"], 77777)
        self.assertEqual(saved["items"][0]["amount"], 12345)

    def test_ambiguous_locked_uncertain_same_name_and_self_chat_never_send(self):
        requested = "합성고 가상학생 생명클리닉"
        results = [
            {"opened": True, "room": requested, "searchEvidence": "ambiguous"},
            {"opened": False, "room": requested, "searchEvidence": "locked"},
            {"opened": None, "room": requested, "searchEvidence": "uncertain"},
            {"opened": True, "room": "동명이인 채팅", "searchEvidence": "unique_exact"},
            {"opened": True, "room": "나와의 채팅", "searchEvidence": "unique_exact"},
        ]
        for index, evidence in enumerate(results):
            with self.subTest(evidence=evidence):
                temp = tempfile.TemporaryDirectory()
                path = Path(temp.name) / "synthetic.sqlite"
                make_snapshot(path)
                bridge = FakeBridge({requested: evidence})
                service = SettlementRequests(path, bridge)
                with self.assertRaises(SettlementRequestError):
                    service.create(owner_id=OWNER, snapshot_id=7, idempotency_key=f"unsafe-room-key-{index}")
                self.assertEqual(bridge.sent, [])
                temp.cleanup()

    def test_unknown_progress_stage_fails_closed_without_room_search(self):
        with closing(sqlite3.connect(self.path)) as conn:
            raw = conn.execute("SELECT data_json FROM aura_settlement_snapshots WHERE id=7").fetchone()[0]
            snapshot = json.loads(raw)
            del snapshot["items"][0]["progressStage"]
            conn.execute("UPDATE aura_settlement_snapshots SET data_json=? WHERE id=7", (json.dumps(snapshot, ensure_ascii=False),))
            conn.commit()
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="unknown-stage-01")
        self.assertEqual(preview["messageCount"], 0)
        self.assertEqual(preview["matchedRooms"], [])
        self.assertEqual(preview["exclusionSummary"]["unknownStageStudents"], 1)
        self.assertEqual(self.bridge.searches, [])
        self.assertEqual(self.bridge.sent, [])

    def test_unknown_nonempty_progress_stage_fails_closed_before_room_search(self):
        item = {"id": 202, "schoolId": 1, "schoolName": "합성고", "roundLabel": "1회",
            "startTime": "2026-09-06T09:00:00+09:00", "endTime": "2026-09-06T10:00:00+09:00",
            "progressStage": "not-a-known-stage", "parentFreeForThreePlus": False, "amount": 30000,
            "targets": [{"studentName": "미지정단계학생"}]}
        make_snapshot(self.path, items=[item])
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="unknown-stage-string-01")
        self.assertEqual(preview["messageCount"], 0)
        self.assertEqual(preview["matchedRooms"], [])
        self.assertEqual(preview["exclusionSummary"]["unknownStageStudents"], 1)
        self.assertEqual(self.bridge.searches, [])
        self.assertEqual(self.bridge.sent, [])

    def test_legacy_progress_stage_remains_eligible(self):
        item = {"id": 203, "schoolId": 1, "schoolName": "합성고", "roundLabel": "1회",
            "startTime": "2026-09-06T09:00:00+09:00", "endTime": "2026-09-06T10:00:00+09:00",
            "progressStage": "grade1_semester1", "parentFreeForThreePlus": False, "amount": 30000,
            "targets": [{"studentName": "기존단계학생"}]}
        make_snapshot(self.path, items=[item])
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="legacy-stage-01")
        self.assertEqual(preview["messageCount"], 1)
        self.assertEqual(preview["exclusionSummary"]["unknownStageStudents"], 0)
        self.assertEqual(self.bridge.searches, ["합성고 기존단계학생 생명클리닉"])

    def test_partial_send_stops_and_marks_manual_check(self):
        items = []
        for index, name in enumerate(("학생A", "학생B"), 1):
            items.append({"id": 300 + index, "schoolId": 1, "schoolName": "합성고", "roundLabel": f"{index}회",
                "startTime": f"2026-09-0{index + 1}T09:00:00+09:00", "endTime": f"2026-09-0{index + 1}T10:00:00+09:00",
                "progressStage": "grade1_winter", "parentFreeForThreePlus": False, "amount": 30000,
                "targets": [{"studentName": name}]})
        make_snapshot(self.path, items=items)
        self.bridge.failures[("send", "합성고 학생B 생명클리닉")] = TimeoutError("synthetic partial timeout")
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="partial-send-key-1")
        result = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(result, {"requestId": preview["requestId"], "status": "manual_check", "sentCount": 1})
        self.assertEqual([room for room, _ in self.bridge.sent], ["합성고 학생A 생명클리닉", "합성고 학생B 생명클리닉"])
        with self.assertRaises(SettlementRequestError):
            self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(len(self.bridge.sent), 2)

    def test_recipient_recheck_failure_after_partial_send_requires_manual_check(self):
        items = []
        for index, name in enumerate(("학생A", "학생B"), 1):
            items.append({"id": 400 + index, "schoolId": 1, "schoolName": "합성고", "roundLabel": f"{index}회",
                "startTime": f"2026-09-0{index + 1}T09:00:00+09:00", "endTime": f"2026-09-0{index + 1}T10:00:00+09:00",
                "progressStage": "grade1_winter", "parentFreeForThreePlus": False, "amount": 30000,
                "targets": [{"studentName": name}]})
        make_snapshot(self.path, items=items)
        room_b = "합성고 학생B 생명클리닉"
        self.bridge.failures[room_b] = [
            {"opened": True, "room": room_b, "searchEvidence": "unique_exact"},
            {"opened": True, "room": room_b, "searchEvidence": "ambiguous"},
        ]
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="mid-send-room-change-01")
        result = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(result, {"requestId": preview["requestId"], "status": "manual_check", "sentCount": 1})
        self.assertEqual([room for room, _ in self.bridge.sent], ["합성고 학생A 생명클리닉"])
        with self.assertRaises(SettlementRequestError) as denied:
            self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(denied.exception.code, "manual_check_only")
        self.assertEqual(len(self.bridge.sent), 1)

    def test_ambiguous_room_never_sends(self):
        self.bridge.failures["합성고 가상학생 생명클리닉"] = {"opened": False, "searchEvidence": "ambiguous"}
        with self.assertRaises(SettlementRequestError) as error:
            self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0002")
        self.assertEqual(error.exception.code, "recipient_unverified")
        self.assertEqual(self.bridge.sent, [])

    def test_explicit_precommit_failure_is_retryable_through_http_with_same_plan(self):
        class ResultSequenceBridge(FakeBridge):
            def __init__(self):
                super().__init__()
                self.results = [
                    {"error": "synthetic precommit failure", "committed": False, "uncertain": False},
                    {"sent": True},
                ]

            def send_text(self, room, text):
                self.sent.append((room, text))
                return self.results.pop(0)

        self.bridge = ResultSequenceBridge()
        self.service = SettlementRequests(self.path, self.bridge)
        app = FastAPI()
        app.include_router(build_router(self.service, lambda: OWNER), prefix="/api/personal")
        client = TestClient(app)
        preview_response = client.post(
            "/api/personal/aura/settlement-requests/preview",
            json={"year": 2026, "month": 9, "idempotencyKey": "precommit-retry-key-001"},
        )
        self.assertEqual(preview_response.status_code, 200)
        first_preview = preview_response.json()
        first_confirm = client.post(
            f"/api/personal/aura/settlement-requests/{first_preview['requestId']}/confirm",
            json={"planDigest": first_preview["planDigest"]},
        )
        self.assertEqual(first_confirm.status_code, 200)
        self.assertEqual(first_confirm.json()["status"], "retryable")
        self.assertTrue(first_confirm.json()["retryable"])

        with closing(sqlite3.connect(self.path)) as conn:
            request_state = conn.execute(
                "SELECT status FROM aura_settlement_request_outbox WHERE id=?",
                (first_preview["requestId"],),
            ).fetchone()[0]
            receipt_state = conn.execute(
                "SELECT state FROM aura_settlement_message_receipts WHERE request_id=?",
                (first_preview["requestId"],),
            ).fetchone()[0]
        self.assertEqual((request_state, receipt_state), ("retryable", "retryable"))

        retry_preview = client.post(
            "/api/personal/aura/settlement-requests/preview",
            json={"year": 2026, "month": 9, "idempotencyKey": "precommit-retry-key-002"},
        )
        self.assertEqual(retry_preview.status_code, 200)
        second_preview = retry_preview.json()
        self.assertEqual(second_preview["requestId"], first_preview["requestId"])
        self.assertEqual(second_preview["planDigest"], first_preview["planDigest"])
        self.assertEqual(second_preview["status"], "retryable")
        second_confirm = client.post(
            f"/api/personal/aura/settlement-requests/{second_preview['requestId']}/confirm",
            json={"planDigest": second_preview["planDigest"]},
        )
        self.assertEqual(second_confirm.status_code, 200)
        self.assertEqual(second_confirm.json()["status"], "succeeded")
        self.assertEqual(len(self.bridge.sent), 2)

    def _prepare_synthetic_recovery(self, *, log_minutes_after=3, logged_room_key=None):
        from datetime import datetime, timedelta, timezone
        import hashlib
        from personal_project.settlement_precommit_recovery import recover

        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="recovery-key-000001")
        row, payload, _ = self.service._snapshot(OWNER, 7)
        messages, _ = self.service._messages(payload, "김지후")
        message = messages[0]
        invoice_digest = self.service._digest({
            "owner": OWNER, "year": row["year"], "month": row["month"],
            "studentKey": message["studentKey"], "room": message["room"],
            "textDigest": self.service._digest(message["text"]), "amount": message["parentCharge"],
        })
        self.assertEqual(self.service._claim_invoice(OWNER, preview["requestId"], invoice_digest), "claimed")
        self.service._finish_invoice(OWNER, invoice_digest, "manual_check")
        self.service._set_status(preview["requestId"], "manual_check", 0)
        with closing(sqlite3.connect(self.path)) as conn:
            created_at = conn.execute(
                "SELECT created_at FROM aura_settlement_request_outbox WHERE id=?", (preview["requestId"],)
            ).fetchone()[0]
        created = datetime.fromisoformat(created_at.replace(" ", "T")).replace(tzinfo=timezone.utc)
        log_time = created + timedelta(minutes=log_minutes_after)
        actual_room_key = hashlib.sha256(message["room"].encode()).hexdigest()[:16]
        logged_room_key = logged_room_key or actual_room_key
        operation_id = "a" * 32
        log_path = Path(self.temp.name) / "synthetic.log"
        log_path.write_text(
            f"kakao_ui at_utc={log_time.isoformat()} operation={operation_id} room_key={logged_room_key} "
            "command=send outcome=error error_code=bridge_error elapsed_ms=12 uncertain=False detail=<redacted>\n"
        )
        bridge_source = Path(self.temp.name) / "synthetic_bridge.swift"
        bridge_source.write_text(
            "var committed=false\ncommitted=true // A posted mouse click\n"
            '"committed":committed,"uncertain":committed\n'
        )
        return recover, {
            "db_path": self.path, "log_path": log_path, "bridge_source": bridge_source,
            "invoice_digest": invoice_digest, "receipt_request_id": preview["requestId"],
            "retry_request_id": preview["requestId"], "operation_id": operation_id,
            "room_key": logged_room_key,
        }

    def test_recovery_is_room_bound_audited_idempotent_and_db_only(self):
        recover, args = self._prepare_synthetic_recovery()
        first = recover(**args)
        self.assertEqual(first["status"], "recovered")
        second = recover(**args)
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual((second["requestStatus"], second["receiptState"]), ("retryable", "retryable"))
        self.assertEqual(self.bridge.sent, [])
        with closing(sqlite3.connect(self.path)) as conn:
            states = conn.execute(
                "SELECT o.status,r.state FROM aura_settlement_request_outbox o "
                "JOIN aura_settlement_message_receipts r ON r.request_id=o.id WHERE o.id=?",
                (args["retry_request_id"],),
            ).fetchone()
            audit_count = conn.execute("SELECT count(*) FROM aura_settlement_recovery_audit").fetchone()[0]
        self.assertEqual(tuple(states), ("retryable", "retryable"))
        self.assertEqual(audit_count, 1)

    def test_recovery_rejects_room_mismatch_and_old_operation_log(self):
        recover, args = self._prepare_synthetic_recovery(logged_room_key="f" * 16)
        with self.assertRaisesRegex(Exception, "room_key_not_linked_to_invoice"):
            recover(**args)
        self.assertEqual(self.bridge.sent, [])

        self.tearDown()
        self.setUp()
        recover, args = self._prepare_synthetic_recovery(log_minutes_after=11)
        with self.assertRaisesRegex(Exception, "operation_outside_request_window"):
            recover(**args)
        self.assertEqual(self.bridge.sent, [])

    def test_nonretryable_bridge_result_stays_manual_check(self):
        class UnknownBridge(FakeBridge):
            def send_text(self, room, text):
                self.sent.append((room, text))
                return {"error": "synthetic uncertain", "committed": False, "uncertain": True}

        bridge = UnknownBridge()
        service = SettlementRequests(self.path, bridge)
        preview = service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="unknown-result-key-01")
        result = service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(result["status"], "manual_check")
        with self.assertRaises(SettlementRequestError) as denied:
            service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(denied.exception.code, "manual_check_only")
        self.assertEqual(len(bridge.sent), 1)

    def test_send_uncertainty_is_manual_check_only_and_duplicate_confirm_never_retries(self):
        for error in (TimeoutError("synthetic timeout"), RuntimeError("synthetic unknown")):
            with self.subTest(error=type(error).__name__):
                self.tearDown()
                self.setUp()
                self.bridge.failures["send"] = error
                preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0003")
                result = self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
                self.assertEqual(result["status"], "manual_check")
                with self.assertRaises(SettlementRequestError) as denied:
                    self.service.confirm(owner_id=OWNER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
                self.assertEqual(denied.exception.code, "manual_check_only")
                self.assertEqual(len(self.bridge.sent), 1)

    def test_outbox_has_no_names_or_message_and_owner_scope_is_enforced(self):
        preview = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0004")
        with closing(sqlite3.connect(self.path)) as conn:
            serialized = repr(conn.execute("SELECT * FROM aura_settlement_request_outbox").fetchall())
        for forbidden in ("가상학생", "합성고", "합자학생", "입금해주셔야"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(SettlementRequestError) as foreign:
            self.service.confirm(owner_id=OTHER, request_id=preview["requestId"], plan_digest=preview["planDigest"])
        self.assertEqual(foreign.exception.code, "request_not_found")
        self.assertEqual(self.bridge.sent, [])

    def test_idempotency_and_immutable_snapshot_binding(self):
        first = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0005")
        second = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="request-key-0005")
        self.assertEqual(second["requestId"], first["requestId"])
        self.assertEqual(second["planDigest"], first["planDigest"])
        third = self.service.create(owner_id=OWNER, snapshot_id=7, idempotency_key="different-request-key-0005")
        self.assertEqual(third["requestId"], first["requestId"])
        self.assertEqual(len(self.bridge.searches), 3)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE aura_settlement_snapshots SET data_json=? WHERE id=7", (json.dumps({"year": 2026, "month": 9, "items": []}),))
            conn.commit()
        with self.assertRaises(SettlementRequestError) as changed:
            self.service.confirm(owner_id=OWNER, request_id=first["requestId"], plan_digest=first["planDigest"])
        self.assertEqual(changed.exception.code, "snapshot_changed")
        self.assertEqual(self.bridge.sent, [])


if __name__ == "__main__":
    unittest.main()
