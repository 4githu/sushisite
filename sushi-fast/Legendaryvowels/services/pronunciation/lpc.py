import numpy as np

from ...schemas import (
    FormantPoint,
    LPCAnalysis,
    LPCPoint,
)
from ..rules import LPC_RULES


def _invalid_analysis(
    sample_rate: int,
    duration_sec: float,
    comment: str,
) -> LPCAnalysis:
    return LPCAnalysis(
        sample_rate=sample_rate,
        duration_seconds=round(duration_sec, 4),
        lpc_order=LPC_RULES.order,
        valid_signal=False,
        comment=comment,
    )


def _estimate_formants(
    frequencies: np.ndarray,
    magnitudes_db: np.ndarray,
) -> list[FormantPoint]:
    candidate_indexes = np.flatnonzero(
        (magnitudes_db[1:-1] > magnitudes_db[:-2])
        & (magnitudes_db[1:-1] >= magnitudes_db[2:])
    ) + 1
    candidate_indexes = [
        index
        for index in candidate_indexes
        if LPC_RULES.minimum_formant_frequency_hz
        <= frequencies[index]
        <= LPC_RULES.maximum_formant_frequency_hz
    ]
    candidate_indexes.sort(key=lambda index: magnitudes_db[index], reverse=True)

    selected: list[int] = []
    for index in candidate_indexes:
        if all(
            abs(frequencies[index] - frequencies[other])
            >= LPC_RULES.minimum_formant_spacing_hz
            for other in selected
        ):
            selected.append(index)
        if len(selected) == 3:
            break

    selected.sort(key=lambda index: frequencies[index])
    return [
        FormantPoint(
            name=f"F{number}",
            frequency_hz=round(float(frequencies[index]), 2),
            magnitude_db=round(float(magnitudes_db[index]), 3),
        )
        for number, index in enumerate(selected, start=1)
    ]


def calculate_lpc(
    signal: np.ndarray,
    sample_rate: int,
) -> LPCAnalysis:
    """단일 음성 구간을 정규화된 LPC 스펙트럼으로 변환한다."""
    signal = np.asarray(signal, dtype=np.float64)
    duration_sec = signal.size / sample_rate if sample_rate else 0.0
    minimum_samples = max(
        LPC_RULES.order * 2 + 1,
        round(LPC_RULES.minimum_segment_sec * sample_rate),
    )
    if signal.size < minimum_samples:
        return _invalid_analysis(
            sample_rate,
            duration_sec,
            "LPC를 계산하기에는 분석 구간이 너무 짧습니다.",
        )

    signal = signal - np.mean(signal)
    peak = float(np.max(np.abs(signal)))
    if peak < 1e-6:
        return _invalid_analysis(
            sample_rate,
            duration_sec,
            "분석 구간의 음량이 너무 낮습니다.",
        )

    emphasized = np.empty_like(signal)
    emphasized[0] = signal[0]
    emphasized[1:] = (
        signal[1:] - LPC_RULES.pre_emphasis * signal[:-1]
    )
    windowed = emphasized * np.hamming(emphasized.size)
    correlation = np.correlate(windowed, windowed, mode="full")
    center = windowed.size - 1
    autocorrelation = correlation[
        center : center + LPC_RULES.order + 1
    ]
    if autocorrelation[0] <= 1e-12:
        return _invalid_analysis(
            sample_rate,
            duration_sec,
            "안정적인 자기상관 값을 얻지 못했습니다.",
        )

    indexes = np.abs(
        np.subtract.outer(
            np.arange(LPC_RULES.order),
            np.arange(LPC_RULES.order),
        )
    )
    toeplitz = autocorrelation[indexes]
    toeplitz += np.eye(LPC_RULES.order) * (
        autocorrelation[0] * LPC_RULES.regularization_ratio
    )

    try:
        predictor = np.linalg.solve(
            toeplitz,
            -autocorrelation[1 : LPC_RULES.order + 1],
        )
    except np.linalg.LinAlgError:
        return _invalid_analysis(
            sample_rate,
            duration_sec,
            "LPC 연립방정식이 불안정하여 곡선을 계산하지 못했습니다.",
        )

    coefficients = np.concatenate(([1.0], predictor))
    frequencies = np.linspace(
        0.0,
        sample_rate / 2.0,
        LPC_RULES.fft_size // 2 + 1,
    )
    angular = 2.0 * np.pi * frequencies / sample_rate
    powers = np.arange(coefficients.size)
    denominator = np.abs(
        np.exp(-1j * np.outer(angular, powers)) @ coefficients
    )
    prediction_error = max(
        float(autocorrelation[0] + np.dot(predictor, autocorrelation[1:])),
        1e-12,
    )
    magnitudes_db = 20.0 * np.log10(
        np.sqrt(prediction_error) / np.maximum(denominator, 1e-12)
    )
    magnitudes_db -= np.max(magnitudes_db)

    visible = frequencies <= LPC_RULES.maximum_curve_frequency_hz
    frequencies = frequencies[visible]
    magnitudes_db = magnitudes_db[visible]

    return LPCAnalysis(
        sample_rate=sample_rate,
        duration_seconds=round(duration_sec, 4),
        lpc_order=LPC_RULES.order,
        valid_signal=True,
        comment=(
            "단어 시간 구간을 음절 수로 균등 분할한 뒤 중앙 구간에서 "
            "계산한 LPC 곡선입니다. 중앙 구간은 실제 모음 경계가 아닌 근사값입니다."
        ),
        points=[
            LPCPoint(
                frequency_hz=round(float(frequency), 2),
                magnitude_db=round(float(magnitude), 3),
            )
            for frequency, magnitude in zip(frequencies, magnitudes_db)
        ],
        formants=_estimate_formants(frequencies, magnitudes_db),
    )

