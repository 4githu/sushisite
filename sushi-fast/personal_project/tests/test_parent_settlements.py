from contextlib import closing
import json
import sqlite3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project.tests.test_settlement_requests import make_snapshot, FakeBridge, OWNER, OTHER
from personal_project.settlement_requests import SettlementRequests, SettlementRequestError, build_router
from personal_project.parent_settlements import ParentSettlements, build_router as parent_router


def setup_service(tmp_path):
    path = tmp_path / "snapshot.sqlite"
    make_snapshot(path)
    with closing(sqlite3.connect(path)) as db:
        payload = json.loads(db.execute("SELECT data_json FROM aura_settlement_snapshots").fetchone()[0])
    extra = {**payload["items"][0], "id": 104, "schoolId": 2,
             "targets": [{"studentName": "다른학생"}]}
    make_snapshot(path, items=[*payload["items"], extra])
    bridge = FakeBridge()
    service = SettlementRequests(path, bridge)
    return path, service, bridge


def test_individual_preview_and_confirm_bind_only_selected_parent(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    result = service.create_for_month(owner_id=OWNER, year=2026, month=9,
                                      idempotency_key="individual-key", student_key="2:다른학생")
    assert result["messageCount"] == 1
    assert len(bridge.searches) == 1 and "다른학생" in bridge.searches[0]
    service.confirm(owner_id=OWNER, request_id=result["requestId"], plan_digest=result["planDigest"])
    assert len(bridge.sent) == 1 and "다른학생" in bridge.sent[0][0]
    assert not any("가상학생" in room for room, _ in bridge.sent)


def test_unknown_accepted_or_foreign_parent_never_searches(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    for owner, key in [(OWNER, "missing"), (OWNER, "1:합자학생"), (OTHER, "2:다른학생")]:
        with pytest.raises(SettlementRequestError):
            service.create_for_month(owner_id=owner, year=2026, month=9,
                                     idempotency_key="bad-parent-key", student_key=key)
    assert bridge.searches == [] and bridge.sent == []


def test_paid_status_is_separate_reversible_and_flags_changed_amount(tmp_path):
    path, service, bridge = setup_service(tmp_path)
    ledger = ParentSettlements(service)
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE aura_clinic_rounds(id, payment_status, amount)")
        db.execute("INSERT INTO aura_clinic_rounds VALUES(101,'pending',77777)")
        db.commit()
    paid = ledger.update(OWNER, 2026, 9, "1:가상학생", True)
    assert paid["status"] == "paid" and paid["amount"] > 0
    assert ledger.list(OTHER, 2026, 9) == {"items": []}
    with pytest.raises(SettlementRequestError):
        ledger.update(OTHER, 2026, 9, "1:가상학생", True)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT payment_status,amount FROM aura_clinic_rounds").fetchone() == ("pending", 77777)
        raw = db.execute("SELECT data_json FROM aura_settlement_snapshots WHERE user_id=?", (OWNER,)).fetchone()[0]
        data = json.loads(raw)
        data["items"][0]["endTime"] = "2026-09-02T11:00:00+09:00"
        db.execute("UPDATE aura_settlement_snapshots SET data_json=? WHERE user_id=?", (json.dumps(data), OWNER))
        db.commit()
        assert "가상학생" not in repr(db.execute("SELECT * FROM aura_parent_settlement_status").fetchall())
    changed = next(x for x in ledger.list(OWNER, 2026, 9)["items"] if x["studentKey"] == "1:가상학생")
    assert changed["status"] == "needs_review"
    assert ledger.update(OWNER, 2026, 9, "1:가상학생", False)["status"] == "pending"
    assert bridge.searches == [] and bridge.sent == []


def test_http_student_selector_and_paid_json_contract(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    app = FastAPI()
    app.include_router(build_router(service, lambda: OWNER), prefix="/api/personal")
    app.include_router(parent_router(ParentSettlements(service), lambda: OWNER, lambda: OWNER), prefix="/api/personal")
    client = TestClient(app)
    preview = client.post("/api/personal/aura/settlement-requests/preview", json={
        "year": 2026, "month": 9, "idempotencyKey": "http-parent-key", "studentKey": "2:다른학생"})
    assert preview.status_code == 200 and preview.json()["messageCount"] == 1
    paid = client.patch("/api/personal/aura/settlements/parents", json={
        "year": 2026, "month": 9, "studentKey": "2:다른학생", "paid": True})
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    listing = client.get("/api/personal/aura/settlements/parents?year=2026&month=9")
    assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
    assert next(x for x in listing.json()["items"] if x["studentKey"] == "2:다른학생")["status"] == "paid"
    assert bridge.sent == []


def test_manual_delivery_confirmation_is_separate_owner_scoped_and_snapshot_bound(tmp_path):
    path, service, bridge = setup_service(tmp_path)
    ledger = ParentSettlements(service)

    confirmed = ledger.confirm_delivery(OWNER, 2026, 9, "1:가상학생")
    assert confirmed["manualDeliveryConfirmed"] is True
    assert confirmed["manualDeliveryConfirmedAt"]
    assert confirmed["status"] == "pending"
    assert ledger.list(OWNER, 2026, 9)["items"][0]["manualDeliveryConfirmed"] is True
    repeated = ledger.confirm_delivery(OWNER, 2026, 9, "1:가상학생")
    assert repeated["manualDeliveryConfirmedAt"] == confirmed["manualDeliveryConfirmedAt"]

    with pytest.raises(SettlementRequestError) as invalid_target:
        ledger.confirm_delivery(OWNER, 2026, 9, "1:합자학생")
    assert invalid_target.value.code == "recipient_not_billable"
    with pytest.raises(SettlementRequestError):
        ledger.confirm_delivery(OTHER, 2026, 9, "1:가상학생")
    assert ledger.list(OTHER, 2026, 9) == {"items": []}

    # A replacement snapshot for the same month must not inherit an old manual confirmation.
    make_snapshot(path, snapshot_id=8)
    refreshed = ledger.list(OWNER, 2026, 9)["items"][0]
    assert refreshed["manualDeliveryConfirmed"] is False
    assert refreshed["manualDeliveryConfirmedAt"] is None
    assert refreshed["status"] == "pending"
    assert bridge.searches == [] and bridge.sent == []


def test_manual_delivery_confirmation_http_contract_never_marks_paid_or_sends(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    app = FastAPI()
    app.include_router(parent_router(ParentSettlements(service), lambda: OWNER, lambda: OWNER), prefix="/api/personal")
    client = TestClient(app)

    response = client.patch("/api/personal/aura/settlements/parents/delivery", json={
        "year": 2026, "month": 9, "studentKey": "1:가상학생"})
    assert response.status_code == 200, response.text
    assert response.json()["manualDeliveryConfirmed"] is True
    assert response.json()["status"] == "pending"

    listing = client.get("/api/personal/aura/settlements/parents?year=2026&month=9")
    item = next(x for x in listing.json()["items"] if x["studentKey"] == "1:가상학생")
    assert item["manualDeliveryConfirmed"] is True
    assert item["status"] == "pending" and item["paidAmount"] == 0
    assert bridge.searches == [] and bridge.sent == []


def test_parent_message_uses_kst_for_utc_schedule_times(tmp_path):
    path, service, _ = setup_service(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        raw = json.loads(db.execute("SELECT data_json FROM aura_settlement_snapshots").fetchone()[0])
    raw["items"] = [{**raw["items"][0], "startTime": "2026-09-02T09:00:00+00:00", "endTime": "2026-09-02T10:00:00+00:00"}]
    messages, _ = service._messages(raw, "테스트")
    assert "9월 2일 18:00~19:00" in messages[0]["text"]
    assert "9월 2일 09:00" not in messages[0]["text"]


def test_individual_then_bulk_never_sends_same_invoice_twice(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    one = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="first-individual", student_key="2:다른학생")
    service.confirm(owner_id=OWNER, request_id=one["requestId"], plan_digest=one["planDigest"])
    bulk = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="then-bulk-key")
    result = service.confirm(owner_id=OWNER, request_id=bulk["requestId"], plan_digest=bulk["planDigest"])
    assert result["status"] == "succeeded" and result["alreadySentCount"] == 1 and result["sentCount"] == 1
    assert len(bridge.sent) == 2
    assert sum("다른학생" in room for room, _ in bridge.sent) == 1


def test_bulk_then_individual_never_sends_same_invoice_twice(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    bulk = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="first-bulk-key")
    service.confirm(owner_id=OWNER, request_id=bulk["requestId"], plan_digest=bulk["planDigest"])
    one = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="then-individual", student_key="2:다른학생")
    result = service.confirm(owner_id=OWNER, request_id=one["requestId"], plan_digest=one["planDigest"])
    assert result["alreadySentCount"] == 1 and result["sentCount"] == 0 and len(bridge.sent) == 2


def test_uncertain_individual_delivery_cannot_be_retried_through_bulk(tmp_path):
    _, service, bridge = setup_service(tmp_path)
    bridge.failures["send"] = TimeoutError("synthetic unknown outcome")
    one = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="uncertain-single", student_key="2:다른학생")
    assert service.confirm(owner_id=OWNER, request_id=one["requestId"], plan_digest=one["planDigest"])["status"] == "manual_check"
    bridge.failures.clear()
    bulk = service.create_for_month(owner_id=OWNER, year=2026, month=9, idempotency_key="uncertain-bulk-key")
    assert service.confirm(owner_id=OWNER, request_id=bulk["requestId"], plan_digest=bulk["planDigest"])["status"] == "manual_check"
    assert sum("다른학생" in room for room, _ in bridge.sent) == 1
