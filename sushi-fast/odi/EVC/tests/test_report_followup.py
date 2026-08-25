import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.db import odidb
from odi.EVC.report_generation import build_report_insight_payload, generate_report_insight
from odi.EVC.report_schema import AIInsight
from odi.EVC.router import router
from odi.EVC.session_store import session_store
from odi.EVC.tests.test_report_generation import segment


def init_test_db(path: Path) -> None:
    odidb.init_db(schema_path=Path(odidb.__file__).with_name("schema.sql"), db_path=path)


def create_linked_pre_session(path: Path) -> tuple[str, str]:
    odidb.create_user("owner", config={}, db_path=path)
    template_id = odidb.create_template(
        owner_id="owner",
        template={"type": "presentation", "environment": {"title": "test"}},
        db_path=path,
    )
    pre_session = odidb.create_pre_session(template_id, db_path=path)
    return template_id, pre_session["pin_code"]


def test_claim_and_atomic_finish_use_server_bound_owner(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    init_test_db(db_path)
    template_id, pin = create_linked_pre_session(db_path)
    odidb.claim_pre_session(pin, db_path=db_path)

    with pytest.raises(ValueError, match="owner"):
        odidb.finish_linked_pre_session(
            pin_code=pin,
            user_id="attacker",
            template_id=template_id,
            feedback={"version": "presentation-report-v1"},
            db_path=db_path,
        )
    assert odidb.get_pre_session_by_pin(pin, db_path=db_path)["session_id"] is None

    session_id = odidb.finish_linked_pre_session(
        pin_code=pin,
        user_id="owner",
        template_id=template_id,
        feedback={"version": "presentation-report-v1"},
        db_path=db_path,
    )
    saved = odidb.get_pre_session_by_pin(pin, db_path=db_path)
    assert saved["state"] == "finished"
    assert saved["session_id"] == session_id
    assert odidb.finish_linked_pre_session(
        pin_code=pin,
        user_id="owner",
        template_id=template_id,
        feedback={"version": "presentation-report-v1"},
        db_path=db_path,
    ) == session_id


def test_smart_start_binds_pre_session_on_server(monkeypatch) -> None:
    claimed = []
    monkeypatch.setattr(
        odidb,
        "get_pre_session_by_pin",
        lambda pin: {
            "pin_code": pin,
            "template_id": "template-1",
            "session_id": None,
            "state": "waiting",
        },
    )
    monkeypatch.setattr(
        odidb,
        "get_template",
        lambda template_id: {"template_id": template_id, "owner_id": "owner-1", "template": {}},
    )
    monkeypatch.setattr(odidb, "claim_pre_session", lambda pin: claimed.append(pin))
    monkeypatch.setattr(odidb, "release_pre_session_claim", lambda pin: None)

    async def scenario() -> None:
        app = FastAPI()
        app.include_router(router, prefix="/odi")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/odi/xreal_rehear/evc/smart-start",
                data={"presentation_title": "bound", "pre_session_pin": "1234", "seed": "31"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            record = await session_store.get_authorized_session(
                UUID(payload["session_id"]), payload["session_token"]
            )
            assert record.owner_user_id == "owner-1"
            assert record.template_id == "template-1"
            assert record.pre_session_pin == "1234"
            assert claimed == ["1234"]
            await session_store.delete_session(record.session_id, payload["session_token"])

    import asyncio
    asyncio.run(scenario())


def test_report_job_segment_upsert_recovery_and_retention(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    init_test_db(db_path)
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    odidb.upsert_presentation_segment(
        evc_session_id="evc-1",
        step=1,
        segment={"step": 1, "transcript": "first"},
        pre_session_pin="1234",
        expires_at=expired,
        db_path=db_path,
    )
    odidb.upsert_presentation_segment(
        evc_session_id="evc-1",
        step=1,
        segment={"step": 1, "transcript": "updated"},
        pre_session_pin="1234",
        expires_at=expired,
        db_path=db_path,
    )
    assert odidb.list_presentation_segments("evc-1", db_path=db_path) == [
        {"step": 1, "transcript": "updated"}
    ]

    first = odidb.start_report_job(evc_session_id="evc-1", request_id="request-1", db_path=db_path)
    repeated = odidb.start_report_job(evc_session_id="evc-1", request_id="request-1", db_path=db_path)
    assert first["job_id"] == repeated["job_id"]
    assert repeated["attempt_count"] == 1
    with odidb.get_conn(db_path) as conn:
        conn.execute(
            "UPDATE presentation_report_jobs SET started_at = datetime('now', '-20 minutes') WHERE request_id = ?",
            ("request-1",),
        )
    assert odidb.recover_stale_report_jobs(stale_minutes=10, db_path=db_path) == 1
    assert odidb.get_report_job("request-1", db_path=db_path)["status"] == "queued"
    assert odidb.delete_expired_presentation_data(db_path=db_path)["segments"] == 1


def test_deleting_report_session_cascades_source_data(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    init_test_db(db_path)
    template_id, pin = create_linked_pre_session(db_path)
    odidb.claim_pre_session(pin, db_path=db_path)
    odidb.upsert_presentation_segment(
        evc_session_id="evc-delete",
        step=1,
        segment={"step": 1},
        pre_session_pin=pin,
        db_path=db_path,
    )
    odidb.start_report_job(
        evc_session_id="evc-delete", request_id="delete-request", db_path=db_path
    )
    feedback = {
        "version": "presentation-report-v1",
        "generation": {"generator": "test", "generated_at": "2026-01-01T00:00:00Z"},
    }
    session_id = odidb.finish_linked_pre_session(
        pin_code=pin,
        user_id="owner",
        template_id=template_id,
        feedback=feedback,
        evc_session_id="evc-delete",
        report_request_id="delete-request",
        db_path=db_path,
    )
    odidb.delete_session(session_id, user_id="owner", db_path=db_path)
    assert odidb.list_presentation_segments("evc-delete", db_path=db_path) == []
    assert odidb.get_presentation_report("evc-delete", db_path=db_path) is None
    assert odidb.get_report_job("delete-request", db_path=db_path) is None


def test_owner_can_download_and_delete_only_source_data(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    init_test_db(db_path)
    template_id, pin = create_linked_pre_session(db_path)
    odidb.claim_pre_session(pin, db_path=db_path)
    odidb.upsert_presentation_segment(
        evc_session_id="evc-source",
        step=1,
        segment={"step": 1, "transcript": "private"},
        pre_session_pin=pin,
        db_path=db_path,
    )
    session_id = odidb.finish_linked_pre_session(
        pin_code=pin,
        user_id="owner",
        template_id=template_id,
        feedback={"version": "presentation-report-v1"},
        evc_session_id="evc-source",
        db_path=db_path,
    )
    assert odidb.get_presentation_transcript_for_session(session_id, "owner", db_path=db_path)[0][
        "transcript"
    ] == "private"
    with pytest.raises(ValueError):
        odidb.get_presentation_transcript_for_session(session_id, "attacker", db_path=db_path)
    assert odidb.delete_presentation_source_data(session_id, "owner", db_path=db_path) == 1
    assert odidb.get_session(session_id, db_path=db_path) is not None
    assert odidb.get_presentation_report("evc-source", db_path=db_path) is not None


def test_long_report_input_keeps_first_middle_last_and_respects_limits(monkeypatch) -> None:
    monkeypatch.setattr("odi.EVC.report_generation.EVC_REPORT_MAX_EVIDENCE_SEGMENTS", 5)
    monkeypatch.setattr("odi.EVC.report_generation.EVC_REPORT_MAX_INPUT_CHARS", 1000)
    segments = [segment(index, (index % 5 - 2) / 2, float(index)) for index in range(1, 31)]
    for item in segments:
        item.transcript = f"segment-{item.step}-" + ("x" * 500)
    payload = build_report_insight_payload("long", [], segments)
    steps = {item["step"] for item in payload["segments"]}
    assert {1, 16, 30} <= steps
    assert len(payload["segments"]) == 5
    assert sum(len(item["transcript"]) for item in payload["segments"]) <= 1100


def test_report_insight_cache_avoids_duplicate_provider_calls() -> None:
    class Provider:
        model = "cache-test-model"

        def __init__(self):
            self.calls = 0

        def generate(self, payload):
            self.calls += 1
            return AIInsight(title="cached", description="cached description")

    async def scenario() -> None:
        provider = Provider()
        payload = {"presentation_title": "unique-cache-test", "segments": [{"step": 1}]}
        first = await generate_report_insight(payload, provider=provider, retries=0)
        second = await generate_report_insight(payload, provider=provider, retries=0)
        assert first == second
        assert provider.calls == 1

    import asyncio
    asyncio.run(scenario())
