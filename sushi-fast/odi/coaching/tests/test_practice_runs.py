import io
import wave
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odi.coaching import router as routes
from odi.db import odidb as db


@pytest.fixture
def api(tmp_path, monkeypatch):
    path = tmp_path / "practice-runs.db"
    db.init_db(db.BASE_DIR / "schema.sql", path)
    original = db.get_conn
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: original(path))
    monkeypatch.setattr(db, "ensure_report_schema", lambda *a, **k: None)
    db.create_user("u", {})
    db.create_user("other", {})
    actor = {"id": "u"}
    monkeypatch.setattr(routes, "get_user_id_from_jwt", lambda request: actor["id"])

    async def analyze(*args):
        pass

    monkeypatch.setattr(routes, "analyze_attempt", analyze)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), actor


def audio():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    return out.getvalue()


def test_run_links_owned_source_and_staged_attempt_without_changing_legacy(api):
    client, actor = api
    source = db.create_session_with_snapshot("u", {"type": "presentation"}, feedback={"score": {"overall_score": 60}})
    created = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate", "source_session_id": source, "origin": "manual"})
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    key = str(uuid4())
    data = {"attempt_id": key, "metric_id": "speech_rate", "target_seconds": 60, "run_id": run_id, "stage": "baseline"}
    send = lambda payload: client.post("/coaching/practice/attempts", data=payload, files={"audio": ("a.wav", audio(), "audio/wav")})
    assert send(data).status_code == 200
    assert send(data).status_code == 200
    result = client.get(f"/coaching/practice/runs/{run_id}")
    assert result.status_code == 200
    assert result.json()["source_session_id"] == source
    assert result.json()["stages"] == [{"stage": "baseline", "attempt_id": key, "state": "queued", "score": None, "target_seconds": 60, "duration_seconds": 1.0, "completed_at": None}]
    assert send({**data, "stage": "guided_practice"}).status_code == 409
    actor["id"] = "other"
    assert client.get(f"/coaching/practice/runs/{run_id}").status_code == 404
    assert send({**data, "attempt_id": str(uuid4())}).status_code == 404
    assert client.post("/coaching/practice/runs", json={"metric_id": "speech_rate", "source_session_id": source, "origin": "manual"}).status_code == 404
    assert client.get("/coaching/practice").status_code == 200


def test_run_requires_valid_metric_and_stage(api):
    client, _ = api
    assert client.post("/coaching/practice/runs", json={"metric_id": "gaze", "origin": "manual"}).status_code == 422
    source = db.create_session_with_snapshot("u", {"type": "presentation"}, feedback={})
    assert client.post("/coaching/practice/runs", json={"metric_id": "speech_rate", "source_session_id": source, "origin": "report_rule_v1"}).status_code == 422
    result = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate", "origin": "manual"})
    assert result.status_code == 200
    run_id = result.json()["run_id"]
    send = lambda stage: client.post("/coaching/practice/attempts", data={"attempt_id": str(uuid4()), "metric_id": "speech_rate", "run_id": run_id, "stage": stage}, files={"audio": ("a.wav", audio(), "audio/wav")})
    assert send("unknown").status_code == 422
    assert send("independent_retry").status_code == 409
    assert client.get(f"/coaching/practice/runs/{run_id}").json()["stages"] == []


def test_completed_stages_and_explicit_followup_require_same_owner(api):
    client, actor = api
    run_id = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate"}).json()["run_id"]
    with db.get_conn() as conn:
        conn.execute("UPDATE practice_runs SET created_at='2020-01-01T00:00:00Z' WHERE run_id=?", (run_id,))
    for stage in ("baseline", "guided_practice", "independent_retry", "transfer_challenge"):
        key = str(uuid4())
        result = client.post(
            "/coaching/practice/attempts",
            data={"attempt_id": key, "metric_id": "speech_rate", "run_id": run_id, "stage": stage},
            files={"audio": ("a.wav", audio(), "audio/wav")},
        )
        assert result.status_code == 200, result.text
        with db.get_conn() as conn:
            conn.execute("UPDATE practice_attempts SET state='completed',score=60,completed_at='2021-01-01T00:00:00Z' WHERE attempt_id=?", (key,))
    foreign = db.create_session_with_snapshot("other", {"type": "presentation"}, feedback={})
    assert client.post(f"/coaching/practice/runs/{run_id}/followups", json={"session_id": foreign}).status_code == 404
    session = db.create_session_with_snapshot("u", {"type": "presentation"}, feedback={})
    assert client.post(f"/coaching/practice/runs/{run_id}/followups", json={"session_id": session}).status_code == 200
    assert client.post(f"/coaching/practice/runs/{run_id}/followups", json={"session_id": session}).status_code == 200
    result = client.get(f"/coaching/practice/runs/{run_id}").json()
    assert [s["stage"] for s in result["stages"]] == ["baseline", "guided_practice", "independent_retry", "transfer_challenge"]
    assert result["stages"][-1]["completed_at"] == "2021-01-01T00:00:00Z"
    assert result["follow_up_sessions"] == [session]
    actor["id"] = "other"
    assert client.post(f"/coaching/practice/runs/{run_id}/followups", json={"session_id": foreign}).status_code == 404


