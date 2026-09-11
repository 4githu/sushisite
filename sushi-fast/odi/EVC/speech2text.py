from __future__ import annotations

import asyncio
import importlib.util
import os
import tempfile
from pathlib import Path
from typing import Any, Literal, Protocol

from .config import DEEPGRAM_PRIMARY_MODEL, EVC_PROVIDER_RETRIES, EVC_STT_TIMEOUT_S
from .schema import SpeechTextResult, SpeechWord


class STTProviderError(RuntimeError):
    pass


class STTProviderConfigurationError(STTProviderError):
    pass


STTProviderName = Literal["deepgram", "azure"]


class SpeechToTextProvider(Protocol):
    def transcribe(self, file_path: str | Path, language: str) -> SpeechTextResult: ...


def _module_is_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError):
        return False


class AzureSpeechToTextProvider:
    def transcribe(self, file_path: str | Path, language: str) -> SpeechTextResult:
        from .azure_continuous_stt import recognize
        from .azure_speech import setting, validate_wav
        try:
            data = Path(file_path).read_bytes()
            validate_wav(data)
            result = recognize(data, setting("AZURE_SPEECH_KEY"), setting("AZURE_SPEECH_REGION"),
                               detailed=True, language=language)
            return SpeechTextResult.model_validate(result)
        except Exception as exc:
            raise STTProviderError("Azure transcription failed") from exc


def normalize_provider_name(value: object | None) -> STTProviderName:
    name = str(value or os.getenv("EVC_STT_PROVIDER", "deepgram")).strip().lower()
    if name not in ("deepgram", "azure"):
        raise STTProviderConfigurationError(f"Unsupported STT provider: {name or 'empty'}")
    return name  # type: ignore[return-value]


def validate_provider_configuration(name: object | None) -> STTProviderName:
    """Validate credentials and SDK availability without sending audio upstream."""

    normalized = normalize_provider_name(name)
    if normalized == "deepgram":
        if not os.getenv("DEEPGRAM_API_KEY", "").strip():
            raise STTProviderConfigurationError("DEEPGRAM_API_KEY is not configured")
        if not _module_is_available("deepgram"):
            raise STTProviderConfigurationError("deepgram-sdk is not installed")
        return normalized

    missing = [
        setting
        for setting in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")
        if not os.getenv(setting, "").strip()
    ]
    if missing:
        raise STTProviderConfigurationError(f"{', '.join(missing)} is not configured")
    if not _module_is_available("azure.cognitiveservices.speech"):
        raise STTProviderConfigurationError("azure-cognitiveservices-speech is not installed")
    return normalized


def provider_for_name(name: object | None) -> SpeechToTextProvider:
    normalized = normalize_provider_name(name)
    if normalized == "azure":
        return AzureSpeechToTextProvider()
    return DeepgramSpeechToTextProvider()


def configured_provider() -> SpeechToTextProvider:
    return provider_for_name(os.getenv("EVC_STT_PROVIDER", "deepgram"))


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
    selected = provider or configured_provider()
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


async def transcribe_wav_bytes(
    audio: bytes,
    language: str = "ko-KR",
    *,
    provider_name: object | None = None,
    provider: SpeechToTextProvider | None = None,
    timeout_s: int = EVC_STT_TIMEOUT_S,
    retries: int = EVC_PROVIDER_RETRIES,
) -> SpeechTextResult:
    """Run the same provider contract for the byte-oriented Q&A endpoint."""

    from .azure_speech import validate_wav

    validate_wav(audio)
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="evc-answer-", suffix=".wav", delete=False) as handle:
            handle.write(audio)
            path = Path(handle.name)
        return await transcribe_audio(
            path,
            language,
            provider=provider or provider_for_name(provider_name),
            timeout_s=timeout_s,
            retries=retries,
        )
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def speech_to_text_detail(file_path: str, language: str = "ko-KR") -> SpeechTextResult:
    """Compatibility entry point used by the legacy synchronous service."""

    return configured_provider().transcribe(file_path, language)
