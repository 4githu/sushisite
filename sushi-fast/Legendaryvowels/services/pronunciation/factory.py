import os

from .base import AcousticFeatureExtractor, PronunciationEvaluator
from .feature import LPCFeatureExtractor
from .lpc_evaluator import LPCEvaluator


def create_pronunciation_pipeline(
) -> tuple[AcousticFeatureExtractor, PronunciationEvaluator]:
    evaluator_name = os.getenv("PRONUNCIATION_EVALUATOR", "lpc").lower()
    if evaluator_name == "lpc":
        return LPCFeatureExtractor(), LPCEvaluator()
    raise ValueError(
        f"지원하지 않는 pronunciation evaluator입니다: {evaluator_name}"
    )
