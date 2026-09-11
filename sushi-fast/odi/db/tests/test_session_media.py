from pathlib import Path

import pytest

from odi.db import odidb


def make_db(path: Path) -> None:
    odidb.init_db(
        schema_path=Path(odidb.__file__).with_name("schema.sql"),
        db_path=path,
    )
    odidb.create_user("owner", config={}, db_path=path)


def test_legacy_media_is_bound_without_losing_unknown_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    make_db(db_path)

    session_id = odidb.create_session_with_snapshot(
        user_id="owner",
        template={},
        feedback={
            "score": {"overall_score": 80},
            "media": {
                "video_url": "/videos/legacy.mp4",
                "title": "기존 영상",
                "poster_url": "/images/poster.webp",
            },
        },
        db_path=db_path,
    )

    feedback = odidb.get_session(session_id, db_path=db_path)["feedback"]
    assert feedback["score"] == {"overall_score": 80}
    assert feedback["media"] == {
        "video_url": "/videos/legacy.mp4",
        "title": "기존 영상",
        "poster_url": "/images/poster.webp",
        "version": "session-media-v1",
        "session_id": session_id,
    }


def test_session_media_update_preserves_report_and_checks_owner(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    make_db(db_path)
    session_id = odidb.create_session_with_snapshot(
        user_id="owner",
        template={},
        feedback={"timeline": [{"time_sec": 3}], "media": {"title": "발표 영상"}},
        db_path=db_path,
    )

    odidb.update_session_media(
        session_id=session_id,
        user_id="owner",
        media={"video_url": "/videos/session.mp4", "source": "upload"},
        db_path=db_path,
    )

    feedback = odidb.get_session(session_id, db_path=db_path)["feedback"]
    assert feedback["timeline"] == [{"time_sec": 3}]
    assert feedback["media"]["title"] == "발표 영상"
    assert feedback["media"]["video_url"] == "/videos/session.mp4"
    assert feedback["media"]["source"] == "upload"
    assert feedback["media"]["session_id"] == session_id

    with pytest.raises(ValueError, match="접근 권한"):
        odidb.update_session_media(
            session_id=session_id,
            user_id="another-user",
            media={"video_url": "/videos/wrong.mp4"},
            db_path=db_path,
        )


def test_feedback_without_media_keeps_legacy_shape(tmp_path: Path) -> None:
    db_path = tmp_path / "odi.db"
    make_db(db_path)
    session_id = odidb.create_session_with_snapshot(
        user_id="owner",
        template={},
        feedback={"score": {"overall_score": 70}},
        db_path=db_path,
    )

    assert odidb.get_session(session_id, db_path=db_path)["feedback"] == {
        "score": {"overall_score": 70}
    }
