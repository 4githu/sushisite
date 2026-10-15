from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from openai import OpenAI

from .schema import AudienceEVC, AudiencePersona, AudienceState, EVCState
from .speech2text import speech2text


OPENAI_MODEL = os.getenv("OPENAI_EVC_MODEL", "gpt-4.1-nano")
DEBUG_EVC_LOG = os.getenv("DEBUG_EVC_LOG", "true").lower() == "true"
DEBUG_LOG_DIR = Path(os.getenv("EVC_DEBUG_LOG_DIR", "evc_logs"))

client = OpenAI()


SYSTEM_PROMPT = """
당신은 발표를 듣는 AI 청중 시뮬레이터이다.

입력으로 고정 청중 페르소나, 지금까지의 발표 요약, 직전 청중 상태, 발표자가 방금 말한 내용이 제공된다.
당신의 역할은 latestSpeech만 반영하여 각 청중의 EVC 상태를 갱신하는 것이다.

E는 Engagement이다. -1은 발표에 거의 관심이 없고 집중하지 않는 상태, 0은 보통 수준, +1은 매우 집중하고 있는 상태이다.
V는 Evaluative Valence이다. -1은 발표를 매우 부정적으로 평가하는 상태, 0은 중립, +1은 매우 긍정적으로 평가하는 상태이다.
C는 Cognitive Clarity이다. -1은 발표를 거의 이해하지 못하는 상태, 0은 부분적으로 이해하는 상태, +1은 매우 명확하게 이해하는 상태이다.

갱신 규칙은 다음과 같다. persona를 반영하고, 기존 state를 기반으로 자연스럽게 변화시키며, latestSpeech에 해당하는 짧은 구간만 반영한다. 5초 구간의 입력이므로 E, V, C는 급격하게 바꾸지 말고 한 번의 업데이트에서 각 값의 변화량은 가능하면 0.15 이내로 유지한다. 발표가 명확하면 C를 증가시키고, 발표가 흥미롭거나 청중의 관심사와 관련 있으면 E를 증가시키며, 발표 품질이 좋거나 설득력이 높으면 V를 증가시킨다. 반복, 모호함, 근거 부족, 과도한 전문 용어는 E, V, C 중 적절한 값을 낮춘다. currentThought는 현재 머릿속에서 드는 생각을 한 문장으로 작성하고, overallImpression은 발표 전체에 대한 누적 인상이므로 급격하게 바꾸지 않는다.

summary_delta에는 이번 latestSpeech를 기존 summary 뒤에 추가하기 좋은 짧은 요약만 작성한다. 기존 summary 전체를 다시 쓰지 않는다. 출력 audiences 배열의 id, 길이, 순서는 입력 session_state.audiences와 동일하게 유지한다.
""".strip()


@dataclass
class EVCSession:
    session_id: str
    personas: list[AudiencePersona]
    summary: str
    evc_state: EVCState
    step: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


sessions: dict[str, EVCSession] = {}


def create_mock_session() -> EVCSession:
    session_id = str(uuid4())

    personas = [
        AudiencePersona(
            id=1,
            persona={
                "role": "AI에 관심이 많은 학생",
                "interest": "AI, VR, 발표 시스템",
                "patience": "high",
                "attitude": "curious",
            },
        ),
        AudiencePersona(
            id=2,
            persona={
                "role": "기술 설명에 익숙하지 않은 청중",
                "interest": "사용자 경험, 쉬운 설명",
                "patience": "medium",
                "attitude": "confused_when_too_technical",
            },
        ),
        AudiencePersona(
            id=3,
            persona={
                "role": "비판적인 평가자",
                "interest": "근거, 실현 가능성, 구조",
                "patience": "medium",
                "attitude": "skeptical",
            },
        ),
    ]

    initial_audiences = [
        AudienceEVC(
            id=p.id,
            state=AudienceState(E=0.0, V=0.0, C=0.0),
            currentThought="아직 발표를 판단하기에는 정보가 부족하다.",
            overallImpression="아직 뚜렷한 인상은 없다.",
        )
        for p in personas
    ]

    session = EVCSession(
        session_id=session_id,
        personas=personas,
        summary="",
        evc_state=EVCState(summary_delta="", audiences=initial_audiences),
    )

    sessions[session_id] = session
    return session


