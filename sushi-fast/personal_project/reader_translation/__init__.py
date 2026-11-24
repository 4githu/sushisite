"""Authenticated, non-persistent translation endpoint for Paiper Reader.

Translation is disabled unless ``READER_TRANSLATION_PROVIDER=hermes_plugin`` and
the Hermes executable and isolated configured profile home are explicitly set.
The backend uses a dedicated plugin CLI subprocess; it never calls chat or the
agent loop and does not persist or log request content.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

MAX_REQUEST_BYTES = 256 * 1024
MAX_SEGMENTS = 50
MAX_SEGMENT_CHARS = 5_000
MAX_TOTAL_CHARS = 20_000
MAX_ID_CHARS = 128
MAX_LANGUAGE_CHARS = 64
MAX_HERMES_TIMEOUT_SECONDS = 60
MAX_HERMES_OUTPUT_BYTES = 256 * 1024


def _bad_request(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def _read_request_json(request: Request, *, max_bytes: int = MAX_REQUEST_BYTES) -> Any:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise _bad_request("request_too_large", f"요청 본문은 {max_bytes // 1024}KB 이하여야 합니다.", 413)
        except ValueError as exc:
            raise _bad_request("invalid_content_length", "Content-Length가 올바르지 않습니다.") from exc

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise _bad_request("request_too_large", f"요청 본문은 {max_bytes // 1024}KB 이하여야 합니다.", 413)
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        # Parsing exceptions can include portions of the submitted source text.
        raise _bad_request("invalid_json", "JSON 요청 본문이 올바르지 않습니다.") from None


def _validate_payload(payload: Any) -> tuple[list[dict[str, str]], str]:
    if not isinstance(payload, dict):
        raise _bad_request("invalid_payload", "요청 본문은 JSON 객체여야 합니다.")
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise _bad_request("invalid_segments", "segments는 비어 있지 않은 배열이어야 합니다.")
    if len(segments) > MAX_SEGMENTS:
        raise _bad_request("too_many_segments", "한 번에 최대 50개 구간까지 번역할 수 있습니다.", 413)

    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    total_chars = 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise _bad_request("invalid_segment", "각 구간은 id와 text를 포함해야 합니다.")
        segment_id = segment.get("id")
        text = segment.get("text")
        if not isinstance(segment_id, str) or not segment_id or len(segment_id) > MAX_ID_CHARS:
            raise _bad_request("invalid_segment_id", "구간 id는 1~128자 문자열이어야 합니다.")
        if segment_id in seen_ids:
            raise _bad_request("duplicate_segment_id", "구간 id는 중복될 수 없습니다.")
        seen_ids.add(segment_id)
        if not isinstance(text, str) or not text.strip():
            raise _bad_request("empty_segment_text", "구간 text는 비어 있을 수 없습니다.")
        if len(text) > MAX_SEGMENT_CHARS:
            raise _bad_request("segment_too_large", "각 구간은 최대 5000자까지 허용됩니다.", 413)
        total_chars += len(text)
        if total_chars > MAX_TOTAL_CHARS:
            raise _bad_request("translation_text_too_large", "전체 번역 텍스트는 최대 20000자까지 허용됩니다.", 413)
        normalized.append({"id": segment_id, "text": text})

    language = payload.get("target_language", "English")
    if not isinstance(language, str) or not language.strip() or len(language) > MAX_LANGUAGE_CHARS:
        raise _bad_request("invalid_target_language", "target_language는 1~64자 문자열이어야 합니다.")
    return normalized, language.strip()


def _hermes_settings(*, personal_owner: bool = False) -> tuple[str, str]:
    """Read only explicit non-secret process settings; never inherit them to child."""
    required_provider = "hermes_personal_owner" if personal_owner else "hermes_plugin"
    if os.getenv("READER_TRANSLATION_PROVIDER", "").strip().lower() != required_provider:
        raise _bad_request(
            "translation_provider_unavailable",
            "번역 제공자가 설정되지 않았습니다.",
            503,
        )
    executable = os.getenv("READER_TRANSLATION_HERMES_EXECUTABLE", "").strip()
    profile_home = os.getenv("READER_TRANSLATION_HERMES_HOME", "").strip()
    if (
        not executable
        or not os.path.isabs(executable)
        or not profile_home
        or not os.path.isabs(profile_home)
    ):
        raise _bad_request(
            "translation_provider_unavailable",
            "Hermes 번역 설정을 사용할 수 없습니다.",
            503,
        )
    try:
        executable_path = Path(executable).resolve(strict=True)
        worker_home = Path(profile_home).resolve(strict=True)
    except (OSError, RuntimeError):
        raise _bad_request(
            "translation_provider_unavailable",
            "Hermes 번역 설정을 사용할 수 없습니다.",
            503,
        ) from None
    marker = worker_home / ".paiper-reader-worker"
    active_home = os.getenv("HERMES_HOME", "").strip()
    default_home = (Path.home() / ".hermes").resolve()
    active_conflict = (
        os.path.realpath(active_home) == str(worker_home)
        if active_home
        else worker_home == default_home
    )
    if (
        not executable_path.is_file()
        or not os.access(executable_path, os.X_OK)
        or not worker_home.is_dir()
        or (not personal_owner and (not marker.is_file() or active_conflict))
    ):
        raise _bad_request(
            "translation_provider_unavailable",
            "Hermes 번역은 실행 파일과 격리된 작업 프로필이 설정된 경우에만 사용할 수 있습니다.",
            503,
        )
    return str(executable_path), str(worker_home)


class _OutputLimitExceeded(Exception):
    """Internal sentinel with no provider/process details."""


async def _read_bounded(stream: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(min(4096, limit + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise _OutputLimitExceeded
        chunks.append(chunk)


async def _discard_output(stream: asyncio.StreamReader) -> None:
    """Drain killed-child output without retaining it, so pipe closure cannot hang."""
    while await stream.read(4096):
        pass


async def _write_stdin(process: asyncio.subprocess.Process, payload: bytes) -> None:
    assert process.stdin is not None
    process.stdin.write(payload)
    await process.stdin.drain()
    process.stdin.close()
    await process.stdin.wait_closed()


async def _invoke_hermes_plugin(
    segments: list[dict[str, str]], target_language: str,
    *, personal_settings: tuple[str, str] | None = None,
) -> list[dict[str, str]]:
    executable, profile_home = personal_settings or _hermes_settings()
    payload = json.dumps(
        {"segments": segments, "target_language": target_language},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("request too large")

    stdout = await _run_hermes_command(payload, "paiper-reader-translate", executable, profile_home)
    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        logging.getLogger(__name__).warning("reader_cli_failure kind=malformed_json")
        raise RuntimeError("Hermes plugin returned malformed output") from None
    try:
        return _validate_plugin_response(result, segments)
    except ValueError:
        logging.getLogger(__name__).warning("reader_cli_failure kind=invalid_schema")
        raise


async def _run_hermes_command(payload: bytes, command: str, executable: str, profile_home: str) -> bytes:
    # Deliberately construct a minimal environment. In particular, request text,
    # API keys, OAuth tokens, cookies, and the parent's environment are not copied.
    child_env = {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "HERMES_HOME": profile_home,
        "PATH": os.defpath,
        "PYTHONNOUSERSITE": "1",
    }
    process = await asyncio.create_subprocess_exec(
        executable,
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=child_env,
        cwd=profile_home,
        limit=MAX_HERMES_OUTPUT_BYTES + 1,
    )
    assert process.stdout is not None
    stdout_task = asyncio.create_task(_read_bounded(process.stdout, MAX_HERMES_OUTPUT_BYTES))
    stdin_task = asyncio.create_task(_write_stdin(process, payload))
    wait_task = asyncio.create_task(process.wait())
    try:
        stdout, _stdin_result, _return_code = await asyncio.wait_for(
            asyncio.gather(stdout_task, stdin_task, wait_task),
            timeout=MAX_HERMES_TIMEOUT_SECONDS,
        )
    except BaseException as exc:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await _discard_output(process.stdout)
        await process.wait()
        for task in (stdout_task, stdin_task, wait_task):
            if not task.done():
                task.cancel()
        if isinstance(exc, asyncio.CancelledError):
            raise
        if isinstance(exc, asyncio.TimeoutError):
            kind = "timeout"
        elif isinstance(exc, _OutputLimitExceeded):
            kind = "output_limit"
        else:
            kind = "io_error"
        logging.getLogger(__name__).warning("reader_cli_failure kind=%s", kind)
        raise RuntimeError("Hermes plugin invocation failed") from None

    if process.returncode != 0:
        logging.getLogger(__name__).warning("reader_cli_failure kind=nonzero_exit returncode=%d", process.returncode)
        raise RuntimeError("Hermes plugin invocation failed")
    if not stdout.strip():
        logging.getLogger(__name__).warning("reader_cli_failure kind=empty_output")
        raise RuntimeError("Hermes plugin invocation failed")
    return stdout


def _validate_plugin_response(result: Any, segments: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(result, dict) or set(result) != {"translations"}:
        raise ValueError("invalid plugin response")
    items = result.get("translations")
    if not isinstance(items, list) or len(items) != len(segments):
        raise ValueError("invalid plugin response")
    expected = {segment["id"] for segment in segments}
    by_id: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "text"}:
            raise ValueError("invalid plugin response")
        segment_id, text = item["id"], item["text"]
        if (
            not isinstance(segment_id, str)
            or segment_id not in expected
            or segment_id in by_id
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError("invalid plugin response")
        by_id[segment_id] = text
    if set(by_id) != expected:
        raise ValueError("invalid plugin response")
    return [{"id": segment["id"], "text": by_id[segment["id"]]} for segment in segments]


async def _authorize_reader_request(request: Request, user_id: int) -> tuple[str, str] | None:
    if os.getenv("READER_TRANSLATION_PROVIDER", "").strip().lower() != "hermes_personal_owner":
        _hermes_settings()
        return None
    owner = os.getenv("READER_TRANSLATION_PERSONAL_OWNER_ID", "").strip()
    if not owner.isascii() or not owner.isdecimal() or len(owner) > 20 or int(owner or "0") <= 0 or user_id != int(owner):
        raise _bad_request("translation_provider_unavailable", "번역 제공자를 연결해야 합니다.", 503)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise _bad_request("json_required", "JSON 요청이 필요합니다.", 415)
    origin = request.headers.get("origin")
    allowed_origins = {"https://chobab.app", "https://netaq.chobab.app", "https://aura.chobab.app", "http://localhost:5173", "http://localhost:9000"}
    if origin and origin not in allowed_origins:
        raise _bad_request("translation_origin_forbidden", "허용되지 않은 출처입니다.", 403)
    return _hermes_settings(personal_owner=True)


async def translate_reader_segments(
    request: Request, user_id: int, *, personal_settings: tuple[str, str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    if personal_settings is None and os.getenv("READER_TRANSLATION_PROVIDER", "").strip().lower() == "hermes_personal_owner":
        personal_settings = await _authorize_reader_request(request, user_id)
    payload = await _read_request_json(request)
    segments, target_language = _validate_payload(payload)
    try:
        if personal_settings is None:
            _hermes_settings()
        translations = await _invoke_hermes_plugin(segments, target_language, personal_settings=personal_settings)
    except HTTPException:
        raise
    except Exception:
        # Do not expose or retain provider exception messages: they may include request content.
        raise HTTPException(
            status_code=502,
            detail={"code": "translation_provider_error", "message": "번역 제공자 요청을 처리하지 못했습니다."},
        ) from None
    return {"translations": translations}
