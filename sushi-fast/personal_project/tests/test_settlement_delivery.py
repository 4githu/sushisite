import json
import logging
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_project import router as routes
from personal_project import kakao_bridge, settlement_delivery, native_kakao


def test_production_routes_require_owner_and_trusted_origin(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)
    payload = {"year": 2026, "month": 11, "idempotencyKey": "test-owner-boundary"}
    monkeypatch.setattr(routes.JMT, "check_jwt", lambda *_: {"data": {"id": 91, "email": "other@example.test"}})
    response = client.post("/api/personal/aura/settlement-requests/preview", json=payload,
                           headers={"origin": "https://aura.chobab.app"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "native_kakao_owner_only"
    monkeypatch.setattr(routes.JMT, "check_jwt", lambda *_: {"data": {"id": 91, "email": native_kakao.OWNER_EMAIL}})
    response = client.post("/api/personal/aura/settlement-requests/preview", json=payload,
                           headers={"origin": "https://untrusted.example.test"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "native_kakao_origin_rejected"


def test_host_binding_uses_shared_operation_lock_and_text_only_bridge(monkeypatch):
    captured = {}
    monkeypatch.setattr(settlement_delivery, "SettlementRequests", lambda path, bridge: captured.update(bridge=bridge) or bridge)
    monkeypatch.setattr(settlement_delivery, "build_router", lambda service, dependency: routes.APIRouter())
    monkeypatch.setattr(settlement_delivery, "ParentSettlements", lambda service: None)
    monkeypatch.setattr(settlement_delivery, "build_parent_router", lambda *_: routes.APIRouter())
    settlement_delivery.bind_settlement_router(lambda: 91)
    bridge = captured["bridge"]
    assert bridge.operation_lock is native_kakao._send_lock
    calls = []
    monkeypatch.setattr(kakao_bridge, "invoke", lambda *args, **kwargs: calls.append((args, kwargs)) or {"sent": True})
    bridge.search_exact("synthetic-room")
    bridge.send_text("synthetic-room", "synthetic-message")
    assert calls == [(("search",), {"room": "synthetic-room", "redact_errors": True}),
                     (("send",), {"room": "synthetic-room", "text": "synthetic-message", "files": [], "redact_errors": True})]


def test_settlement_bridge_error_does_not_log_private_text(monkeypatch, caplog):
    monkeypatch.setattr(kakao_bridge.BINARY.__class__, "is_file", lambda _: True)
    result = SimpleNamespace(stdout=json.dumps({"error": "private-student-room"}), returncode=0)
    monkeypatch.setattr(kakao_bridge.subprocess, "run", lambda *_, **__: result)
    with caplog.at_level(logging.ERROR):
        kakao_bridge.invoke("search", room="synthetic-room", redact_errors=True)
    assert "<redacted>" in caplog.text
    assert "private-student-room" not in caplog.text