def get_session(session_id: str) -> EVCSession:
    session = sessions.get(session_id)
    if session is None:
        raise ValueError(f"존재하지 않는 EVC session_id입니다: {session_id}")
    return session


async def save_upload_file_temp(audio: UploadFile) -> str:
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        contents = await audio.read()
        temp_file.write(contents)
        return temp_file.name


def build_gpt_input(session: EVCSession, latest_speech: str) -> dict[str, Any]:
    return {
        "audiences_persona": [p.model_dump() for p in session.personas],
        "presentation_summary": session.summary,
        "session_state": session.evc_state.model_dump(),
        "latestSpeech": latest_speech,
    }


def call_gpt_for_evc(session: EVCSession, latest_speech: str) -> EVCState:
    gpt_input = build_gpt_input(session, latest_speech)

    completion = client.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    gpt_input,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        response_format=EVCState,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("GPT 응답을 EVCState로 파싱하지 못했습니다.")

    validate_evc_output(session.evc_state, parsed)
    log_usage(session, completion)
    return parsed


def validate_evc_output(previous_state: EVCState, new_state: EVCState) -> None:
    previous_ids = [a.id for a in previous_state.audiences]
    new_ids = [a.id for a in new_state.audiences]

    if previous_ids != new_ids:
        raise ValueError(f"GPT 출력의 audience id 순서가 입력과 다릅니다. previous={previous_ids}, new={new_ids}")


def apply_evc_output(session: EVCSession, output: EVCState) -> None:
    if output.summary_delta.strip():
        if session.summary:
            session.summary += " " + output.summary_delta.strip()
        else:
            session.summary = output.summary_delta.strip()

    session.evc_state = output
    session.step += 1
    session.updated_at = datetime.now()


def generate_idle_actions(session: EVCSession) -> list[dict[str, Any]]:
    return [
        {
            "id": audience.id,
            "motion": "idle",
            "intensity": 0.0,
        }
        for audience in session.evc_state.audiences
    ]


def build_update_response(session: EVCSession, latest_speech: str) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "step": session.step,
        "latestSpeech": latest_speech,
        "summary": session.summary,
        "evc_state": session.evc_state.model_dump(),
        "actions": generate_idle_actions(session),
    }


async def update_evc_from_audio(session_id: str, audio: UploadFile, language: str = "ko-KR") -> dict[str, Any]:
    session = get_session(session_id)
    temp_audio_path = await save_upload_file_temp(audio)

    try:
        latest_speech = speech2text(temp_audio_path, language=language)
        gpt_output = call_gpt_for_evc(session, latest_speech)
        debug_save_step(session, latest_speech, gpt_output)
        apply_evc_output(session, gpt_output)
        return build_update_response(session, latest_speech)

    finally:
        try:
            os.remove(temp_audio_path)
        except OSError:
            pass


def debug_save_step(session: EVCSession, latest_speech: str, gpt_output: EVCState) -> None:
    if not DEBUG_EVC_LOG:
        return

    session_dir = DEBUG_LOG_DIR / session.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "session_id": session.session_id,
        "step": session.step + 1,
        "created_at": datetime.now().isoformat(),
        "latestSpeech": latest_speech,
        "summary_before": session.summary,
        "gpt_output": gpt_output.model_dump(),
    }

    path = session_dir / f"step_{session.step + 1:04d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def log_usage(session: EVCSession, completion: Any) -> None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return

    try:
        cached_tokens = usage.prompt_tokens_details.cached_tokens
    except Exception:
        cached_tokens = None

    if cached_tokens is not None:
        print(f"[EVC] session={session.session_id} step={session.step + 1} cached_tokens={cached_tokens}")