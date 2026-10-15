"""Server-only Speech SDK, compatible with the resource's F0 tier."""
import io
import json
import re
import threading
import wave

import azure.cognitiveservices.speech as sdk
from fastapi import HTTPException


_recognition_lock = threading.Lock()


def recognize(data, key, region, *, detailed=False, language="ko-KR"):
    # Shared by presentation segments and Q&A; protect the F0 resource across threads.
    if not _recognition_lock.acquire(timeout=30):
        raise HTTPException(429, "Azure recognition is busy; retry shortly")
    try:
        return _recognize(data, key, region, detailed=detailed, language=language)
    finally:
        _recognition_lock.release()


def _recognize(data, key, region, *, detailed=False, language="ko-KR"):
    if not re.fullmatch(r"[a-z0-9]+", region):
        raise HTTPException(503, "Invalid Azure region")
    with wave.open(io.BytesIO(data), "rb") as wav:
        rate = wav.getframerate()
        duration = wav.getnframes() / rate
        pcm = wav.readframes(wav.getnframes())
    config = sdk.SpeechConfig(subscription=key, region=region)
    config.speech_recognition_language = language
    config.output_format = sdk.OutputFormat.Detailed
    config.request_word_level_timestamps()
    stream = sdk.audio.PushAudioInputStream(
        stream_format=sdk.audio.AudioStreamFormat(samples_per_second=rate, bits_per_sample=16, channels=1))
    audio = sdk.audio.AudioConfig(stream=stream)
    recognizer = sdk.SpeechRecognizer(speech_config=config, audio_config=audio)
    done = threading.Event()
    phrases, failures, words = [], [], []

    def recognized(event):
        if event.result.reason == sdk.ResultReason.RecognizedSpeech and event.result.text:
            phrases.append(event.result.text.strip())
            try:
                best = json.loads(event.result.json)["NBest"][0]
                for word in best.get("Words", []):
                    words.append({"word": word["Word"], "start": word["Offset"] / 10_000_000,
                                  "end": (word["Offset"] + word["Duration"]) / 10_000_000,
                                  "confidence": word.get("Confidence", best.get("Confidence", 0))})
            except (KeyError, IndexError, TypeError, ValueError):
                failures.append("InvalidDetailedResult")

    def canceled(event):
        if event.reason == sdk.CancellationReason.Error:
            # Raw SDK errors can contain URLs and credentials. Return the enum only.
            failures.append(str(event.error_code))
        done.set()

    recognizer.recognized.connect(recognized)
    recognizer.canceled.connect(canceled)
    recognizer.session_stopped.connect(lambda _: done.set())
    started = False
    try:
        recognizer.start_continuous_recognition_async().get()
        started = True
        for offset in range(0, len(pcm), 8192):
            stream.write(pcm[offset:offset + 8192])
        stream.close()
        if not done.wait(max(60, duration + 60)):
            raise HTTPException(504, "Azure STT timed out")
        if failures:
            raise HTTPException(502, "Azure STT failed: " + failures[0])
        text = " ".join(phrases).strip()
        return {"transcript": text, "words": words} if detailed else text
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Azure STT SDK unavailable or recognition failed") from None
    finally:
        stream.close()
        if started:
            try:
                recognizer.stop_continuous_recognition_async().get()
            except Exception:
                pass
