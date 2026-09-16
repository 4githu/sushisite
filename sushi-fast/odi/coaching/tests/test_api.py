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
    path = tmp_path / "isolated.db"
    db.init_db(db.BASE_DIR / "schema.sql", path)
    original = db.get_conn
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: original(path))
    monkeypatch.setattr(db, "ensure_report_schema", lambda *a, **k: None)
    db.create_user("u", {})
    monkeypatch.setattr(routes, "get_user_id_from_jwt", lambda request: "u")
    calls = []

    async def analyze(*args):
        calls.append(args[0])

    monkeypatch.setattr(routes, "analyze_attempt", analyze)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), calls


def wav(value=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(bytes([value, 0]) * 16000)
    return output.getvalue()


def test_audio_retry_does_not_duplicate_attempt_or_progress(api):
    client, calls = api
    key = str(uuid4())

    def send(data=None):
        return client.post(
            "/coaching/practice/attempts",
            data={"attempt_id": key, "metric_id": "speech_rate", "target_seconds": 60},
            files={"audio": ("a.wav", data or wav(), "audio/wav")},
        )

    assert send().status_code == 200
    assert send().status_code == 200
    assert len(calls) == 1
    assert send(wav(2)).status_code == 409
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE practice_attempts SET state='failed' WHERE attempt_id=?", (key,)
        )
    assert send().status_code == 200
    assert len(calls) == 2
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_attempts").fetchone()[0] == 1
    result = client.get("/coaching/practice").json()
    assert result["progress"]["completed_count"] == 0


def test_invalid_audio_and_unavailable_exercise_do_not_create_attempt(api):
    client, _ = api
    for metric, raw in [("gaze", wav()), ("speech_rate", b"not wav")]:
        res = client.post(
            "/coaching/practice/attempts",
            data={"attempt_id": str(uuid4()), "metric_id": metric},
            files={"audio": ("a.wav", raw)},
        )
        assert res.status_code == 422
    assert client.get("/coaching/practice").json()["attempts"] == []


def test_manual_script_rejects_missing_source_before_ai(api):
    client, _ = api
    result = client.post(
        "/coaching/script/check",
        json={
            "text": "원문 전체",
            "version": 1,
            "sections": [{"slide": 1, "text": "원문"}],
        },
    )
    assert result.status_code == 422
