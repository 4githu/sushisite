from dataclasses import dataclass

import numpy as np

from ..audio import decode_audio
from ..rules import (
    LPC_RULES,
    PRONUNCIATION_EVALUATION_RULES,
)
from ...schemas import LPCAnalysis
from .base import (
    AcousticFeatureExtractor,
    Envelope,
    REQUIRED_FORMANT_NAMES,
    LPCResult,
)
from .lpc import calculate_lpc


class FeatureExtractionError(RuntimeError):
    pass


def lpc_analysis_to_result(analysis: LPCAnalysis) -> LPCResult:
    if not analysis.valid_signal:
        raise FeatureExtractionError(analysis.comment)

    formants = {
        point.name: point.frequency_hz for point in analysis.formants
    }
    missing = set(REQUIRED_FORMANT_NAMES) - formants.keys()
    if missing:
        raise FeatureExtractionError(
            f"필수 포먼트 F1/F2를 추출하지 못했습니다: {sorted(missing)}"
        )

    return LPCResult(
        formants=formants,
        envelope=Envelope(
            freq=[point.frequency_hz for point in analysis.points],
            amp=[point.magnitude_db for point in analysis.points],
        ),
    )


class LPCFeatureExtractor(AcousticFeatureExtractor):
    """단일 음절 또는 지속 모음 오디오에서 중앙 안정 구간을 추출한다."""

    def extract(self, audio_path: str) -> LPCResult:
        signal, sample_rate = decode_audio(audio_path)
        signal = self._select_active_center(signal)
        return lpc_analysis_to_result(calculate_lpc(signal, sample_rate))

    @staticmethod
    def _select_active_center(signal: np.ndarray) -> np.ndarray:
        absolute = np.abs(signal)
        peak = float(np.max(absolute)) if absolute.size else 0.0
        if peak < 1e-6:
            return signal

        threshold = max(1e-4, peak * 0.08)
        active = np.flatnonzero(absolute >= threshold)
        if active.size < 2:
            return signal

        active_signal = signal[active[0] : active[-1] + 1]
        keep_ratio = LPC_RULES.center_window_ratio
        margin = round(active_signal.size * (1.0 - keep_ratio) / 2.0)
        if margin <= 0 or margin * 2 >= active_signal.size:
            return active_signal
        return active_signal[margin:-margin]


@dataclass(frozen=True)
class FeatureVector:
    formants: np.ndarray
    envelope: np.ndarray


def build_feature_vector(
    result: LPCResult,
    envelope_frequency_grid: np.ndarray,
) -> FeatureVector:
    rules = PRONUNCIATION_EVALUATION_RULES
    formants = np.array(
        [result.formants[name] for name in sorted(result.formants)],
        dtype=np.float64,
    )
    formant_scales = np.array(
        [
            {
                "F1": rules.f1_scale_hz,
                "F2": rules.f2_scale_hz,
                "F3": rules.f3_scale_hz,
            }[name]
            for name in sorted(result.formants)
        ],
        dtype=np.float64,
    )
    formants = formants / formant_scales
    envelope = np.interp(
        envelope_frequency_grid,
        np.asarray(result.envelope.freq, dtype=np.float64),
        np.asarray(result.envelope.amp, dtype=np.float64),
    ) / rules.envelope_scale_db
    return FeatureVector(formants=formants, envelope=envelope)
