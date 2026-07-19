from dataclasses import dataclass

from .services.pronunciation.base import (
    AcousticFeatureExtractor,
    EvaluationResult,
    LPCResult,
    PronunciationEvaluator,
)
from .services.pronunciation.factory import create_pronunciation_pipeline


@dataclass(frozen=True)
class WordAnalysis:
    lpc: LPCResult
    evaluation: EvaluationResult


class WordPronunciationService:
    """글자 음성의 특징 추출과 평가 호출 순서만 담당한다."""

    def __init__(
        self,
        feature_extractor: AcousticFeatureExtractor,
        evaluator: PronunciationEvaluator,
    ):
        self.feature_extractor = feature_extractor
        self.evaluator = evaluator

    def analyze(self, audio_path: str, vowel: str) -> WordAnalysis:
        acoustic_features = self.feature_extractor.extract(audio_path)
        evaluation = self.evaluator.evaluate(vowel, acoustic_features)
        return WordAnalysis(
            lpc=acoustic_features,
            evaluation=evaluation,
        )


def create_word_pronunciation_service() -> WordPronunciationService:
    feature_extractor, evaluator = create_pronunciation_pipeline()
    return WordPronunciationService(
        feature_extractor=feature_extractor,
        evaluator=evaluator,
    )
