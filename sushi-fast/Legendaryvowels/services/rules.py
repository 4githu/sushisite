"""음성 평가 정책 값.

평가 기준을 조정할 때는 서비스 코드 대신 이 파일의 값부터 변경한다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioRules:
    sample_rate: int = 16_000
    frame_length: int = 1024
    hop_length: int = 512
    decode_timeout_sec: int = 30
    minimum_duration_sec: float = 0.4
    minimum_peak_rms: float = 0.003
    silence_rms_floor: float = 0.003
    silence_peak_ratio: float = 0.12
    long_pause_sec: float = 0.7


@dataclass(frozen=True)
class VerificationRules:
    # Verification runs when confidence/similarity is below these values.
    # Lower values mean fewer second-STT calls. Override with env if needed.
    minimum_average_confidence: float = 0.65
    minimum_target_similarity: float = 0.85


@dataclass(frozen=True)
class MismatchRules:
    maximum_text_score: float = 20.0
    minimum_transcript_characters: int = 8
    target_length_multiplier: float = 2.0


@dataclass(frozen=True)
class DeliveryScoreRules:
    # Temporary calibration values. Replace with data-derived values after
    # collecting real Korean presentation recordings.
    acceptable_silence_ratio: float = 0.35
    silence_penalty_weight: float = 80.0
    long_pause_penalty: float = 5.0
    maximum_long_pause_penalty: float = 30.0
    filler_penalty: float = 2.0
    maximum_filler_penalty: float = 20.0
    minimum_speaking_rate_cpm: float = 150.0
    maximum_speaking_rate_cpm: float = 420.0
    slow_rate_penalty_divisor: float = 7.5
    fast_rate_penalty_divisor: float = 10.0
    maximum_rate_penalty: float = 20.0
    target_word_char_duration_sec: float = 0.18
    word_char_duration_outlier_ratio: float = 0.75
    maximum_timing_penalty: float = 25.0
    timing_score_weight: float = 0.35
    pause_score_weight: float = 0.35
    fluency_score_weight: float = 0.30
    presentation_text_weight: float = 0.6
    presentation_delivery_weight: float = 0.4


@dataclass(frozen=True)
class LpcRules:
    order: int = 16
    fft_size: int = 512
    pre_emphasis: float = 0.97
    center_window_ratio: float = 0.6
    minimum_segment_sec: float = 0.03
    regularization_ratio: float = 1e-6
    maximum_curve_frequency_hz: float = 5_000.0
    minimum_formant_frequency_hz: float = 200.0
    maximum_formant_frequency_hz: float = 4_000.0
    minimum_formant_spacing_hz: float = 150.0


@dataclass(frozen=True)
class PronunciationEvaluationRules:
    formant_weight: float = 0.65
    envelope_weight: float = 0.35
    f1_scale_hz: float = 300.0
    f2_scale_hz: float = 600.0
    f3_scale_hz: float = 900.0
    envelope_scale_db: float = 30.0
    envelope_sample_count: int = 128
    score_sensitivity: float = 0.8
    good_score_threshold: float = 85.0


AUDIO_RULES = AudioRules()
VERIFICATION_RULES = VerificationRules()
MISMATCH_RULES = MismatchRules()
DELIVERY_SCORE_RULES = DeliveryScoreRules()
LPC_RULES = LpcRules()
PRONUNCIATION_EVALUATION_RULES = PronunciationEvaluationRules()

FILLER_WORDS = frozenset({"어", "음", "그", "저", "뭐"})
PRACTICE_RESOURCES = {"고": "ko_syllable_go_01"}
