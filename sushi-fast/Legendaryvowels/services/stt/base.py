from abc import ABC, abstractmethod

from ...schemas import SpeechTextResult


class STTService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> SpeechTextResult:
        """음성을 단어 시간 정보가 포함된 전사 결과로 변환한다."""
