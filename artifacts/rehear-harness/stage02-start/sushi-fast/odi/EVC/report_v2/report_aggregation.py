from __future__ import annotations

from datetime import datetime, timezone

from .report_metric_catalog import CONTENT_METRIC_SPECS, DELIVERY_METRIC_SPECS, DetailMetricSpec
from .report_schema import (
    AIInsight,
    AIInsightItem,
    AudienceAnalysis,
    AudienceEvent,
    AudienceGraphPoint,
    DetailAnalysis,
    DetailMetricFeedback,
    HighlightMetric,
    ReportDuration,
    ReportFeedback,
    ReportEvidence,
    ReportGenerationMetadata,
    ReportScore,
    ReportScoreCard,
    ReportScoreCardDescriptions,
    ReportScoreCardValues,
    ReportReactionRecord,
    ReportReactionTrace,
    ReportSegmentRecord,
    TimelineItem,
    TrainingRecommendation,
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


def _metric_evidence_ids(
    evidence: list[ReportEvidence],
    metric: str,
) -> list[str]:
    if not evidence:
        return []
    selected = max(evidence, key=lambda item: abs(item.metric_impacts.get(metric, 0.0)))
    return [selected.evidence_id]


def _detail_metrics(
    *,
    content: dict[str, int],
    delivery: dict[str, int],
    segments: list[ReportSegmentRecord],
    evidence: list[ReportEvidence],
    planned_seconds: int,
    actual_seconds: int,
) -> tuple[list[DetailMetricFeedback], list[DetailMetricFeedback]]:
    total_words = sum(item.speech_metrics.word_count for item in segments)
    total_fillers = sum(item.speech_metrics.filler_count for item in segments)
    filler_score = (
        round(max(0.0, 100.0 - (total_fillers / total_words) * 500.0))
        if total_words > 0 else None
    )
    time_score = (
        round(max(0.0, 100.0 - abs(actual_seconds - planned_seconds) / planned_seconds * 100.0))
        if planned_seconds > 0 else None
    )

    metric_scores: dict[str, int | None] = {
        "content.central_message": content["central_message"],
        "content.organization": content["organization"],
        "content.supporting_material": content["supporting_material"],
        "content.cer_validity": content["cer_validity"],
        "delivery.language_clarity": delivery["language_clarity"],
        "delivery.gaze_delivery": delivery["gaze_delivery"],
        "delivery.vocal_delivery": delivery["vocal_delivery"],
        "derived.filler_score": filler_score,
        "derived.time_score": time_score,
    }

    def item(spec: DetailMetricSpec) -> DetailMetricFeedback:
        score = metric_scores.get(spec.source)
        available = score is not None
        return DetailMetricFeedback(
            id=spec.id,
            label=spec.label,
            score=score,
            reason=(
                _description(spec.label, score)
                if available
                else spec.unavailable_reason or "현재 세션에서 평가에 필요한 입력이 수집되지 않았습니다."
            ),
            evidence_ids=_metric_evidence_ids(evidence, spec.axis) if available else [],
            coaching=spec.coaching if available else None,
        )

    content_metrics = [item(spec) for spec in CONTENT_METRIC_SPECS]
    delivery_metrics = [item(spec) for spec in DELIVERY_METRIC_SPECS]
    return content_metrics, delivery_metrics


def _training_recommendations(
    metrics: list[DetailMetricFeedback],
) -> list[TrainingRecommendation]:
    available = sorted(
        (item for item in metrics if item.score is not None),
        key=lambda item: (item.score or 0, item.id),
    )
    if not available:
        return []
    templates = {
        "speech_rate": ("발화 속도 안정화 훈련", "발화 속도와 호흡을 조절해 청중의 집중을 안정적으로 유지하는 연습입니다."),
        "gaze": ("시선 분배 훈련", "정면에 집중된 시선을 청중 전체로 자연스럽게 분산하는 연습입니다."),
        "message_clarity": ("핵심 메시지 구조화 훈련", "결론을 먼저 말하고 근거를 짧게 덧붙이는 전달 순서를 연습합니다."),
        "structure_flow": ("발표 흐름 구조화 훈련", "도입과 본론, 결론의 연결 문장을 간결하게 정리하는 연습입니다."),
        "evidence_use": ("근거 연결 훈련", "주장과 사례, 자료를 자연스럽게 연결해 설득력을 높이는 연습입니다."),
        "claim_evidence_link": ("주장-근거 연결 훈련", "주장 뒤에 근거와 해석을 순서대로 붙이는 연습입니다."),
        "vocabulary_expression": ("쉬운 표현 전환 훈련", "긴 문장과 전문 용어를 청중이 이해하기 쉬운 말로 바꾸는 연습입니다."),
        "filler_words": ("습관어 줄이기 훈련", "불필요한 연결어 대신 짧은 쉼을 사용하는 연습입니다."),
        "time_management": ("발표 시간 운영 훈련", "구간별 목표 시간에 맞춰 핵심 내용을 전달하는 연습입니다."),
    }
    recommendations = []
    for index, metric in enumerate(available[:2]):
        title, description = templates.get(
            metric.id,
            (f"{metric.id} 집중 훈련", f"{metric.id}을 다음 발표에서 안정적으로 적용하는 연습입니다."),
        )
        recommendations.append(TrainingRecommendation(
            id=f"training-{metric.id}",
            title=title,
            description=description,
            priority=index == 0,
            evidence_ids=metric.evidence_ids,
        ))
    return recommendations


def _metric_impacts(segment: ReportSegmentRecord) -> dict[str, float]:
    content = segment.evaluation.content
    delivery = segment.evaluation.delivery
    return {
        "engagement": round(segment.delta.common.E if segment.delta else segment.evc_state.E, 4),
        "clarity": round(
            (content.organization + content.central_message + delivery.language_clarity
             + delivery.slide_speech_alignment) / 4,
            4,
        ),
        "credibility": round(
            (content.supporting_material + content.cer_validity
             + (segment.delta.common.V if segment.delta else segment.evc_state.V)) / 3,
            4,
        ),
    }


def build_report_evidence(segments: list[ReportSegmentRecord]) -> list[ReportEvidence]:
    return [
        ReportEvidence(
            evidence_id=f"segment-{segment.step}",
            source_step=segment.step,
            start_sec=round(max(0.0, segment.client_time_s - segment.speech_metrics.duration_s), 3),
            end_sec=round(segment.client_time_s, 3),
            slide=segment.slide_index + 1,
            transcript_excerpt=segment.transcript[:800],
            evaluation_summary=segment.evaluation.short_reason,
            metric_impacts=_metric_impacts(segment),
            confidence=segment.evaluation.confidence,
            missing_inputs=segment.evaluation.missing_inputs,
        )
        for segment in segments
    ]


def build_reaction_trace(
    segments: list[ReportSegmentRecord],
    reactions: list[ReportReactionRecord],
) -> list[ReportReactionTrace]:
    records = reactions
    if not records:
        records = [
            ReportReactionRecord(
                sequence=segment.step,
                client_time_s=segment.client_time_s,
                source_steps=[segment.step],
                audiences=segment.audiences,
                commands=segment.commands,
            )
            for segment in segments
            if segment.commands
        ]
    return [
        ReportReactionTrace(
            reaction_id=f"reaction-{record.sequence}",
            sequence=record.sequence,
            time_sec=record.client_time_s,
            source_steps=record.source_steps,
            evidence_ids=[f"segment-{step}" for step in record.source_steps],
            audiences=record.audiences,
            commands=record.commands,
        )
        for record in records
    ]


def _timeline(
    segments: list[ReportSegmentRecord],
    reaction_trace: list[ReportReactionTrace],
    limit: int = 8,
) -> list[TimelineItem]:
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
            time_sec=round(max(0.0, segment.client_time_s - segment.speech_metrics.duration_s)),
            title=segment.evaluation.segment_note or ("강점 구간" if average > 0 else "개선 구간"),
            description=segment.evaluation.short_reason,
            type=kind,
            slide=segment.slide_index + 1,
            source_step=segment.step,
            end_sec=round(segment.client_time_s),
            evidence_ids=[f"segment-{segment.step}"],
            reaction_ids=[
                reaction.reaction_id
                for reaction in reaction_trace
                if segment.step in reaction.source_steps
            ],
            metric_impacts=_metric_impacts(segment),
        )
        for _, segment, kind, average in selected
    ]


