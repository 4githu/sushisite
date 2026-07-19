import os
from pathlib import Path

from deepgram import DeepgramClient
from dotenv import load_dotenv

from ...schemas import SpeechTextResult, SpeechWord
from .base import STTService


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


def speech_to_text_detail(
    file_path: str,
    language: str = "ko-KR",
    model: str = "nova-3",
) -> SpeechTextResult:
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY가 설정되어 있지 않습니다.")

    try:
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

        with open(file_path, "rb") as file:
            buffer_data = file.read()

        response = deepgram.listen.v1.media.transcribe_file(
            request=buffer_data,
            model=model,
            language=language,
            filler_words=True,
            utterances=True,
            smart_format=True,
        ).model_dump()

        alternative = response["results"]["channels"][0]["alternatives"][0]
        transcript = alternative.get("transcript", "") or ""
        raw_words = alternative.get("words", []) or []
        words = [
            SpeechWord(
                word=item.get("word", ""),
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", 0.0)),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in raw_words
            if item.get("word")
        ]

        return SpeechTextResult(transcript=transcript, words=words)

    except Exception as error:
        raise RuntimeError(f"STT 처리 실패: {error}") from error


class DeepgramSTT(STTService):
    def __init__(self, model: str = "nova-3", language: str = "ko-KR"):
        self.model = model
        self.language = language

    def transcribe(self, audio_path: str) -> SpeechTextResult:
        return speech_to_text_detail(
            audio_path,
            language=self.language,
            model=self.model,
        )
