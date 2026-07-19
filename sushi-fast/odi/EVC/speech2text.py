# xreal_rehair/evc/speech2text.py

import os
from dotenv import load_dotenv
from deepgram import DeepgramClient

from .schema import SpeechTextResult, SpeechWord

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


def speech_to_text_detail(file_path: str, language: str = "ko-KR") -> SpeechTextResult:
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY가 설정되어 있지 않습니다.")

    try:
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

        with open(file_path, "rb") as f:
            buffer_data = f.read()

        response = deepgram.listen.v1.media.transcribe_file(
            request=buffer_data,
            model="nova-3",
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

    except Exception as e:
        raise RuntimeError(f"STT 처리 실패: {e}") from e