def aggregate_report(
    *,
    segments: list[ReportSegmentRecord],
    planned_seconds: int = 0,
    qa_seconds: int = 0,
    insight: AIInsight | None = None,
    generator: str = "deterministic-v2",
    extra_warnings: list[str] | None = None,
    reactions: list[ReportReactionRecord] | None = None,
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
    evidence = build_report_evidence(segments)
    content_metrics, delivery_metrics = _detail_metrics(
        content=content,
        delivery=delivery,
        segments=segments,
        evidence=evidence,
        planned_seconds=planned_seconds,
        actual_seconds=actual_seconds,
    )
    reaction_trace = build_reaction_trace(segments, reactions or [])
    timeline = _timeline(segments, reaction_trace)
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
            strengths=[AIInsightItem(
                title=f"{strongest[0]}이 안정적이었습니다.",
                description="해당 평가가 가장 높았던 대표 구간을 근거로 선정했습니다.",
                action="같은 구성과 전달 방식을 다음 발표에서도 유지해 보세요.",
                evidence_ids=[max(evidence, key=lambda item: item.metric_impacts.get("clarity", 0)).evidence_id],
            )],
            improvements=[AIInsightItem(
                title=f"{weakest[0]}을 먼저 다듬어 보세요.",
                description="해당 평가가 가장 낮았던 대표 구간을 근거로 선정했습니다.",
                action="근거를 짧게 제시하고 결론과 직접 연결하는 문장으로 다시 연습해 보세요.",
                evidence_ids=[min(evidence, key=lambda item: item.metric_impacts.get("clarity", 0)).evidence_id],
            )],
        )

    return ReportFeedback(
        version="presentation-report-v2",
        generation=ReportGenerationMetadata(
            generated_at=datetime.now(timezone.utc),
            generator=generator,
            source_segment_count=len(segments),
            source_reaction_count=len(reaction_trace),
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
            content_metrics=content_metrics,
            delivery_metrics=delivery_metrics,
        ),
        timeline=timeline,
        audience_analysis=AudienceAnalysis(graph=graph, events=events),
        ai_insight=insight,
        evidence=evidence,
        reaction_trace=reaction_trace,
        recommended_trainings=_training_recommendations(content_metrics + delivery_metrics),
    )
