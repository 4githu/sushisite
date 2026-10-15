"""Synthetic Azure integration check; no user microphone or real LLM call.

Run from sushi-fast: python -m odi.EVC.tests.manual_azure_qa_check
Requires server AZURE_SPEECH_KEY and AZURE_SPEECH_REGION. Uses Azure quota.
"""
import asyncio
import os
from uuid import uuid4

from odi.EVC.azure_speech import synthesize, validate_wav
from odi.EVC.azure_continuous_stt import recognize
from odi.EVC.answer_service import submit_answer
from odi.EVC.schema import SpeechTextResult, GeneratedQuestion, GeneratedQuestionSet, SmartStartOptions, TranscriptSegment
from odi.EVC.session_store import SessionStore


async def main():
    audio = await synthesize("대조군과 비교해서 추천 결과의 다양성을 검증했습니다.", "ko-KR-InJoonNeural")
    validate_wav(audio)
    result = SpeechTextResult.model_validate(await asyncio.to_thread(
        recognize, audio, os.environ["AZURE_SPEECH_KEY"], os.environ["AZURE_SPEECH_REGION"], detailed=True))
    assert result.transcript and result.words and all(w.end >= w.start >= 0 for w in result.words)
    print("PASS real Azure TTS -> continuous STT -> word timing (synthetic audio).")
    store = SessionStore()
    record, token = await store.create_session(SmartStartOptions(presentation_title="추천 다양성 테스트"))
    record.transcript_segments = [TranscriptSegment(step=1, slide_index=0, client_time_s=1,
                                                   text="추천 결과의 다양성을 비교했습니다.", word_count=4)]
    record.generated_questions = [GeneratedQuestion(id=f"q{i}", order=i, question=f"검증 질문 {i}?",
                                                    intent="확인", source_steps=[1]) for i in (1, 2)]
    record.question_generation_status = "ready"
    class MockLLM:
        def generate(self, payload):
            assert payload["qa_history"][0]["answer"] == result.transcript
            assert payload["next_audience"]["agent_id"] == "audience_02"
            return GeneratedQuestionSet(questions=[GeneratedQuestion(id="q1", order=1,
                question="다양성 외에 사용자의 만족도는 어떻게 측정하셨나요?", intent="다른 관점 확인", source_steps=[1])])
    async def recognized(_): return result.transcript
    response = await submit_answer(session_id=record.session_id, token=token, index=0, request_id=uuid4(),
                audio=audio, next_audience_id="audience_02", store=store, provider=MockLLM(), transcriber=recognized)
    assert response["total"] == 2 and response["next_question"]["order"] == 2
    next_audio = await synthesize(record.generated_questions[1].question, "ko-KR-SunHiNeural")
    validate_wav(next_audio)
    print("PASS answer context -> MOCK LLM -> updated q2 -> real Azure TTS; total remains 2.")
    print("Not tested: real LLM credentials, deployed API, Unity/Quest microphone.")


if __name__ == "__main__":
    asyncio.run(main())
