from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import read_named_api_key
from .gemini_report_service import GeminiReportService, GeminiReportError


class ProviderReportService:
    """OpenAI/Anthropic 텍스트 API를 동일한 아우라 JSON 계약으로 감싼다."""

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        self.last_cache_mode = "implicit"
        self.cache_notice = "동일 입력 결과는 아우라 DB에서 재사용합니다."
        key_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        self.api_key = os.getenv(key_name) or read_named_api_key(key_name)
        if not self.api_key:
            raise GeminiReportError(f"{key_name}가 없습니다. sushi-fast/.env에 API 키를 추가해주세요.")

    def close(self) -> None:
        return None

    def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GeminiReportError(f"{self.provider} API 오류 ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise GeminiReportError(f"{self.provider} API 연결 오류: {exc}") from exc

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        value = raw.strip()
        if value.startswith("```"):
            value = value.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            result = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GeminiReportError(f"AI 응답이 올바른 JSON이 아닙니다: {exc}") from exc
        if not isinstance(result, dict):
            raise GeminiReportError("AI 응답 JSON의 최상위 값은 객체여야 합니다.")
        return result

    def generate(
        self,
        *,
        report_input: dict[str, Any],
        score_mode: str = "auto",
        score_format: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        prompt = GeminiReportService.read_prompt()
        prompt_hash = GeminiReportService.prompt_hash(prompt)
        user_text = GeminiReportService._request_text(report_input, score_mode, score_format)
        schema = GeminiReportService._response_schema()
        if self.provider == "openai":
            response = self._post(
                "https://api.openai.com/v1/chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_text},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": "aura_clinic_report", "strict": True, "schema": schema},
                    },
                },
                {"Authorization": f"Bearer {self.api_key}"},
            )
            raw = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            response = self._post(
                "https://api.anthropic.com/v1/messages",
                {
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": prompt + "\n반드시 JSON 객체만 출력하십시오.",
                    "messages": [{"role": "user", "content": user_text}],
                },
                {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
            raw = "\n".join(
                item.get("text", "") for item in response.get("content", [])
                if item.get("type") == "text"
            )
        generated = self._parse_json(raw)
        return GeminiReportService._validate_result(
            generated, report_input, score_mode, score_format
        ), prompt_hash
