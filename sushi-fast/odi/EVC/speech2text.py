from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Protocol

from .config import DEEPGRAM_PRIMARY_MODEL, EVC_PROVIDER_RETRIES, EVC_STT_TIMEOUT_S
from .schema import SpeechTextResult, SpeechWord


class STTProviderError(RuntimeError):
    pass


class SpeechToTextProvider(Protocol):
    def transcribe(self, file_path: str | Path, language: str) -> SpeechTextResult: ...


class DeepgramSpeechToTextProvider:
    def __init__(self, api_key: str | None = None, model: str = DEEPGRAM_PRIMARY_MODEL) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.model = model

    def transcribe(self, file_path: str | Path, language: str) -> SpeechTextResult:
        if not self.api_key:
            raise STTProviderError("DEEPGRAM_API_KEY is not configured")
        try:
            from deepgram import DeepgramClient
        except ImportError as exc:
            raise STTProviderError("deepgram-sdk is not installed") from exc

        try:
            deepgram = DeepgramClient(api_key=self.api_key)
            buffer_data = Path(file_path).read_bytes()
            response = deepgram.listen.v1.media.transcribe_file(
                request=buffer_data,
                model=self.model,
                language=language,
                filler_words=True,
                utterances=True,
                smart_format=True,
            )
            raw = response.model_dump() if hasattr(response, "model_dump") else response
            return normalize_deepgram_response(raw)
        except STTProviderError:
            raise
        except Exception as exc:
            raise STTProviderError(f"Deepgram transcription failed: {exc}") from exc


def normalize_deepgram_response(response: dict[str, Any]) -> SpeechTextResult:
    try:
        alternative = response["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise STTProviderError("Deepgram response has no transcription alternative") from exc

    transcript = str(alternative.get("transcript", "") or "")
    words: list[SpeechWord] = []
    for item in alternative.get("words", []) or []:
        if not isinstance(item, dict) or not item.get("word"):
            continue
        words.append(
            SpeechWord(
                word=str(item["word"]),
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", 0.0)),
                confidence=float(item.get("confidence", 0.0)),
            )
        )
    return SpeechTextResult(transcript=transcript, words=words)


async def transcribe_audio(
    file_path: str | Path,
    language: str = "ko-KR",
    *,
    provider: SpeechToTextProvider | None = None,
    timeout_s: int = EVC_STT_TIMEOUT_S,
    retries: int = EVC_PROVIDER_RETRIES,
) -> SpeechTextResult:
    selected = provider or DeepgramSpeechToTextProvider()
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(selected.transcribe, file_path, language),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            last_error = STTProviderError(f"STT timed out after {timeout_s} seconds")
            last_error.__cause__ = exc
        except STTProviderError as exc:
            last_error = exc
        if attempt < retries:
            await asyncio.sleep(0)
    assert last_error is not None
    raise last_error


def speech_to_text_detail(file_path: str, language: str = "ko-KR") -> SpeechTextResult:
    """Compatibility entry point used by the legacy synchronous service."""

    return DeepgramSpeechToTextProvider().transcribe(file_path, language)
