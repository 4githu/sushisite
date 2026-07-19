from statistics import pstdev

from ...schemas import AudioMetrics, SpeechWord
from ..rules import DELIVERY_SCORE_RULES
from .alignment import normalize_text


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def calculate_pause_score(metrics: AudioMetrics) -> float:
    rules = DELIVERY_SCORE_RULES
    score = 100.0
    score -= max(
        0.0,
        metrics.silence_ratio - rules.acceptable_silence_ratio,
    ) * rules.silence_penalty_weight
    score -= min(
        rules.maximum_long_pause_penalty,
        metrics.long_pause_count * rules.long_pause_penalty,
    )
    return _clamp_score(score)


def calculate_fluency_score(metrics: AudioMetrics) -> float:
    rules = DELIVERY_SCORE_RULES
    score = 100.0
    score -= min(
        rules.maximum_filler_penalty,
        metrics.filler_count * rules.filler_penalty,
    )

    if metrics.speaking_rate_cpm is not None:
        if metrics.speaking_rate_cpm < rules.minimum_speaking_rate_cpm:
            score -= min(
                rules.maximum_rate_penalty,
                (rules.minimum_speaking_rate_cpm - metrics.speaking_rate_cpm)
                / rules.slow_rate_penalty_divisor,
            )
        elif metrics.speaking_rate_cpm > rules.maximum_speaking_rate_cpm:
            score -= min(
                rules.maximum_rate_penalty,
                (metrics.speaking_rate_cpm - rules.maximum_speaking_rate_cpm)
                / rules.fast_rate_penalty_divisor,
            )

    return _clamp_score(score)


def calculate_timing_score(words: list[SpeechWord]) -> float | None:
    durations: list[float] = []
    for word in words:
        character_count = len(normalize_text(word.word))
        duration = max(0.0, float(word.end) - float(word.start))
        if character_count and duration > 0.0:
            durations.append(duration / character_count)

    if len(durations) < 2:
        return None

    rules = DELIVERY_SCORE_RULES
    target = rules.target_word_char_duration_sec
    outlier_threshold = target * rules.word_char_duration_outlier_ratio
    average_delta = sum(abs(duration - target) for duration in durations) / len(durations)
    outlier_count = sum(
        abs(duration - target) > outlier_threshold for duration in durations
    )
    consistency_penalty = min(15.0, pstdev(durations) / target * 15.0)
    average_penalty = min(
        rules.maximum_timing_penalty,
        average_delta / target * rules.maximum_timing_penalty,
    )
    outlier_penalty = min(10.0, outlier_count * 3.0)
    return _clamp_score(100.0 - average_penalty - consistency_penalty - outlier_penalty)


def calculate_delivery_score_components(
    metrics: AudioMetrics,
    words: list[SpeechWord],
) -> tuple[float | None, float, float, float]:
    timing_score = calculate_timing_score(words)
    pause_score = calculate_pause_score(metrics)
    fluency_score = calculate_fluency_score(metrics)

    rules = DELIVERY_SCORE_RULES
    if timing_score is None:
        delivery_score = round(
            pause_score * 0.5 + fluency_score * 0.5,
            2,
        )
    else:
        delivery_score = round(
            timing_score * rules.timing_score_weight
            + pause_score * rules.pause_score_weight
            + fluency_score * rules.fluency_score_weight,
            2,
        )
    return timing_score, pause_score, fluency_score, delivery_score
