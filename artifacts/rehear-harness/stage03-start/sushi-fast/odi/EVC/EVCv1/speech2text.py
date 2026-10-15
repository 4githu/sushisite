import os
# from dotenv import load_dotenv
# load_dotenv()
# 근데 이건 main.py에서 했으면 할필요 없다네요?
from deepgram import (
    DeepgramClient,
)
SPEECH2TEXT_API_KEY = os.getenv("DEEPGRAM_API_KEY")

def speech2text(file, language = "ko-KR") -> str:
    try:

        deepgram = DeepgramClient(api_key=SPEECH2TEXT_API_KEY)

        with open(file, "rb") as f:
            buffer_data = f.read()

        response = deepgram.listen.v1.media.transcribe_file(
            request=buffer_data,
            model="nova-3",
            filler_words=True, 
            utterances=True,
            language=language,
        ).model_dump()

        return response['results']['channels'][0]['alternatives'][0]['transcript']

    except Exception as e:
        raise RuntimeError("Speech to Text 실패") from e


