import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.EVC.pipeline import create_pipeline_session
from odi.EVC.report_aggregation import aggregate_report
from odi.EVC.report_metric_catalog import (
    CONTENT_METRIC_COUNT,
    DELIVERY_METRIC_COUNT,
    DETAIL_METRIC_COUNT,
)
from odi.EVC.report_schema import DetailMetricFeedback, ReportFinishRequest, ReportSegmentRecord
from odi.EVC.report_service import ReportSourceMissingError, finish_session_with_report
from odi.EVC.router import router
from odi.EVC.schema import (
    AudienceState,
    ContentScores,
    DeliveryScores,
    MtDtEvaluation,
    SmartStartOptions,
    SpeechMetrics,
)
from odi.EVC.session_store import SessionStore, session_store


def segment(step: int, score: float, time_s: float) -> ReportSegmentRecord:
    return ReportSegmentRecord(
        step=step,
        client_time_s=time_s,
        slide_index=step - 1,
        transcript=f"발표 구간 {step}의 핵심 주장과 근거입니다.",
        evaluation=MtDtEvaluation(
            move="Rationale",
            content=ContentScores(
                organization=score,
                supporting_material=score,
                central_message=score,
                cer_validity=score,
            ),
            delivery=DeliveryScores(
                language_clarity=score,
                vocal_delivery=score,
                gaze_delivery=score,
                slide_speech_alignment=score,
            ),
            segment_note=f"구간 {step}",
            short_reason="주장과 근거가 연결되었습니다.",
            confidence=1.0,
        ),
        speech_metrics=SpeechMetrics(
            duration_s=5.0,
            word_count=10,
            speech_rate_wps=2.0,
            pause_count=0,
            pause_total_s=0.0,
            filler_count=0,
            repeated_word_count=0,
            avg_confidence=0.95,
            vocal_delivery_score=score,
        ),
        evc_state=AudienceState(E=score, V=score, C=score),
    )


def test_report_aggregation_builds_frontend_contract() -> None:
    report = aggregate_report(
        segments=[segment(1, 0.8, 5.0), segment(2, -0.2, 12.0)],
        planned_seconds=60,
    )
    assert report.version == "presentation-report-v2"
    assert report.duration.actual_seconds == 12
    assert report.generation.source_segment_count == 2
    assert report.score.percentile is None
    assert report.audience_analysis.graph[-1].time_sec == 12
    assert all(item.source_step in {1, 2} for item in report.timeline)
    assert [item.evidence_id for item in report.evidence] == ["segment-1", "segment-2"]
    assert all(item.evidence_ids for item in report.timeline)
    assert [item.label for item in report.detail_analysis.content_metrics] == [
        "메시지 명확성",
        "발표 구조와 흐름",
        "근거와 자료 활용",
        "주장 - 근거 연결성",
        "어휘 및 표현 적절성",
    ]
    assert len(report.detail_analysis.delivery_metrics) == 5
    pronunciation = next(
        item for item in report.detail_analysis.delivery_metrics if item.id == "pronunciation"
    )
    assert pronunciation.score is None
    serialized = report.model_dump(mode="json")
    assert set(serialized["detail_analysis"]) == {"content_metrics", "delivery_metrics"}
    assert "label" not in serialized["detail_analysis"]["content_metrics"][0]
    assert "rank_label" not in serialized["detail_analysis"]["content_metrics"][0]
    assert "status" not in serialized["detail_analysis"]["content_metrics"][0]
    assert "average_scores" not in serialized["score_card"]
    assert "previous_session_delta" not in serialized["score"]
    assert report.recommended_trainings


def test_detail_metric_catalog_is_complete_and_display_metadata_is_not_persisted() -> None:
    report = aggregate_report(
        segments=[segment(1, 0.8, 5.0), segment(2, -0.2, 12.0)],
        planned_seconds=60,
    )
    detail_metrics = report.detail_analysis.content_metrics + report.detail_analysis.delivery_metrics

    assert len(report.detail_analysis.content_metrics) == CONTENT_METRIC_COUNT == 5
    assert len(report.detail_analysis.delivery_metrics) == DELIVERY_METRIC_COUNT == 5
    assert len(detail_metrics) == DETAIL_METRIC_COUNT == 10
    assert [metric.id for metric in detail_metrics] == [
        "message_clarity",
        "structure_flow",
        "evidence_use",
        "claim_evidence_link",
        "vocabulary_expression",
        "gaze",
        "speech_rate",
        "pronunciation",
        "filler_words",
        "time_management",
    ]

    stored = DetailMetricFeedback(
        id="message_clarity",
        label="메시지 명확성",
        score=80,
        rank_label="개선",
        status="available",
        reason="핵심 메시지가 명확했습니다.",
    ).model_dump(mode="json")
    assert stored == {
        "id": "message_clarity",
        "score": 80,
        "reason": "핵심 메시지가 명확했습니다.",
        "evidence_ids": [],
        "coaching": None,
    }


def test_report_finish_is_idempotent_and_rejects_empty_source() -> None:
    async def scenario() -> None:
        store = SessionStore()
        started = await create_pipeline_session(
            SmartStartOptions(presentation_title="종합 리포트 테스트", seed=11), store=store
        )
        request = ReportFinishRequest(request_id=uuid4(), planned_seconds=60)
        with pytest.raises(ReportSourceMissingError):
            await finish_session_with_report(
                session_id=started.session_id,
                token=started.session_token,
                payload=request,
                store=store,
            )
        record = await store.get_authorized_session(started.session_id, started.session_token)
        record.report_segments.append(segment(1, 0.5, 8.0))
        first = await finish_session_with_report(
            session_id=started.session_id,
            token=started.session_token,
            payload=request,
            store=store,
        )
        repeated = await finish_session_with_report(
            session_id=started.session_id,
            token=started.session_token,
            payload=request,
            store=store,
        )
        assert repeated == first
        assert record.report_generation_status == "ready"
        assert record.presentation_status == "finished"

    asyncio.run(scenario())


def test_report_finish_and_status_api() -> None:
    async def scenario() -> None:
        started = await create_pipeline_session(
            SmartStartOptions(presentation_title="리포트 API", seed=12), store=session_store
        )
        record = await session_store.get_authorized_session(started.session_id, started.session_token)
        record.report_segments.append(segment(1, 0.4, 9.0))
        app = FastAPI()
        app.include_router(router, prefix="/odi")
        headers = {"X-EVC-Session-Token": started.session_token}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/odi/xreal_rehear/evc/sessions/{started.session_id}/finish",
                headers=headers,
                json={"request_id": str(uuid4()), "planned_seconds": 60},
            )
            assert response.status_code == 200, response.text
            fetched = await client.get(
                f"/odi/xreal_rehear/evc/sessions/{started.session_id}/report", headers=headers
            )
            assert fetched.status_code == 200
            assert fetched.json()["status"] == "ready"
            assert fetched.json()["report"]["score"] == response.json()["report"]["score"]
            injected = await client.post(
                f"/odi/xreal_rehear/evc/sessions/{started.session_id}/finish",
                headers=headers,
                json={"request_id": str(uuid4()), "user_id": "another-user"},
            )
            assert injected.status_code == 422
        await session_store.delete_session(started.session_id, started.session_token)

    asyncio.run(scenario())