def test_runs_can_be_discovered_after_refresh_only_by_owner(api):
    client, actor = api
    run_id = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate"}).json()["run_id"]
    result = client.get("/coaching/practice/runs")
    assert result.status_code == 200
    assert [r["run_id"] for r in result.json()["runs"]] == [run_id]
    actor["id"] = "other"
    assert client.get("/coaching/practice/runs").json()["runs"] == []


def test_past_session_cannot_be_followup_even_if_it_is_owned_and_completed(api):
    client, _ = api
    old = db.create_session_with_snapshot("u", {"type": "presentation"}, feedback={})
    run_id = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate"}).json()["run_id"]
    with db.get_conn() as conn:
        for stage in ("baseline", "guided_practice", "independent_retry", "transfer_challenge"):
            key = str(uuid4())
            conn.execute("INSERT INTO practice_attempts(attempt_id,user_id,metric_id,duration_seconds,created_at,state,completed_at) VALUES(?,?,?,?,?,'completed',?)", (key, "u", "speech_rate", 60, "2030-01-01T00:00:00Z", "2030-01-01T00:00:00Z"))
            conn.execute("INSERT INTO practice_run_stages(run_id,stage,attempt_id) VALUES(?,?,?)", (run_id, stage, key))
    assert client.post(f"/coaching/practice/runs/{run_id}/followups", json={"session_id": old}).status_code == 409
    assert client.get(f"/coaching/practice/runs/{run_id}").json()["follow_up_sessions"] == []


def test_equal_or_missing_start_time_cannot_prove_followup(api):
    client, _ = api
    run_id = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate"}).json()["run_id"]
    session = db.create_session_with_snapshot("u", {"type": "presentation"}, feedback={})
    with db.get_conn() as conn:
        run_time = conn.execute("SELECT created_at FROM practice_runs WHERE run_id=?", (run_id,)).fetchone()[0]
        for stage in ("baseline", "guided_practice", "independent_retry", "transfer_challenge"):
            key = str(uuid4())
            conn.execute("INSERT INTO practice_attempts(attempt_id,user_id,metric_id,duration_seconds,created_at,state,completed_at) VALUES(?,?,?,?,?,'completed',?)", (key, "u", "speech_rate", 60, run_time, run_time))
            conn.execute("INSERT INTO practice_run_stages(run_id,stage,attempt_id) VALUES(?,?,?)", (run_id, stage, key))
        conn.execute("UPDATE sessions SET started_at=?,ended_at=? WHERE session_id=?", (run_time, run_time, session))
    url = f"/coaching/practice/runs/{run_id}/followups"
    assert client.post(url, json={"session_id": session}).status_code == 409
    with db.get_conn() as conn:
        conn.execute("UPDATE sessions SET started_at=NULL WHERE session_id=?", (session,))
    assert client.post(url, json={"session_id": session}).status_code == 409


def test_new_recording_can_replace_only_a_failed_stage_without_erasing_history(api):
    client, actor = api
    run_id = client.post("/coaching/practice/runs", json={"metric_id": "speech_rate"}).json()["run_id"]
    first, second = str(uuid4()), str(uuid4())

    def send(key, restart=False):
        return client.post(
            "/coaching/practice/attempts",
            data={"attempt_id": key, "metric_id": "speech_rate", "run_id": run_id,
                  "stage": "baseline", "restart_failed": str(restart).lower()},
            files={"audio": ("new.wav", audio(), "audio/wav")},
        )

    assert send(first).status_code == 200
    assert send(second, True).status_code == 409  # queued is not failed
    with db.get_conn() as conn:
        conn.execute("UPDATE practice_attempts SET state='failed',error='analysis_failed' WHERE attempt_id=?", (first,))
    assert send(second).status_code == 409  # explicit restart required
    actor["id"] = "other"
    assert send(second, True).status_code == 404
    actor["id"] = "u"
    assert send(second, True).status_code == 200
    assert send(second, True).status_code == 200  # idempotent retry
    run = client.get(f"/coaching/practice/runs/{run_id}").json()
    assert run["stages"][0]["attempt_id"] == second
    assert run["failed_stage_attempts"] == [{"stage": "baseline", "attempt_id": first}]
    # A replaced attempt remains historical and may not be replayed as a legacy
    # attempt or as the current stage, even with the original audio and ID.
    legacy_replay = client.post(
        "/coaching/practice/attempts",
        data={"attempt_id": first, "metric_id": "speech_rate"},
        files={"audio": ("old.wav", audio(), "audio/wav")},
    )
    assert legacy_replay.status_code == 409
    assert send(first, True).status_code == 409
    with db.get_conn() as conn:
        assert conn.execute("SELECT state FROM practice_attempts WHERE attempt_id=?", (first,)).fetchone()[0] == "failed"
        assert conn.execute("SELECT COUNT(*) FROM practice_attempts WHERE attempt_id=?", (second,)).fetchone()[0] == 1
