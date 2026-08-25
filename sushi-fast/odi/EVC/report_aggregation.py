from __future__ import annotations

from datetime import datetime, timezone

from .report_schema import (
    AIInsight,
    AudienceAnalysis,
    AudienceEvent,
    AudienceGraphPoint,
    DetailAnalysis,
    HighlightMetric,
    ReportDuration,
    ReportFeedback,
    ReportGenerationMetadata,
    ReportScore,
    ReportScoreCard,
    ReportScoreCardDescriptions,
    ReportScoreCardValues,
    ReportSegmentRecord,
    TimelineItem,
)


CONTENT_KEYS = ("organization", "supporting_material", "central_message", "cer_validity")
DELIVERY_KEYS = ("language_clarity", "vocal_delivery", "gaze_delivery", "slide_speech_alignment")


def _to_score(value: float) -> int:
    return round(max(0.0, min(1.0, (value + 1.0) / 2.0)) * 100)


def _weighted_average(segments: list[ReportSegmentRecord], getter) -> float:
    weighted = 0.0
    total = 0.0
    for segment in segments:
        weight = max(0.1, segment.evaluation.confidence) * max(1, segment.speech_metrics.word_count)
        weighted += float(getter(segment)) * weight
        total += weight
    return weighted / total if total else 0.0


def _grade(score: int) -> str:
    if score >= 90:
        return "매우 우수"
    if score >= 80:
        return "우수"
    if score >= 65:
        return "보통"
    return "개선 필요"


def _description(label: str, score: int) -> str:
    if score >= 80:
        return f"{label}이(가) 발표 전반에서 안정적으로 유지되었습니다."
    if score >= 65:
        return f"{label}은(는) 대체로 양호하지만 일부 구간을 더 명확하게 다듬을 수 있습니다."
    return f"{label}을(를) 우선 개선하면 발표의 전달 효과가 크게 좋아질 수 있습니다."


def _timeline(segments: list[ReportSegmentRecord], limit: int = 8) -> list[TimelineItem]:
    ranked = []
    for segment in segments:
        values = [
            *segment.evaluation.content.model_dump().values(),
            *segment.evaluation.delivery.model_dump().values(),
        ]
        average = sum(values) / len(values)
        severity = abs(average)
        if severity < 0.15:
            continue
        kind = "positive" if average >= 0.35 else "negative" if average <= -0.35 else "warning"
        ranked.append((severity, segment, kind, average))
    selected = sorted(ranked, key=lambda item: (-item[0], item[1].step))[:limit]
    selected.sort(key=lambda item: item[1].client_time_s)
    return [
        TimelineItem(
            time_sec=round(segment.client_time_s),
            title=segment.evaluation.segment_note or ("강점 구간" if average > 0 else "개선 구간"),
            description=segment.evaluation.short_reason,
            type=kind,
            slide=segment.slide_index + 1,
            source_step=segment.step,
        )
        for _, segment, kind, average in selected
    ]


def aggregate_report(
    *,
    segments: list[ReportSegmentRecord],
    planned_seconds: int = 0,
    qa_seconds: int = 0,
    insight: AIInsight | None = None,
    generator: str = "deterministic-v1",
    extra_warnings: list[str] | None = None,
) -> ReportFeedback:
    if not segments:
        raise ValueError("at least one analyzed presentation segment is required")

    content = {
        key: _to_score(_weighted_average(segments, lambda item, key=key: getattr(item.evaluation.content, key)))
        for key in CONTENT_KEYS
    }
    delivery = {
        key: _to_score(_weighted_average(segments, lambda item, key=key: getattr(item.evaluation.delivery, key)))
        for key in DELIVERY_KEYS
    }
    engagement = _to_score(_weighted_average(segments, lambda item: item.evc_state.E))
    clarity = round((content["organization"] + content["central_message"] + delivery["language_clarity"] + delivery["slide_speech_alignment"]) / 4)
    credibility = round((content["supporting_material"] + content["cer_validity"] + _to_score(_weighted_average(segments, lambda item: item.evc_state.V))) / 3)
    overall = round((engagement + clarity + credibility) / 3)
    actual_seconds = round(max(item.client_time_s for item in segments))

    all_metrics = {**content, **delivery}
    highlights = sorted(all_metrics.items(), key=lambda item: (-item[1], item[0]))[:4]
    timeline = _timeline(segments)
    graph = [
        AudienceGraphPoint(
            time_sec=round(item.client_time_s),
            E=round(item.evc_state.E, 4),
            V=round(item.evc_state.V, 4),
            C=round(item.evc_state.C, 4),
        )
        for item in segments
    ]
    events = [
        AudienceEvent(
            time_sec=item.time_sec,
            label=item.title,
            type=item.type,
            source_step=item.source_step,
        )
        for item in timeline
    ]
    warnings = list(dict.fromkeys([
        *(extra_warnings or []),
        *(warning for segment in segments for warning in segment.warnings),
        *(missing for segment in segments for missing in segment.evaluation.missing_inputs),
    ]))
    if insight is None:
        weakest = min(all_metrics.items(), key=lambda item: item[1])
        strongest = max(all_metrics.items(), key=lambda item: item[1])
        insight = AIInsight(
            title=f"가장 강한 요소는 {strongest[0]}, 우선 개선 요소는 {weakest[0]}입니다.",
            description=(
                f"전체 {len(segments)}개 발표 구간을 종합했습니다. 강점인 {strongest[0]}은 유지하고 "
                f"{weakest[0]}을 중심으로 다음 연습 목표를 설정해 보세요."
            ),
        )

    return ReportFeedback(
        generation=ReportGenerationMetadata(
            generated_at=datetime.now(timezone.utc),
            generator=generator,
            source_segment_count=len(segments),
            transcript_word_count=sum(item.speech_metrics.word_count for item in segments),
            warnings=warnings,
        ),
        score=ReportScore(overall_score=overall, percentile=None, grade=_grade(overall)),
        duration=ReportDuration(
            planned_seconds=planned_seconds,
            actual_seconds=actual_seconds,
            qa_seconds=qa_seconds,
        ),
        score_card=ReportScoreCard(
            scores=ReportScoreCardValues(
                engagement=engagement,
                clarity=clarity,
                credibility=credibility,
            ),
            descriptions=ReportScoreCardDescriptions(
                engagement=_description("청중 몰입", engagement),
                clarity=_description("내용 명료성", clarity),
                credibility=_description("주장의 신뢰성", credibility),
            ),
        ),
        detail_analysis=DetailAnalysis(
            highlight_metrics=[HighlightMetric(name=name, score=score) for name, score in highlights],
            content_analysis=content,
            delivery_analysis=delivery,
        ),
        timeline=timeline,
        audience_analysis=AudienceAnalysis(graph=graph, events=events),
        ai_insight=insight,
    )
