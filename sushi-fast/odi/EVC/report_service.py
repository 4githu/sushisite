from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from uuid import UUID

from odi.db import odidb

from .report_aggregation import aggregate_report
from .report_generation import (
    ReportInsightProvider,
    ReportInsightProviderError,
    build_report_insight_payload,
    generate_report_insight,
)
from .report_schema import (
    ReportFeedback,
    ReportFinishRequest,
    ReportFinishResponse,
    ReportStatusResponse,
    ReportSegmentRecord,
)
from .session_store import SessionStore, session_store
from .observability import record_report_generation


class ReportGenerationError(RuntimeError):
    pass


class ReportGenerationInProgressError(ReportGenerationError):
    pass


class ReportNotGeneratedError(ReportGenerationError):
    pass


class ReportSourceMissingError(ReportGenerationError):
    pass


def _persist_report(record, feedback: dict) -> str | None:
    if record.pre_session_pin:
        if not record.owner_user_id or not record.template_id:
            raise ReportSourceMissingError("linked EVC session is missing ownership metadata")
        return odidb.finish_linked_pre_session(
            pin_code=record.pre_session_pin,
            user_id=record.owner_user_id,
            template_id=record.template_id,
            feedback=feedback,
        )
    return None


async def finish_session_with_report(
    *,
    session_id: UUID,
    token: str,
    payload: ReportFinishRequest,
    provider: ReportInsightProvider | None = None,
    store: SessionStore = session_store,
) -> ReportFinishResponse:
    started_at = time.perf_counter()
    async with store.locked_session(session_id, token) as record:
        cached = record.report_response_cache.get(payload.request_id)
        if cached is not None:
            return cached
        if record.report_generation_status == "ready" and record.report_feedback:
            response = ReportFinishResponse(
                session_id=record.session_id,
                generated_at=record.report_generated_at or record.updated_at,
                persistent_session_id=record.persistent_session_id,
                report=record.report_feedback,
            )
            _cache_response(record, payload.request_id, response)
            return response
        if record.report_generation_status == "generating":
            raise ReportGenerationInProgressError("report is already being generated")
        if not record.report_segments:
            raise ReportSourceMissingError("no analyzed presentation segments are available")

        record.presentation_status = "finishing"
        record.report_generation_status = "generating"
        record.report_generation_request_id = payload.request_id
        record.report_generation_error = None
        title = record.presentation_title
        slides = list(record.slides)
        segments = [item.model_copy(deep=True) for item in record.report_segments]
        persistence_record = record
        if record.pre_session_pin:
            job = odidb.start_report_job(
                evc_session_id=str(record.session_id),
                request_id=str(payload.request_id),
            )
            if job.get("status") == "ready":
                stored = odidb.get_presentation_report(str(record.session_id))
                if stored:
                    report = ReportFeedback.model_validate(stored["feedback"])
                    record.report_feedback = report
                    record.presentation_status = "finished"
                    record.report_generation_status = "ready"
                    record.persistent_session_id = stored.get("odi_session_id")
                    record.report_generated_at = report.generation.generated_at
                    response = ReportFinishResponse(
                        session_id=record.session_id,
                        generated_at=report.generation.generated_at,
                        persistent_session_id=record.persistent_session_id,
                        report=report,
                    )
                    _cache_response(record, payload.request_id, response)
                    return response

    insight = None
    warnings: list[str] = []
    generator = "deterministic-v1"
    if provider is not None or os.getenv("OPENAI_API_KEY"):
        try:
            insight = await generate_report_insight(
                build_report_insight_payload(title, slides, segments),
                provider=provider,
            )
            generator = "deterministic-v1+openai-insight"
        except ReportInsightProviderError:
            warnings.append("ai_insight_fallback")

    try:
        report = aggregate_report(
            segments=segments,
            planned_seconds=payload.planned_seconds,
            qa_seconds=payload.qa_seconds,
            insight=insight,
            generator=generator,
            extra_warnings=warnings,
        )
        feedback_json = report.model_dump(mode="json")
        if persistence_record.pre_session_pin:
            persistent_session_id = odidb.finish_linked_pre_session(
                pin_code=persistence_record.pre_session_pin,
                user_id=persistence_record.owner_user_id,
                template_id=persistence_record.template_id,
                feedback=feedback_json,
                evc_session_id=str(persistence_record.session_id),
                report_request_id=str(payload.request_id),
            )
        else:
            persistent_session_id = _persist_report(persistence_record, feedback_json)
    except Exception as exc:
        if persistence_record.pre_session_pin:
            odidb.fail_report_job(str(payload.request_id), type(exc).__name__)
        async with store.locked_session(session_id, token) as record:
            record.presentation_status = "finished"
            record.report_generation_status = "failed"
            record.report_generation_error = type(exc).__name__
        record_report_generation(
            session_id=str(session_id),
            request_id=str(payload.request_id),
            status="failed",
            latency_ms=(time.perf_counter() - started_at) * 1000,
            segment_count=len(segments),
            word_count=sum(item.speech_metrics.word_count for item in segments),
            generator=generator,
            persistent=bool(persistence_record.pre_session_pin),
            warning_codes=warnings,
            error_code=type(exc).__name__,
        )
        raise

    async with store.locked_session(session_id, token) as record:
        generated_at = report.generation.generated_at
        record.presentation_status = "finished"
        record.report_generation_status = "ready"
        record.report_generation_error = None
        record.report_feedback = report
        record.report_generated_at = generated_at
        record.persistent_session_id = persistent_session_id
        response = ReportFinishResponse(
            session_id=record.session_id,
            generated_at=generated_at,
            persistent_session_id=persistent_session_id,
            report=report,
        )
        _cache_response(record, payload.request_id, response)
        record_report_generation(
            session_id=str(session_id),
            request_id=str(payload.request_id),
            status="ready",
            latency_ms=(time.perf_counter() - started_at) * 1000,
            segment_count=len(segments),
            word_count=report.generation.transcript_word_count,
            generator=report.generation.generator,
            persistent=bool(persistent_session_id),
            warning_codes=report.generation.warnings,
        )
        return response


