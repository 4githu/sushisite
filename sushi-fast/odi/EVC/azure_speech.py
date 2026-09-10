"""Server-only Azure adapter for the existing EVC API (no credentials in APK)."""
import asyncio
import io
import json
import os
import re
import wave
from xml.sax.saxutils import escape
import httpx
from fastapi import HTTPException

# F0 Speech supports one concurrent recognition. Run EVC with one worker,
# consistent with its existing in-memory SessionStore.
_stt_slot = asyncio.Semaphore(1)
MAX_WAV_BYTES = 20_000_000
def setting(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(503, f"Server configuration missing: {name}")
    return value


def azure_headers():
    return {"Ocp-Apim-Subscription-Key": setting("AZURE_SPEECH_KEY")}


async def checked_request(method, url, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=150, follow_redirects=False) as client:
            response = await client.request(method, url, **kwargs)
    except httpx.HTTPError:
        raise HTTPException(502, "Speech dependency unavailable") from None
    if response.status_code in (401, 403) and "X-EVC-Session-Token" in kwargs.get("headers", {}):
        raise HTTPException(403, "Invalid session credentials")
    if not 200 <= response.status_code < 300:
        # Do not expose upstream bodies, keys or session tokens.
        raise HTTPException(502, f"Speech dependency returned HTTP {response.status_code}")
    return response



def validate_wav(data):
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or not 8000 <= rate <= 48000:
                raise ValueError()
            if not 0 < frames / rate <= 601 or len(audio.readframes(frames)) != frames * 2:
                raise ValueError()
    except (wave.Error, EOFError, ValueError):
        raise HTTPException(422, "Expected mono PCM16 WAV up to ten minutes") from None


async def _transcribe(data):
    mode = os.environ.get("AZURE_STT_MODE", "continuous").strip().lower()
    if mode == "continuous":
        from .azure_continuous_stt import recognize
        return await asyncio.to_thread(recognize, data, setting("AZURE_SPEECH_KEY"), setting("AZURE_SPEECH_REGION"))
    if mode != "fast":
        raise HTTPException(503, "AZURE_STT_MODE must be continuous or fast")
    endpoint = setting("AZURE_SPEECH_ENDPOINT").rstrip("/")
    if not re.fullmatch(r"https://[a-zA-Z0-9-]+\.cognitiveservices\.azure\.com", endpoint):
        raise HTTPException(503, "Use the Azure resource HTTPS custom endpoint")
    response = await checked_request("POST", endpoint + "/speechtotext/transcriptions:transcribe?api-version=2025-10-15",
        headers=azure_headers(), files={"audio": ("answer.wav", data, "audio/wav")},
        data={"definition": json.dumps({"locales": ["ko-KR"]})})
    result = response.json()
    return " ".join(p.get("text", "").strip() for p in result.get("combinedPhrases", [])).strip()


VOICES = ("ko-KR-InJoonNeural", "ko-KR-BongJinNeural", "ko-KR-GookMinNeural",
          "ko-KR-SunHiNeural", "ko-KR-JiMinNeural", "ko-KR-SeoHyeonNeural", "ko-KR-SoonBokNeural", "ko-KR-YuJinNeural")


async def synthesize(text, voice):
    region = setting("AZURE_SPEECH_REGION")
    if not re.fullmatch(r"[a-z0-9]+", region):
        raise HTTPException(503, "Invalid Azure region")
    if voice not in VOICES:
        raise HTTPException(422, "Unsupported Korean voice")
    ssml = f'<speak version="1.0" xml:lang="ko-KR"><voice name="{voice}">{escape(text)}</voice></speak>'
    headers = {**azure_headers(), "Content-Type": "application/ssml+xml",
               "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm", "User-Agent": "ReHearSpeech"}
    response = await checked_request("POST", f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                                      headers=headers, content=ssml.encode("utf-8"))
    if not response.content.startswith(b"RIFF"):
        raise HTTPException(502, "Invalid speech audio")
    return response.content



async def transcribe(data):
    async with _stt_slot:
        return await _transcribe(data)
