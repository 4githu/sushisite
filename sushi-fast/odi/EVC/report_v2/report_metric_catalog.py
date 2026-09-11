"""Canonical metric catalogue for presentation report detail cards.

The report UI always receives ten detail cards in a stable order:

* Content (5): message clarity, structure/flow, evidence use,
  claim-evidence connection, vocabulary/expression.
* Delivery (5): gaze, speech rate, pronunciation, filler words,
  time management.

Some data sources cannot yet measure a card (currently pronunciation). Those
cards are still emitted with ``score=null`` instead of disappearing, which
keeps the UI layout and JSON contract stable. Display labels and rank badges
are derived from the metric id and score by the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MetricGroup = Literal["content", "delivery"]
MetricAxis = Literal["engagement", "clarity", "credibility"]
MetricRankLabel = Literal["우수", "보통", "개선"]

CONTENT_METRIC_COUNT = 5
DELIVERY_METRIC_COUNT = 5
DETAIL_METRIC_COUNT = CONTENT_METRIC_COUNT + DELIVERY_METRIC_COUNT


def metric_rank_label(score: int | float | None) -> MetricRankLabel | None:
    """Return the only UI rank label allowed for a scored detail metric.

    Thresholds deliberately differ from the broader report grade.  Detail-card
    labels use the three labels present in the Figma design, while the overall
    report grade can retain values such as ``매우 우수`` and ``개선 필요``.
    """

    if score is None:
        return None
    if score >= 80:
        return "우수"
    if score >= 65:
        return "보통"
    return "개선"


@dataclass(frozen=True)
class DetailMetricSpec:
    id: str
    label: str
    group: MetricGroup
    axis: MetricAxis
    coaching: str
    source: str
    unavailable_reason: str | None = None


CONTENT_METRIC_SPECS: tuple[DetailMetricSpec, ...] = (
    DetailMetricSpec(
        id="message_clarity",
        label="메시지 명확성",
        group="content",
        axis="clarity",
        source="content.central_message",
        coaching="슬라이드마다 청중이 기억할 한 문장을 먼저 정해 보세요.",
    ),
    DetailMetricSpec(
        id="structure_flow",
        label="발표 구조와 흐름",
        group="content",
        axis="clarity",
        source="content.organization",
        coaching="결론을 먼저 말한 뒤 근거와 예시를 한 문장씩 연결해 보세요.",
    ),
    DetailMetricSpec(
        id="evidence_use",
        label="근거와 자료 활용",
        group="content",
        axis="credibility",
        source="content.supporting_material",
        coaching="핵심 주장 바로 뒤에 수치·사례·출처를 붙여 보세요.",
    ),
    DetailMetricSpec(
        id="claim_evidence_link",
        label="주장 - 근거 연결성",
        group="content",
        axis="credibility",
        source="content.cer_validity",
        coaching="주장, 근거, 그 근거가 주장을 지지하는 이유를 순서대로 말해 보세요.",
    ),
    DetailMetricSpec(
        id="vocabulary_expression",
        label="어휘 및 표현 적절성",
        group="content",
        axis="clarity",
        source="delivery.language_clarity",
        coaching="긴 문장을 둘로 나누고 전문 용어는 짧게 풀어서 설명해 보세요.",
    ),
)

DELIVERY_METRIC_SPECS: tuple[DetailMetricSpec, ...] = (
    DetailMetricSpec(
        id="gaze",
        label="시선 처리",
        group="delivery",
        axis="engagement",
        source="delivery.gaze_delivery",
        coaching="문장이 끝날 때 화면 대신 청중을 바라보는 습관을 연습해 보세요.",
    ),
    DetailMetricSpec(
        id="speech_rate",
        label="발화 속도",
        group="delivery",
        axis="engagement",
        source="delivery.vocal_delivery",
        coaching="강조할 문장 앞에서 잠시 쉬고 핵심어는 조금 천천히 말해 보세요.",
    ),
    DetailMetricSpec(
        id="pronunciation",
        label="발음 정확도",
        group="delivery",
        axis="clarity",
        source="unavailable",
        coaching="",
        unavailable_reason="현재 STT 결과에는 발음 정확도 평가값이 포함되지 않아 점수를 산정하지 않았습니다.",
    ),
    DetailMetricSpec(
        id="filler_words",
        label="습관어 사용",
        group="delivery",
        axis="clarity",
        source="derived.filler_score",
        coaching="문장 시작 전 짧게 호흡해 불필요한 연결어를 줄여 보세요.",
    ),
    DetailMetricSpec(
        id="time_management",
        label="시간 운영",
        group="delivery",
        axis="engagement",
        source="derived.time_score",
        coaching="도입·본론·마무리의 목표 시간을 정하고 구간별로 맞춰 연습해 보세요.",
    ),
)

DETAIL_METRIC_SPECS = CONTENT_METRIC_SPECS + DELIVERY_METRIC_SPECS
