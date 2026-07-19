import os

import numpy as np

from ...schemas import SpeechTextResult, SpeechWord
from ..audio import decode_audio
from .base import STTService


def _duration_to_seconds(value) -> float:
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    seconds = getattr(value, "seconds", 0)
    nanos = getattr(value, "nanos", 0)
    return float(seconds) + float(nanos) / 1_000_000_000.0


def google_speech_to_text_detail(
    file_path: str,
    language: str = "ko-KR",
    model: str | None = None,
) -> SpeechTextResult:
    try:
        from google.cloud import speech_v1p1beta1 as speech
    except ImportError as error:
        raise RuntimeError(
            "Google STT 검증을 사용하려면 google-cloud-speech 패키지가 필요합니다."
        ) from error

    try:
        signal, sample_rate = decode_audio(file_path)
        pcm16 = np.clip(signal, -1.0, 1.0)
        content = (pcm16 * 32767.0).astype("<i2").tobytes()

        client = speech.SpeechClient()
        config_kwargs = {
            "encoding": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "sample_rate_hertz": sample_rate,
            "language_code": language,
            "enable_word_time_offsets": True,
            "enable_word_confidence": True,
        }
        if model:
            config_kwargs["model"] = model

        response = client.recognize(
            config=speech.RecognitionConfig(**config_kwargs),
            audio=speech.RecognitionAudio(content=content),
        )

        transcript_parts: list[str] = []
        words: list[SpeechWord] = []
        for result in response.results:
            if not result.alternatives:
                continue
            alternative = result.alternatives[0]
            transcript_parts.append(alternative.transcript.strip())
            for word in alternative.words:
                words.append(
                    SpeechWord(
                        word=word.word,
                        start=_duration_to_seconds(word.start_time),
                        end=_duration_to_seconds(word.end_time),
                        confidence=float(getattr(word, "confidence", 0.0) or 0.0),
                    )
                )

        return SpeechTextResult(
            transcript=" ".join(part for part in transcript_parts if part),
            words=words,
        )

    except Exception as error:
        raise RuntimeError(f"Google STT 처리 실패: {error}") from error


class GoogleSTT(STTService):
    def __init__(self, model: str | None = None, language: str = "ko-KR"):
        self.model = model
        self.language = language

    def transcribe(self, audio_path: str) -> SpeechTextResult:
        return google_speech_to_text_detail(
            audio_path,
            language=self.language,
            model=self.model,
        )


def create_google_verification_stt() -> GoogleSTT:
    return GoogleSTT(
        model=os.getenv("GOOGLE_STT_MODEL") or None,
        language=os.getenv("GOOGLE_STT_LANGUAGE_CODE", "ko-KR"),
    )
