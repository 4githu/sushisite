from collections.abc import Callable

from ...schemas import SpeechTextResult
from .base import STTService


class WhisperSTT(STTService):
    """Whisper 구현을 주입하기 위한 어댑터.

    로컬 Whisper, faster-whisper 또는 원격 API 중 하나를 선택한 뒤
    동일한 SpeechTextResult를 반환하는 callable을 주입한다.
    """

    def __init__(
        self,
        transcriber: Callable[[str], SpeechTextResult],
    ):
        self._transcriber = transcriber

    def transcribe(self, audio_path: str) -> SpeechTextResult:
        return self._transcriber(audio_path)
