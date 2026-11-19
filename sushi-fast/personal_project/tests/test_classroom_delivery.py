from datetime import datetime
import pytest
from personal_project import classroom_delivery as delivery


def test_disabled_and_outside_window_never_read_or_send(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(delivery, "read_owner_rounds", lambda *_: pytest.fail("should not read"))
    monkeypatch.setattr(delivery, "_bridge", lambda *_a, **_k: pytest.fail("should not send"))
    assert delivery.run_once()["state"] == "disabled"
    delivery.configure(7, True)
    assert delivery.run_once(datetime(2026, 11, 6, 8, 59, tzinfo=delivery.outbox.KST))["state"] == "outside_window"
    assert delivery.run_once(datetime(2026, 11, 6, 10, tzinfo=delivery.outbox.KST))["state"] == "outside_window"


def test_existing_kakao_operation_blocks_scheduler_before_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "CONFIG_PATH", tmp_path / "settings.json")
    delivery.configure(7, True)
    monkeypatch.setattr(delivery, "read_owner_rounds", lambda *_: pytest.fail("should not read"))
    with delivery.native_kakao._send_lock:
        assert delivery.run_once(datetime(2026, 11, 6, 9, tzinfo=delivery.outbox.KST))["state"] == "transport_busy"


def test_operational_scheduler_uses_owner_scope_and_persistent_daily_deduplication(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(delivery, "_initialized", False)
    delivery.configure(7, True)
    rounds = [{"id": 1, "schoolId": 2, "schoolName": "synthetic", "startTime": "2026-11-07T10:00:00+09:00",
               "endTime": "2026-11-07T11:00:00+09:00", "attendanceStatus": "scheduled", "modality": "in_person",
               "targets": [{"id": 3, "studentName": "synthetic"}]}]
    owners = []
    monkeypatch.setattr(delivery, "read_owner_rounds", lambda owner, now: owners.append(owner) or rounds)
    calls = []
    def bridge(command, **args):
        calls.append(command)
        if command == "status": return {"trusted": True, "running": True, "locked": False}
        return {"opened": True, "room": delivery.outbox.PRIMARY_ROOM, "searchEvidence": "unique_exact"} if command == "search" else {"sent": True}
    monkeypatch.setattr(delivery, "_bridge", bridge)
    now = datetime(2026, 11, 6, 9, tzinfo=delivery.outbox.KST)
    assert delivery.run_once(now)["state"] == "succeeded"
    assert delivery.run_once(now)["state"] == "succeeded"
    assert calls == ["status", "search", "send"]
    assert set(owners) == {7}


def test_locked_mac_waits_before_reserving_and_can_run_after_unlock(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(delivery, "_initialized", False)
    delivery.configure(19, True)
    health = {"trusted": True, "running": True, "locked": True}
    monkeypatch.setattr(delivery, "_bridge", lambda command, **args: health)
    monkeypatch.setattr(delivery, "read_owner_rounds", lambda *_: [])
    now = datetime(2026, 11, 8, 9, tzinfo=delivery.outbox.KST)
    assert delivery.run_once(now)["state"] == "waiting_for_unlock"
    with delivery.repository.connection() as db:
        assert delivery.outbox.status(db, 19, "2026-11-08") is None
    health["locked"] = False
    assert delivery.run_once(now)["state"] == "skipped"


def test_disabled_transport_never_starts_background_scheduler(monkeypatch):
    monkeypatch.setenv("DISABLE_KAKAO_BRIDGE", "1")
    monkeypatch.setattr(delivery.threading, "Thread", lambda *a, **k: pytest.fail("background thread must stay disabled"))
    delivery.start()
    assert delivery._last_state == "disabled_by_environment"


def test_disabled_transport_cannot_reach_real_native_bridge(monkeypatch):
    monkeypatch.setenv("DISABLE_KAKAO_BRIDGE", "1")
    with pytest.raises(RuntimeError, match="disabled"):
        delivery._bridge("status")
