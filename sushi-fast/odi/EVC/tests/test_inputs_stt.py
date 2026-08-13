import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from odi.EVC.inputs import (
    InputValidationError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    normalize_segment_context,
    save_slide_upload,
    temporary_audio_file,
)
from odi.EVC.schema import SpeechTextResult, SpeechWord
from odi.EVC.speech2text import (
    STTProviderError,
    normalize_deepgram_response,
    transcribe_audio,
)


class FakeUpload:
    def __init__(self, data: bytes, filename: str, content_type: str) -> None:
        self._data = data
        self._offset = 0
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._offset
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def test_temporary_audio_is_validated_and_always_removed() -> None:
    async def scenario() -> None:
        upload = FakeUpload(b"RIFF-test", "voice.wav", "audio/wav")
        captured: Path | None = None
        async with temporary_audio_file(upload, max_bytes=100) as path:
            captured = path
            assert path.read_bytes() == b"RIFF-test"
        assert captured is not None
        assert not captured.exists()

    asyncio.run(scenario())


def test_upload_limits_and_media_types_fail_without_leaving_files(tmp_path: Path) -> None:
    async def scenario() -> None:
        with pytest.raises(PayloadTooLargeError):
            async with temporary_audio_file(
                FakeUpload(b"12345", "voice.wav", "audio/wav"),
                max_bytes=4,
            ):
                pass

        with pytest.raises(UnsupportedMediaTypeError):
            await save_slide_upload(
                FakeUpload(b"text", "slides.txt", "text/plain"),
                tmp_path,
            )
        assert list(tmp_path.iterdir()) == []

    asyncio.run(scenario())


def test_context_normalization_validates_slide_language_and_events() -> None:
    context = normalize_segment_context(
        slides=[],
        current_slide_index=0,
        utterance_position="slide_transition",
        language="ko-KR",
        gaze_delivery_score=None,
        slide_reference=False,
        event_signals='{"information_dense": 0.6}',
        client_time_s=2.5,
    )
    assert context.slide_reference is True
    assert context.event_signals.slide_reference == 1.0
    assert context.event_signals.information_dense == 0.6

    with pytest.raises(InputValidationError):
        normalize_segment_context(
            slides=[],
            current_slide_index=1,
            utterance_position="during_speech",
            language="ko-KR",
            gaze_delivery_score=None,
            slide_reference=False,
            event_signals=None,
            client_time_s=0.0,
        )

    with pytest.raises(InputValidationError):
        normalize_segment_context(
            slides=[],
            current_slide_index=0,
            utterance_position="during_speech",
            language="not a tag",
            gaze_delivery_score=None,
            slide_reference=False,
            event_signals=None,
            client_time_s=0.0,
        )

    with pytest.raises(ValidationError):
        normalize_segment_context(
            slides=[],
            current_slide_index=0,
            utterance_position="during_speech",
            language="ko-KR",
            gaze_delivery_score=None,
            slide_reference=False,
            event_signals='{"unknown": 1}',
            client_time_s=0.0,
        )


def test_deepgram_response_is_normalized_and_invalid_timing_is_rejected() -> None:
    result = normalize_deepgram_response(
        {
            "results": {
                "channels": [
                    {
                        "alternatives": [
                            {
                                "transcript": "안녕하세요",
                                "words": [
                                    {
                                        "word": "안녕하세요",
                                        "start": 0.1,
                                        "end": 0.8,
                                        "confidence": 0.95,
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        }
    )
    assert result.transcript == "안녕하세요"
    assert result.words[0].confidence == 0.95

    with pytest.raises(STTProviderError):
        normalize_deepgram_response({"results": {"channels": []}})
    with pytest.raises(ValidationError):
        SpeechWord(word="bad", start=1.0, end=0.5, confidence=0.5)


def test_async_stt_boundary_supports_test_provider_and_retries(tmp_path: Path) -> None:
    class FlakyProvider:
        def __init__(self) -> None:
            self.calls = 0

        def transcribe(self, file_path: str | Path, language: str) -> SpeechTextResult:
            self.calls += 1
            if self.calls == 1:
                raise STTProviderError("temporary")
            return SpeechTextResult(transcript="ok", words=[])

    async def scenario() -> None:
        provider = FlakyProvider()
        result = await transcribe_audio(
            tmp_path / "audio.wav",
            provider=provider,
            timeout_s=1,
            retries=1,
        )
        assert result.transcript == "ok"
        assert provider.calls == 2

    asyncio.run(scenario())
