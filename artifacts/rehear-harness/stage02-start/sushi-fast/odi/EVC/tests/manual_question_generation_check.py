"""Manual live-provider check for presentation question generation.

Run from sushi-fast with:
    .venv/Scripts/python.exe -m odi.EVC.tests.manual_question_generation_check
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from odi.EVC.pipeline import create_pipeline_session
from odi.EVC.question_service import generate_session_questions
from odi.EVC.schema import (
    GeneratedQuestion,
    GeneratedQuestionSet,
    SmartStartOptions,
    TranscriptSegment,
)
from odi.EVC.session_store import SessionStore


SCRIPT_SEGMENTS = [
    "안녕하세요. 컴퓨터공학과 강수련입니다.",
    (
        "저는 컴퓨터 그래픽스와 실시간 렌더링, 그리고 XR 기술이 가진 실질적인 "
        "효용성에 집중하고 있습니다. 기술 자체의 성능 향상도 중요하지만, 궁극적으로 "
        "그 기술이 사람과 어떻게 상호작용하고 사회적인 문제를 해결할 수 있는지가 "
        "제 주된 연구 관심사입니다."
    ),
    (
        "현재 진행 중인 졸업 프로젝트 마이 익스프레션 프렌드는 이러한 고민의 "
        "결과물입니다. 이 프로젝트는 아이들의 표정 인식과 사회적 상호작용 훈련을 "
        "돕는 앱으로, 그래픽스와 HCI 기술이 실생활의 문제를 개선하는 도구로 쓰일 수 "
        "있음을 증명하는 과정에 있습니다."
    ),
    (
        "앞으로 저는 메타버스 플랫폼이나 글로벌 R&D 환경에서 기술적 한계를 극복하고 "
        "렌더링 파이프라인을 최적화하는 그래픽스 엔지니어로 성장하고자 합니다. 막연한 "
        "기대감보다는 객관적인 데이터와 논리를 바탕으로 문제를 분석하고, 꾸준히 "
        "돌파구를 찾아내는 개발자가 되겠습니다. 감사합니다."
    ),
]


class LocalCheckProvider:
    """Deterministic provider for verifying service flow and response JSON."""

    def generate(self, payload):
        assert len(payload["transcript_segments"]) == 4
        return GeneratedQuestionSet(
            questions=[
                GeneratedQuestion(
                    id="q1",
                    order=1,
                    question=(
                        "‘마이 익스프레션 프렌드’가 아이들의 표정 인식 능력 향상에 "
                        "실제로 효과가 있는지 어떤 지표로 평가할 계획인가요?"
                    ),
                    intent="프로젝트 효과의 객관적인 검증 방법 확인",
                    source_steps=[3],
                ),
                GeneratedQuestion(
                    id="q2",
                    order=2,
                    question=(
                        "아동의 표정 데이터를 다루는 과정에서 개인정보 보호와 편향 "
                        "문제를 어떻게 해결하고 있나요?"
                    ),
                    intent="실제 적용 과정의 윤리적·기술적 한계 확인",
                    source_steps=[2, 3],
                ),
                GeneratedQuestion(
                    id="q3",
                    order=3,
                    question=(
                        "현재 프로젝트 경험이 앞으로 목표로 하는 렌더링 파이프라인 "
                        "최적화 업무와 구체적으로 어떻게 연결되나요?"
                    ),
                    intent="현재 프로젝트와 향후 진로 사이의 연계성 확인",
                    source_steps=[3, 4],
                ),
            ]
        )


async def main() -> None:
    load_dotenv()
    store = SessionStore()
    started = await create_pipeline_session(
        SmartStartOptions(
            presentation_title="컴퓨터 그래픽스와 HCI를 활용한 사회적 문제 해결",
            seed=20260825,
        ),
        store=store,
    )
    record = await store.get_authorized_session(started.session_id, started.session_token)
    for step, text in enumerate(SCRIPT_SEGMENTS, start=1):
        record.transcript_segments.append(
            TranscriptSegment(
                step=step,
                client_time_s=float(step * 10),
                slide_index=0,
                text=text,
                word_count=len(text.split()),
            )
        )

    response = await generate_session_questions(
        session_id=started.session_id,
        token=started.session_token,
        request_id=__import__("uuid").uuid4(),
        question_count=3,
        provider=LocalCheckProvider() if "--local" in sys.argv else None,
        store=store,
    )
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
