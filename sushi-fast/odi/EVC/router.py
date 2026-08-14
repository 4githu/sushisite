from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import ValidationError

from .config import EVC_UPLOAD_DIR
from .evaluation import EvaluationProviderError
from .inputs import (
    InputValidationError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    extract_slides,
    normalize_contract_setting,
    normalize_segment_context,
    save_slide_upload,
    temporary_audio_file,
)
from .pipeline import (
    ClientTimeRegressionError,
    StepConflictError,
    create_pipeline_session,
    read_pipeline_session,
    update_pipeline,
)
from .schema import (
    EVCUpdateResponseV2,
    SessionResponseV2,
    SmartStartOptions,
    SmartStartResponseV2,
    UtterancePosition,
)
from .session_store import (
    InvalidSessionTokenError,
    SessionCapacityError,
    SessionNotFoundError,
    session_store,
)
from .speech2text import STTProviderError


router = APIRouter(
    prefix="/xreal_rehear/evc",
    tags=["xreal-rehear-evc"],
)


@router.post("/smart-start", response_model=SmartStartResponseV2)
async def smart_start(
    presentation_title: str = Form(...),
    topic_interest: str = Form("middle"),
    prior_knowledge: str = Form("middle"),
    slide_file: UploadFile | None = File(None),
    seed: int | None = Form(None),
):
    stored_slide: Path | None = None
    try:
        options = SmartStartOptions(
            presentation_title=presentation_title,
            topic_interest=normalize_contract_setting(topic_interest),
            prior_knowledge=normalize_contract_setting(prior_knowledge),
            seed=seed,
        )
        slides = []
        if slide_file is not None:
            stored_slide = await save_slide_upload(slide_file, EVC_UPLOAD_DIR)
            slides = extract_slides(stored_slide)
        return await create_pipeline_session(
            options,
            slides=slides,
            slide_file_path=str(stored_slide) if stored_slide is not None else None,
        )
    except Exception as exc:
        if stored_slide is not None:
            stored_slide.unlink(missing_ok=True)
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}", response_model=SessionResponseV2)
async def read_session(
    session_id: UUID,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        return await read_pipeline_session(
            session_id,
            _required_token(x_evc_session_token),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        await session_store.delete_session(
            session_id,
            _required_token(x_evc_session_token),
        )
        return None
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/update", response_model=EVCUpdateResponseV2)
async def update_evc(
    session_id: UUID = Form(...),
    request_id: UUID = Form(...),
    expected_step: int = Form(...),
    client_time_s: float = Form(...),
    audio: UploadFile = File(...),
    current_slide_index: int = Form(0),
    utterance_position: UtterancePosition = Form("during_speech"),
    language: str = Form("ko-KR"),
    gaze_delivery_score: float | None = Form(None),
    slide_reference: bool = Form(False),
    event_signals: str | None = Form(None),
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        token = _required_token(x_evc_session_token)
        record = await session_store.get_authorized_session(session_id, token)
        context = normalize_segment_context(
            slides=record.slides,
            current_slide_index=current_slide_index,
            utterance_position=utterance_position,
            language=language,
            gaze_delivery_score=gaze_delivery_score,
            slide_reference=slide_reference,
            event_signals=event_signals,
            client_time_s=client_time_s,
        )
        async with temporary_audio_file(audio) as audio_path:
            return await update_pipeline(
                session_id=session_id,
                token=token,
                request_id=request_id,
                expected_step=expected_step,
                context=context,
                audio_path=audio_path,
            )
    except Exception as exc:
        raise _http_error(exc) from exc


def _required_token(token: str | None) -> str:
    if token is None or not token.strip():
        raise InvalidSessionTokenError("X-EVC-Session-Token is required")
    return token


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, InvalidSessionTokenError):
        return HTTPException(401, detail={"code": "invalid_session_token", "message": str(exc)})
    if isinstance(exc, SessionNotFoundError):
        return HTTPException(404, detail={"code": "session_not_found", "message": str(exc)})
    if isinstance(exc, StepConflictError):
        return HTTPException(409, detail={"code": "step_conflict", "message": str(exc)})
    if isinstance(exc, ClientTimeRegressionError):
        return HTTPException(409, detail={"code": "client_time_regression", "message": str(exc)})
    if isinstance(exc, PayloadTooLargeError):
        return HTTPException(413, detail={"code": "payload_too_large", "message": str(exc)})
    if isinstance(exc, UnsupportedMediaTypeError):
        return HTTPException(415, detail={"code": "unsupported_media_type", "message": str(exc)})
    if isinstance(exc, SessionCapacityError):
        return HTTPException(429, detail={"code": "session_capacity_exceeded", "message": str(exc)})
    if isinstance(exc, STTProviderError):
        return HTTPException(
            502,
            detail={"code": "stt_provider_error", "message": "STT provider failed"},
        )
    if isinstance(exc, EvaluationProviderError):
        return HTTPException(
            502,
            detail={
                "code": "evaluation_provider_error",
                "message": "Evaluation provider failed",
            },
        )
    if isinstance(exc, (InputValidationError, ValidationError, ValueError)):
        return HTTPException(422, detail={"code": "validation_error", "message": str(exc)})
    return HTTPException(
        500,
        detail={"code": "internal_pipeline_error", "message": "EVC pipeline failed"},
    )
