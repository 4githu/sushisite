import os

from .base import STTService
from .deepgram import DeepgramSTT
from .google import GoogleSTT


def create_stt_service() -> STTService:
    provider = os.getenv("PRONUNCIATION_STT_PROVIDER", "deepgram").lower()
    if provider == "deepgram":
        return DeepgramSTT(
            model=os.getenv("DEEPGRAM_PRIMARY_MODEL", "nova-3")
        )
    if provider == "google":
        return GoogleSTT(
            model=os.getenv("GOOGLE_STT_MODEL") or None,
            language=os.getenv("GOOGLE_STT_LANGUAGE_CODE", "ko-KR"),
        )
    raise ValueError(f"지원하지 않는 STT provider입니다: {provider}")
