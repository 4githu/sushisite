from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


FORMANT_NAMES = ("F1", "F2", "F3")
REQUIRED_FORMANT_NAMES = ("F1", "F2")


class Envelope(BaseModel):
    freq: list[float] = Field(default_factory=list)
    amp: list[float] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if len(self.freq) != len(self.amp):
            raise ValueError("envelope의 freq와 amp 길이는 같아야 합니다.")
        if not self.freq:
            raise ValueError("envelope는 하나 이상의 좌표를 포함해야 합니다.")
        if any(left >= right for left, right in zip(self.freq, self.freq[1:])):
            raise ValueError("envelope 주파수는 오름차순이어야 합니다.")


class LPCResult(BaseModel):
    formants: dict[str, float]
    envelope: Envelope

    def model_post_init(self, __context) -> None:
        missing = set(REQUIRED_FORMANT_NAMES) - self.formants.keys()
        if missing:
            raise ValueError(
                f"LPC 결과에 필수 포먼트가 부족합니다: {sorted(missing)}"
            )


class GraphPoint(BaseModel):
    frequency_hz: float
    magnitude_db: float


class EvaluationGraph(BaseModel):
    user: list[GraphPoint]
    target: list[GraphPoint]


class EvaluationResult(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    distance: float = Field(ge=0.0)
    feedback: str
    user_formants: dict[str, float]
    target_formants: dict[str, float]
    delta: dict[str, float]
    graph: EvaluationGraph


class PronunciationEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        vowel: str,
        lpc_result: LPCResult,
    ) -> EvaluationResult:
        """추출된 음향 특징을 기준 모델과 비교한다."""


class AcousticFeatureExtractor(ABC):
    @abstractmethod
    def extract(self, audio_path: str) -> LPCResult:
        """오디오를 현재 evaluator가 소비하는 특징으로 변환한다."""


class DistanceMetric(ABC):
    @abstractmethod
    def calculate(self, user: LPCResult, target: LPCResult) -> float:
        """두 특징 사이의 0 이상 거리를 계산한다."""
