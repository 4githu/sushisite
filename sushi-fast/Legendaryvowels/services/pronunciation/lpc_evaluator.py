import json
import math
import os
import re
from pathlib import Path

import numpy as np

from ..rules import PRONUNCIATION_EVALUATION_RULES
from .base import (
    DistanceMetric,
    EvaluationGraph,
    EvaluationResult,
    GraphPoint,
    LPCResult,
    PronunciationEvaluator,
)
from .feedback import FormantFeedbackGenerator


class ReferenceNotFoundError(FileNotFoundError):
    pass


class JsonReferenceRepository:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def load(self, vowel: str) -> LPCResult:
        self._validate_vowel(vowel)
        path = self.directory / f"{vowel}.json"
        if not path.exists():
            raise ReferenceNotFoundError(
                f"정답 LPC를 찾을 수 없습니다: {path}"
            )
        return LPCResult.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, vowel: str, result: LPCResult) -> Path:
        self._validate_vowel(vowel)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{vowel}.json"
        payload = {
            "vowel": vowel,
            **result.model_dump(mode="json"),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _validate_vowel(vowel: str) -> None:
        if not re.fullmatch(r"[0-9A-Za-z가-힣_-]+", vowel or ""):
            raise ValueError(
                "vowel은 영문, 한글, 숫자, 밑줄 또는 하이픈만 사용할 수 있습니다."
            )


class CompositeLPCDistance(DistanceMetric):
    """포먼트 거리와 전체 LPC envelope RMSE를 결합한다."""

    def calculate(self, user: LPCResult, target: LPCResult) -> float:
        rules = PRONUNCIATION_EVALUATION_RULES
        start_frequency = max(
            min(user.envelope.freq),
            min(target.envelope.freq),
        )
        end_frequency = min(
            max(user.envelope.freq),
            max(target.envelope.freq),
        )
        if end_frequency <= start_frequency:
            raise ValueError("사용자와 정답 envelope의 주파수 범위가 겹치지 않습니다.")

        grid = np.linspace(
            start_frequency,
            end_frequency,
            rules.envelope_sample_count,
        )
        common_formants = sorted(set(user.formants) & set(target.formants))
        if common_formants:
            scales = {
                "F1": rules.f1_scale_hz,
                "F2": rules.f2_scale_hz,
                "F3": rules.f3_scale_hz,
            }
            user_formants = np.array(
                [user.formants[name] / scales[name] for name in common_formants],
                dtype=np.float64,
            )
            target_formants = np.array(
                [target.formants[name] / scales[name] for name in common_formants],
                dtype=np.float64,
            )
            formant_distance = float(
                np.sqrt(np.mean(np.square(user_formants - target_formants)))
            )
        else:
            formant_distance = 0.0
        user_envelope = np.interp(
            grid,
            np.asarray(user.envelope.freq, dtype=np.float64),
            np.asarray(user.envelope.amp, dtype=np.float64),
        ) / rules.envelope_scale_db
        target_envelope = np.interp(
            grid,
            np.asarray(target.envelope.freq, dtype=np.float64),
            np.asarray(target.envelope.amp, dtype=np.float64),
        ) / rules.envelope_scale_db
        envelope_distance = float(
            np.sqrt(np.mean(np.square(user_envelope - target_envelope)))
        )
        return (
            rules.formant_weight * formant_distance
            + rules.envelope_weight * envelope_distance
        )


class ExponentialScoreNormalizer:
    def normalize(self, distance: float) -> float:
        sensitivity = PRONUNCIATION_EVALUATION_RULES.score_sensitivity
        return round(100.0 * math.exp(-sensitivity * distance), 2)


class LPCEvaluator(PronunciationEvaluator):
    def __init__(
        self,
        reference_repository: JsonReferenceRepository | None = None,
        distance_metric: DistanceMetric | None = None,
        feedback_generator: FormantFeedbackGenerator | None = None,
        score_normalizer: ExponentialScoreNormalizer | None = None,
    ):
        default_directory = Path(
            os.getenv(
                "PRONUNCIATION_REFERENCE_DIR",
                Path(__file__).resolve().parents[2] / "reference_lpc",
            )
        )
        self.reference_repository = (
            reference_repository or JsonReferenceRepository(default_directory)
        )
        self.distance_metric = distance_metric or CompositeLPCDistance()
        self.feedback_generator = (
            feedback_generator or FormantFeedbackGenerator()
        )
        self.score_normalizer = (
            score_normalizer or ExponentialScoreNormalizer()
        )

    def evaluate(
        self,
        vowel: str,
        lpc_result: LPCResult,
    ) -> EvaluationResult:
        target = self.reference_repository.load(vowel)
        distance = self.distance_metric.calculate(lpc_result, target)
        score = self.score_normalizer.normalize(distance)
        common_formants = sorted(set(lpc_result.formants) & set(target.formants))
        delta = {
            name: round(
                lpc_result.formants[name] - target.formants[name],
                2,
            )
            for name in common_formants
        }

        return EvaluationResult(
            score=score,
            distance=round(distance, 6),
            feedback=self.feedback_generator.generate(score, delta),
            user_formants=lpc_result.formants,
            target_formants=target.formants,
            delta=delta,
            graph=EvaluationGraph(
                user=self._graph_points(lpc_result),
                target=self._graph_points(target),
            ),
        )

    @staticmethod
    def _graph_points(result: LPCResult) -> list[GraphPoint]:
        return [
            GraphPoint(frequency_hz=frequency, magnitude_db=amplitude)
            for frequency, amplitude in zip(
                result.envelope.freq,
                result.envelope.amp,
            )
        ]