async def get_session_report_status(
    *, session_id: UUID, token: str, store: SessionStore = session_store
) -> ReportStatusResponse:
    async with store.locked_session(session_id, token) as record:
        return ReportStatusResponse(
            session_id=record.session_id,
            status=record.report_generation_status,
            persistent_session_id=record.persistent_session_id,
            error=record.report_generation_error,
            report=record.report_feedback,
        )


def _cache_response(record, request_id: UUID, response: ReportFinishResponse) -> None:
    record.report_response_cache[request_id] = response
    record.report_response_cache.move_to_end(request_id)
    while len(record.report_response_cache) > 32:
        record.report_response_cache.popitem(last=False)


async def recover_pre_session_report(
    *,
    pin_code: str,
    owner_user_id: str,
    request_id: UUID,
    planned_seconds: int = 0,
    qa_seconds: int = 0,
    provider: ReportInsightProvider | None = None,
) -> ReportFinishResponse:
    pre_session = odidb.get_pre_session_by_pin(pin_code)
    if pre_session is None:
        raise ReportSourceMissingError("pre-session does not exist")
    template_record = odidb.get_template(pre_session["template_id"])
    if template_record is None or str(template_record["owner_id"]) != str(owner_user_id):
        raise PermissionError("pre-session is not owned by the user")
    if pre_session.get("session_id"):
        raise ReportGenerationError("pre-session already has a completed report")
    if pre_session["state"] != "running":
        raise ReportGenerationError("pre-session is not recoverable")
    evc_session_id = odidb.get_evc_session_id_by_pre_session_pin(pin_code)
    if not evc_session_id:
        raise ReportSourceMissingError("persisted presentation segments do not exist")
    segments = [
        ReportSegmentRecord.model_validate(item)
        for item in odidb.list_presentation_segments(evc_session_id)
    ]
    if not segments:
        raise ReportSourceMissingError("persisted presentation segments do not exist")
    environment = (template_record.get("template") or {}).get("environment") or {}
    title = str(environment.get("title") or "발표")
    odidb.start_report_job(evc_session_id=evc_session_id, request_id=str(request_id))
    insight = None
    warnings = ["recovered_from_persistent_segments"]
    generator = "deterministic-v1-recovery"
    if provider is not None or os.getenv("OPENAI_API_KEY"):
        try:
            insight = await generate_report_insight(
                build_report_insight_payload(title, [], segments), provider=provider
            )
            generator += "+openai-insight"
        except ReportInsightProviderError:
            warnings.append("ai_insight_fallback")
    try:
        report = aggregate_report(
            segments=segments,
            planned_seconds=planned_seconds,
            qa_seconds=qa_seconds,
            insight=insight,
            generator=generator,
            extra_warnings=warnings,
        )
        persistent_session_id = odidb.finish_linked_pre_session(
            pin_code=pin_code,
            user_id=owner_user_id,
            template_id=pre_session["template_id"],
            feedback=report.model_dump(mode="json"),
            evc_session_id=evc_session_id,
            report_request_id=str(request_id),
        )
    except Exception as exc:
        odidb.fail_report_job(str(request_id), type(exc).__name__)
        raise
    return ReportFinishResponse(
        session_id=UUID(evc_session_id),
        generated_at=report.generation.generated_at,
        persistent_session_id=persistent_session_id,
        report=report,
    )
