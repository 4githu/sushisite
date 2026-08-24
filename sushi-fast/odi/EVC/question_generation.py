from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Protocol

from .config import (
    EVC_PROVIDER_RETRIES,
    EVC_QUESTION_TIMEOUT_S,
    OPENAI_QUESTION_MODEL,
)
from .schema import GeneratedQuestionSet


SYSTEM_PROMPT = """
You generate audience questions after an XR presentation. Use only the supplied
presentation transcript and slide outline. Return exactly question_count distinct
questions in the requested language. Prefer: (1) clarification of a core claim or
method, (2) evidence, limitations, or validation, and (3) application or extension.
Do not invent facts. Every question must include a concise intent and source_steps
that refer to transcript step numbers. Return IDs q1..qN and orders 1..N.
""".strip()


class QuestionGenerationProviderError(RuntimeError):
    pass


class QuestionGenerationProvider(Protocol):
    def generate(self, payload: dict[str, Any]) -> GeneratedQuestionSet: ...


class OpenAIQuestionGenerationProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENAI_QUESTION_MODEL,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def generate(self, payload: dict[str, Any]) -> GeneratedQuestionSet:
        if not self.api_key:
            raise QuestionGenerationProviderError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise QuestionGenerationProviderError("openai package is not installed") from exc

        try:
            client = OpenAI(api_key=self.api_key)
            completion = client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    },
                ],
                response_format=GeneratedQuestionSet,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise QuestionGenerationProviderError(
                    "OpenAI response could not be parsed as GeneratedQuestionSet"
                )
            return parsed
        except QuestionGenerationProviderError:
            raise
        except Exception as exc:
            raise QuestionGenerationProviderError(
                f"OpenAI question generation failed: {exc}"
            ) from exc


def validate_question_set(
    result: GeneratedQuestionSet,
    *,
    question_count: int,
    valid_steps: set[int],
) -> GeneratedQuestionSet:
    if len(result.questions) != question_count:
        raise QuestionGenerationProviderError(
            f"provider returned {len(result.questions)} questions; expected {question_count}"
        )
    normalized = [" ".join(item.question.lower().split()) for item in result.questions]
    if len(normalized) != len(set(normalized)):
        raise QuestionGenerationProviderError("provider returned duplicate questions")
    expected_orders = list(range(1, question_count + 1))
    if [item.order for item in result.questions] != expected_orders:
        raise QuestionGenerationProviderError("question orders must be consecutive")
    for index, item in enumerate(result.questions, start=1):
        if item.id != f"q{index}":
            raise QuestionGenerationProviderError("question IDs must match their order")
        if not item.source_steps or not set(item.source_steps) <= valid_steps:
            raise QuestionGenerationProviderError("question contains invalid source_steps")
    return result


async def generate_questions(
    payload: dict[str, Any],
    *,
    provider: QuestionGenerationProvider | None = None,
    timeout_s: int = EVC_QUESTION_TIMEOUT_S,
    retries: int = EVC_PROVIDER_RETRIES,
) -> GeneratedQuestionSet:
    selected = provider or OpenAIQuestionGenerationProvider()
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(selected.generate, payload),
                timeout=timeout_s,
            )
            return validate_question_set(
                result,
                question_count=int(payload["question_count"]),
                valid_steps={int(item["step"]) for item in payload["transcript_segments"]},
            )
        except asyncio.TimeoutError as exc:
            last_error = QuestionGenerationProviderError(
                f"question generation timed out after {timeout_s} seconds"
            )
            last_error.__cause__ = exc
        except QuestionGenerationProviderError as exc:
            last_error = exc
        if attempt < retries:
            await asyncio.sleep(0)
    assert last_error is not None
    raise last_error
