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
    PresentationFinishedError,
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
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    QuestionListResponse,
    UtterancePosition,
)
from .session_store import (
    InvalidSessionTokenError,
    SessionCapacityError,
    SessionNotFoundError,
    session_store,
)
from .speech2text import STTProviderError
from .question_generation import QuestionGenerationProviderError
from .question_service import (
    QuestionGenerationInProgressError,
    QuestionsNotGeneratedError,
    TranscriptTooShortError,
    generate_session_questions,
    list_session_questions,
)
from .report_schema import ReportFinishRequest, ReportFinishResponse, ReportStatusResponse
from .report_service import (
    ReportGenerationInProgressError,
    ReportNotGeneratedError,
    ReportSourceMissingError,
    finish_session_with_report,
    get_session_report_status,
)
from odi.db import odidb


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
    pre_session_pin: str | None = Form(None),
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
        owner_user_id = None
        template_id = None
        normalized_pin = pre_session_pin.strip() if pre_session_pin else None
        if normalized_pin:
            if len(normalized_pin) != 4 or not normalized_pin.isdigit():
                raise HTTPException(422, detail={"code": "invalid_pre_session_pin", "message": "pre-session PIN must contain four digits"})
            pre_session = odidb.get_pre_session_by_pin(normalized_pin)
            if pre_session is None:
                raise HTTPException(404, detail={"code": "pre_session_not_found", "message": "pre-session does not exist"})
            if pre_session["state"] != "waiting" or pre_session.get("session_id"):
                raise HTTPException(409, detail={"code": "pre_session_unavailable", "message": "pre-session is not available"})
            template_record = odidb.get_template(pre_session["template_id"])
            if template_record is None:
                raise HTTPException(404, detail={"code": "template_not_found", "message": "pre-session template does not exist"})
            owner_user_id = str(template_record["owner_id"])
            template_id = str(pre_session["template_id"])
            try:
                odidb.claim_pre_session(normalized_pin)
            except ValueError as exc:
                raise HTTPException(409, detail={"code": "pre_session_unavailable", "message": str(exc)}) from exc
        try:
            return await create_pipeline_session(
                options,
                slides=slides,
                slide_file_path=str(stored_slide) if stored_slide is not None else None,
                owner_user_id=owner_user_id,
                template_id=template_id,
                pre_session_pin=normalized_pin,
            )
        except Exception:
            if normalized_pin:
                odidb.release_pre_session_claim(normalized_pin)
            raise
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


@router.post(
    "/sessions/{session_id}/questions/generate",
    response_model=QuestionGenerationResponse,
)
async def generate_questions_for_session(
    session_id: UUID,
    payload: QuestionGenerationRequest,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        return await generate_session_questions(
            session_id=session_id,
            token=_required_token(x_evc_session_token),
            request_id=payload.request_id,
            question_count=payload.question_count,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/sessions/{session_id}/questions",
    response_model=QuestionListResponse,
)
async def get_questions_for_session(
    session_id: UUID,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        return await list_session_questions(
            session_id=session_id,
            token=_required_token(x_evc_session_token),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/finish",
    response_model=ReportFinishResponse,
)
async def finish_presentation_session(
    session_id: UUID,
    payload: ReportFinishRequest,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        return await finish_session_with_report(
            session_id=session_id,
            token=_required_token(x_evc_session_token),
            payload=payload,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get(
    "/sessions/{session_id}/report",
    response_model=ReportStatusResponse,
)
async def get_presentation_report(
    session_id: UUID,
    x_evc_session_token: str | None = Header(None, alias="X-EVC-Session-Token"),
):
    try:
        return await get_session_report_status(
            session_id=session_id,
            token=_required_token(x_evc_session_token),
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
    if isinstance(exc, PresentationFinishedError):
        return HTTPException(409, detail={"code": "presentation_finished", "message": str(exc)})
    if isinstance(exc, QuestionGenerationInProgressError):
        return HTTPException(409, detail={"code": "questions_generating", "message": str(exc)})
    if isinstance(exc, QuestionsNotGeneratedError):
        return HTTPException(404, detail={"code": "questions_not_generated", "message": str(exc)})
    if isinstance(exc, TranscriptTooShortError):
        return HTTPException(422, detail={"code": "transcript_too_short", "message": str(exc)})
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
    if isinstance(exc, QuestionGenerationProviderError):
        return HTTPException(
            502,
            detail={
                "code": "question_generation_provider_error",
                "message": "Question generation provider failed",
            },
        )
    if isinstance(exc, ReportGenerationInProgressError):
        return HTTPException(409, detail={"code": "report_generating", "message": str(exc)})
    if isinstance(exc, ReportNotGeneratedError):
        return HTTPException(404, detail={"code": "report_not_generated", "message": str(exc)})
    if isinstance(exc, ReportSourceMissingError):
        return HTTPException(422, detail={"code": "report_source_missing", "message": str(exc)})
    if isinstance(exc, (InputValidationError, ValidationError, ValueError)):
        return HTTPException(422, detail={"code": "validation_error", "message": str(exc)})
    return HTTPException(
        500,
        detail={"code": "internal_pipeline_error", "message": "EVC pipeline failed"},
    )
