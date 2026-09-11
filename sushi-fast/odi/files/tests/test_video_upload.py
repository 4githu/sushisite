import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from odi.files import service


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_session_video_upload_is_scoped_to_user_and_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(service, "STORAGE_ROOT", tmp_path / "storage" / "odi")

    result = asyncio.run(
        service.save_session_video_upload(
            "user-1",
            "session-1",
            make_upload("demo.mp4", b"video-bytes", "video/mp4"),
        )
    )

    saved_path = tmp_path / result["storage_path"]
    assert saved_path.read_bytes() == b"video-bytes"
    assert "users/user-1/sessions/session-1/media" in result["storage_path"]
    assert result["original_name"] == "demo.mp4"


def test_session_video_upload_rejects_non_video_extension(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(service, "STORAGE_ROOT", tmp_path / "storage" / "odi")

    with pytest.raises(HTTPException, match="형식만 업로드"):
        asyncio.run(
            service.save_session_video_upload(
                "user-1",
                "session-1",
                make_upload("not-video.txt", b"text", "text/plain"),
            )
        )


def test_session_media_path_cannot_escape_its_owner_or_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(service, "STORAGE_ROOT", tmp_path / "storage" / "odi")
    other_path = tmp_path / "storage" / "odi" / "users" / "other" / "sessions" / "s2" / "media" / "video.mp4"

    with pytest.raises(HTTPException, match="현재 세션의 영상 경로"):
        service.session_media_path_from_storage_path(
            "user-1",
            "session-1",
            other_path.relative_to(tmp_path).as_posix(),
        )
