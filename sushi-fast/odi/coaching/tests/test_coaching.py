from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import json
import pytest
from odi.coaching.service import (
    ScriptOutput,
    Suggestion,
    SlideBoundary,
    validate_analysis,
    progress,
    delivery_score,
    analyze_attempt,
)
from odi.db import odidb as db


def test_mapping_preserves_original_and_ignores_bad_ranges():
    text = "안녕 👋. 다음 문장입니다."
    result = validate_analysis(
        text,
        ScriptOutput(boundaries=[SlideBoundary(end=6, slide=1)], suggestions=[]),
        2,
    )
    assert "".join(s["text"] for s in result["sections"]) == text
    assert result["sections"][-1]["end"] == len(text)


def test_suggestions_reject_stale_overlapping_and_cross_slide():
    text = "abcdefghi"
    suggestions = [
        Suggestion(category="length", start=0, end=3, original="abc", replacement="AB"),
        Suggestion(category="terms", start=1, end=4, original="bcd", replacement="X"),
        Suggestion(category="rhythm", start=4, end=7, original="efg", replacement="x"),
        Suggestion(category="terms", start=7, end=9, original="WRONG", replacement="x"),
    ]
    result = validate_analysis(
        text,
        ScriptOutput(
            boundaries=[SlideBoundary(end=5, slide=1), SlideBoundary(end=9, slide=2)],
            suggestions=suggestions,
        ),
        2,
    )
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["original"] == "abc"


def row(
    score=80, metric="speech_rate", state="completed", date="2026-09-07T00:00:00+09:00"
):
    return {
        "score": score,
        "metric_id": metric,
        "state": state,
        "completed_at": date,
        "duration_seconds": 60,
    }


def test_performance_levels_week_boundary_and_failures():
    now = datetime(2026, 9, 12, 12, tzinfo=ZoneInfo("Asia/Seoul"))
    rows = [
        row(),
        row(),
        row(),
        row(79),
        row(state="failed"),
        row(date="2026-09-06T23:59:59+09:00"),
    ]
    p = progress(rows, now)
    assert p["metrics"]["speech_rate"]["level"] == 1
    assert p["metrics"]["speech_rate"]["next_progress"] == 1
    assert p["weekly_successes"] == 3
    assert "gaze" not in p["metrics"]
    assert (
        progress([row() for _ in range(19)], now)["metrics"]["speech_rate"]["level"]
        == 5
    )


def test_delivery_scores_use_measurement():
    assert delivery_score("time_management", "연습입니다", 60, 60).score == 100
    assert delivery_score("time_management", "연습입니다", 30, 60).score == 50
    assert delivery_score("filler_words", "음 그 어 그", 60, 60).score == 0


def test_audio_analysis_persists_result_without_audio(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(db.BASE_DIR / "schema.sql", path)
    original = db.get_conn
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: original(path))
    db.create_user("u", {})
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO practice_attempts(attempt_id,user_id,metric_id,duration_seconds,created_at) VALUES('a','u','time_management',60,?)",
            (db.utc_now(),),
        )
    from odi.EVC import azure_speech

    async def transcribe(audio):
        return "오늘의 핵심은 반복 연습입니다."

    monkeypatch.setattr(azure_speech, "transcribe", transcribe)
    asyncio.run(analyze_attempt("a", b"audio-in-memory", "time_management", 60, 60))
    with db.get_conn() as conn:
        r = dict(conn.execute("SELECT * FROM practice_attempts").fetchone())
    assert r["state"] == "completed" and r["score"] == 100
    assert "audio" not in r and "storage_path" not in r
    assert list(tmp_path.iterdir()) == [path]


def test_unavailable_metrics_do_not_count_in_progress():
    p = progress([row(metric="gaze"), row(metric="pronunciation")])
    assert (
        p["completed_count"] == 0
        and p["total_seconds"] == 0
        and p["weekly_successes"] == 0
    )


def test_assessment_keeps_exact_original_sentence_and_rejects_unknown_index():
    from odi.coaching.service import ExerciseAssessment, assessment_feedback

    sentences = ['첫째, 하루에 1번 연습합니다.', '다음으로  녹음을 듣습니다!']
    result = assessment_feedback(
        ExerciseAssessment(score=85, feedback='핵심을 잘 설명했어요.', evidence_index=1),
        sentences,
    )
    assert result.evidence == '다음으로  녹음을 듣습니다!'
    with pytest.raises(ValueError, match='발화 근거'):
        assessment_feedback(
            ExerciseAssessment(score=85, feedback='확인', evidence_index=2), sentences
        )


def test_content_analysis_selects_original_evidence_and_completes(tmp_path, monkeypatch):
    from odi.coaching import service
    from odi.EVC import azure_speech

    path = tmp_path / 'content.db'
    db.init_db(db.BASE_DIR / 'schema.sql', path)
    original = db.get_conn
    monkeypatch.setattr(db, 'get_conn', lambda *a, **k: original(path))
    db.create_user('content-user', {})
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO practice_attempts(attempt_id,user_id,metric_id,duration_seconds,created_at) VALUES('content','content-user','message_clarity',20,?)",
            (db.utc_now(),),
        )

    transcript = '오늘의 핵심은 반복 연습입니다. 하루에 1번 녹음합니다!'
    async def transcribe(audio):
        return transcript
    def structured(model, instruction, payload):
        assert payload['sentences'] == ['오늘의 핵심은 반복 연습입니다.', '하루에 1번 녹음합니다!']
        return model(score=85, feedback='핵심이 명확합니다.', evidence_index=0)
    monkeypatch.setattr(azure_speech, 'transcribe', transcribe)
    monkeypatch.setattr(service, 'structured', structured)
    asyncio.run(analyze_attempt('content', b'audio', 'message_clarity', 20, 60))
    with db.get_conn() as conn:
        result = dict(conn.execute("SELECT * FROM practice_attempts WHERE attempt_id='content'").fetchone())
    assert result['state'] == 'completed'
    assert json.loads(result['feedback'])['evidence'] in transcript
