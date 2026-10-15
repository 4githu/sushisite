from __future__ import annotations

import json
import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Protocol
from uuid import uuid4

from .config import EVC_MAX_AUDIO_BYTES, EVC_MAX_SLIDE_BYTES
from .schema import EventSignals, SegmentContext, SlideInfo, UtterancePosition


ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
    "video/webm",
    "application/octet-stream",
}
ALLOWED_SLIDE_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
ALLOWED_SLIDE_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/octet-stream",
}
LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class UploadLike(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


class InputValidationError(ValueError):
    pass


class PayloadTooLargeError(InputValidationError):
    pass


class UnsupportedMediaTypeError(InputValidationError):
    pass


def normalize_contract_setting(value: str | float | int) -> float:
    mapping = {
        "low": 0.25,
        "낮음": 0.25,
        "middle": 0.50,
        "mid": 0.50,
        "medium": 0.50,
        "중간": 0.50,
        "high": 0.75,
        "높음": 0.75,
    }
    normalized = str(value).strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    try:
        numeric = float(normalized)
    except ValueError as exc:
        raise InputValidationError(f"unsupported audience setting: {value}") from exc
    for allowed in (0.25, 0.50, 0.75):
        if numeric == allowed:
            return allowed
    raise InputValidationError("audience setting must be 0.25, 0.50, or 0.75")


async def write_validated_upload(
    upload: UploadLike,
    destination: Path,
    *,
    max_bytes: int,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
) -> int:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise UnsupportedMediaTypeError(f"unsupported file extension: {suffix or '<none>'}")
    content_type = (upload.content_type or "application/octet-stream").lower()
    if content_type not in allowed_content_types:
        raise UnsupportedMediaTypeError(f"unsupported content type: {content_type}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise PayloadTooLargeError(f"upload exceeds {max_bytes} bytes")
                output.write(chunk)
        if written == 0:
            raise InputValidationError("uploaded file is empty")
        return written
    except Exception:
        destination.unlink(missing_ok=True)
        raise


@asynccontextmanager
async def temporary_audio_file(
    upload: UploadLike,
    *,
    max_bytes: int = EVC_MAX_AUDIO_BYTES,
) -> AsyncIterator[Path]:
    suffix = Path(upload.filename or "audio.wav").suffix.lower() or ".wav"
    descriptor, raw_path = tempfile.mkstemp(prefix="evc_audio_", suffix=suffix)
    import os

    os.close(descriptor)
    Path(raw_path).unlink(missing_ok=True)
    try:
        # mkstemp reserves a unique name. Closing before exclusive creation is safe
        # because write_validated_upload uses the exact non-user-controlled path.
        path = Path(raw_path)
        await write_validated_upload(
            upload,
            path,
            max_bytes=max_bytes,
            allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
            allowed_content_types=ALLOWED_AUDIO_CONTENT_TYPES,
        )
        yield path
    finally:
        Path(raw_path).unlink(missing_ok=True)


async def save_slide_upload(
    upload: UploadLike,
    directory: Path,
    *,
    max_bytes: int = EVC_MAX_SLIDE_BYTES,
) -> Path:
    suffix = Path(upload.filename or "slides.pdf").suffix.lower() or ".pdf"
    path = directory / f"{uuid4()}{suffix}"
    await write_validated_upload(
        upload,
        path,
        max_bytes=max_bytes,
        allowed_extensions=ALLOWED_SLIDE_EXTENSIONS,
        allowed_content_types=ALLOWED_SLIDE_CONTENT_TYPES,
    )
    return path


def extract_slides(path: Path) -> list[SlideInfo]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    return [
        SlideInfo(
            index=0,
            title=path.name,
            text="",
            summary="PPT/PPTX text extraction is not enabled in this prototype.",
        )
    ]


def _extract_pdf(path: Path) -> list[SlideInfo]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to extract PDF slides") from exc

    reader = PdfReader(str(path))
    slides: list[SlideInfo] = []
    for index, page in enumerate(reader.pages):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        slides.append(
            SlideInfo(
                index=index,
                title=text[:50] if text else f"Slide {index + 1}",
                text=text[:2500],
                summary=text[:300],
            )
        )
    return slides


def parse_event_signals(raw: str | None) -> EventSignals:
    if raw is None or not raw.strip():
        return EventSignals()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputValidationError("event_signals must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise InputValidationError("event_signals must be a JSON object")
    return EventSignals.model_validate(parsed)


def normalize_segment_context(
    *,
    slides: list[SlideInfo],
    current_slide_index: int,
    utterance_position: UtterancePosition,
    language: str,
    gaze_delivery_score: float | None,
    slide_reference: bool,
    event_signals: str | None,
    client_time_s: float,
) -> SegmentContext:
    if slides:
        if current_slide_index < 0 or current_slide_index >= len(slides):
            raise InputValidationError("current_slide_index is outside the slide range")
    elif current_slide_index != 0:
        raise InputValidationError("current_slide_index must be 0 when no slides exist")
    if not LANGUAGE_PATTERN.fullmatch(language):
        raise InputValidationError("language must be a BCP-47 style tag")

    signals = parse_event_signals(event_signals)
    if slide_reference or utterance_position == "slide_transition":
        signals = signals.model_copy(
            update={"slide_reference": max(signals.slide_reference, 1.0)}
        )
    return SegmentContext(
        current_slide_index=current_slide_index,
        utterance_position=utterance_position,
        language=language,
        gaze_delivery_score=gaze_delivery_score,
        slide_reference=slide_reference or utterance_position == "slide_transition",
        event_signals=signals,
        client_time_s=client_time_s,
    )
