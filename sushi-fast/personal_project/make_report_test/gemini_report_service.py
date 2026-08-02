from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .config import (
    CACHE_KEY,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_MODEL,
    PROMPT_PATH,
    PROMPT_RULES_PATH,
    get_api_key,
)
from .db_repository import delete_cache, get_cache, save_cache, touch_cache


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiReportError(RuntimeError):
    pass


class GeminiReportService:
    """외부 패키지 없이 Gemini REST API와 명시적 컨텍스트 캐시를 사용한다."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        explicit_cache: bool = True,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.api_key = get_api_key(api_key)
        self.model = model
        self.explicit_cache = explicit_cache
        self.last_cache_mode = "explicit" if explicit_cache else "implicit"
        self.cache_notice: str | None = None
        self.cache_ttl_seconds = max(1, cache_ttl_seconds)

    def close(self) -> None:
        # urllib은 요청마다 연결을 정리하므로 별도 클라이언트 종료가 필요 없다.
        return None

    @staticmethod
    def read_prompt() -> str:
        draft = PROMPT_PATH.read_text(encoding="utf-8").strip()
        rules = PROMPT_RULES_PATH.read_text(encoding="utf-8").strip()
        prompt = f"{rules}\n\n[사용자 지침 원문]\n{draft}"
        if not draft or not rules:
            raise GeminiReportError("리포트 지침 파일이 비어 있습니다.")
        return prompt

    @staticmethod
    def prompt_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _expired(expires_at: str | None) -> bool:
        if not expires_at:
            return False
        try:
            value = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value <= datetime.now(timezone.utc)
        except ValueError:
            return True

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        separator = "&" if "?" in path else "?"
        url = f"{API_ROOT}/{path}{separator}{urlencode({'key': self.api_key})}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
        request = Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GeminiReportError(f"Gemini API 오류 ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise GeminiReportError(f"Gemini API 연결 실패: {exc.reason}") from exc

    def _remote_cache(self, cache_name: str) -> dict | None:
        try:
            return self._request("GET", cache_name)
        except GeminiReportError as exc:
            if "(404)" in str(exc):
                return None
            raise

    def _explicit_cache_name(self, prompt: str, prompt_hash: str) -> str | None:
        record = get_cache(CACHE_KEY, self.model, prompt_hash)
        if record and not self._expired(record.expires_at):
            if self._remote_cache(record.cache_name):
                touch_cache(record.id)
                print(f"기존 지침 캐시 재사용: {record.cache_name}")
                return record.cache_name
            delete_cache(record.id)

        print("사용 가능한 지침 캐시가 없어 새로 생성합니다.")
        try:
            cached = self._request(
                "POST",
                "cachedContents",
                {
                    "model": f"models/{self.model}",
                    "systemInstruction": {"parts": [{"text": prompt}]},
                    "displayName": f"{CACHE_KEY}:{prompt_hash[:12]}",
                    "ttl": f"{self.cache_ttl_seconds}s",
                },
            )
        except GeminiReportError as exc:
            detail = str(exc)
            if "(429)" in detail and (
                "TotalCachedContentStorageTokensPerModelFreeTier" in detail
                or "limit=0" in detail
            ):
                self.explicit_cache = False
                self.last_cache_mode = "implicit"
                self.cache_notice = (
                    "무료 등급의 명시적 캐시 한도가 0이라 일반 요청으로 자동 전환했습니다. "
                    "동일한 지침을 계속 보내므로 Gemini의 암시적 캐싱 대상이 될 수 있습니다."
                )
                return None
            raise
        cache_name = cached.get("name")
        if not cache_name:
            raise GeminiReportError("Gemini가 생성된 캐시 이름을 반환하지 않았습니다.")
        save_cache(
            CACHE_KEY,
            self.model,
            prompt_hash,
            cache_name,
            cached.get("expireTime"),
        )
        print(f"새 지침 캐시 생성 완료: {cache_name}")
        return str(cache_name)

    @staticmethod
    def _request_text(
        report_input: dict[str, Any],
        score_mode: str,
        score_format: dict[str, Any] | None,
    ) -> str:
        if score_mode not in {"auto", "none"}:
            raise ValueError(f"지원하지 않는 평가 모드입니다: {score_mode}")
        if score_mode == "none":
            score_instruction = (
                "평가를 하지 않는다. assessment는 반드시 null로 반환하고 "
                "learningContent만 작성한다."
            )
        elif score_format:
            score_instruction = (
                "아래 기존 평가 양식의 이름, 항목명, 항목 순서를 정확히 재사용한다. "
                "항목을 추가·삭제·이름 변경하지 않는다.\n"
                + json.dumps(score_format, ensure_ascii=False)
            )
        else:
            score_instruction = (
                "저장된 평가 양식이 없다. 이번 학습 범위에 맞는 4~8개 평가 항목을 "
                "새로 만들고 각 항목을 1~5점으로 평가한다. 이후 재사용할 수 있도록 "
                "formatName과 items를 빠짐없이 반환한다."
            )
        return (
            "다음 아우라 클리닉 JSON을 분석해 지정된 JSON 결과만 반환하십시오. "
            "editorDocument의 blocks, 표, depth, 각 children의 highlightColor와 "
            "questionChecks를 원형 그대로 해석해야 합니다. 입력에 없는 사실은 추측하지 마십시오.\n\n"
            f"[평가 처리]\n{score_instruction}\n\n"
            "[아우라 입력 JSON]\n"
            + json.dumps(report_input, ensure_ascii=False, separators=(",", ":"))
        )

    @staticmethod
    def _response_json(response: dict) -> dict[str, Any]:
        texts = [
            part.get("text", "")
            for candidate in response.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
            if part.get("text")
        ]
        raw = "\n".join(texts).strip()
        if not raw:
            raise GeminiReportError(
                "Gemini가 JSON 결과를 반환하지 않았습니다: "
                + json.dumps(response, ensure_ascii=False)[:1000]
            )
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```")
            raw = raw.removesuffix("```").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GeminiReportError(f"Gemini 응답이 올바른 JSON이 아닙니다: {exc}") from exc
        if not isinstance(parsed, dict):
            raise GeminiReportError("Gemini 응답 JSON의 최상위 값은 객체여야 합니다.")
        return parsed

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "assessment": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "formatName": {"type": "string"},
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "score": {"type": "integer", "minimum": 1, "maximum": 5},
                                        },
                                        "required": ["name", "score"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["formatName", "items"],
                            "additionalProperties": False,
                        },
                    ]
                },
                "learningContent": {
                    "type": "object",
                    "properties": {
                        "paragraphs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["paragraphs"],
                    "additionalProperties": False,
                },
            },
            "required": ["assessment", "learningContent"],
            "additionalProperties": False,
        }

    @staticmethod
    def _validate_result(
        generated: dict[str, Any],
        report_input: dict[str, Any],
        score_mode: str,
        score_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        learning = generated.get("learningContent")
        if not isinstance(learning, dict) or not isinstance(learning.get("paragraphs"), list):
            raise GeminiReportError("응답 JSON에 learningContent.paragraphs가 없습니다.")
        assessment = generated.get("assessment")
        if score_mode == "none":
            assessment = None
        elif not isinstance(assessment, dict) or not isinstance(assessment.get("items"), list):
            raise GeminiReportError("평가 모드인데 assessment.items가 없습니다.")
        elif score_format:
            expected = [str(item) for item in score_format.get("items", [])]
            actual = assessment["items"]
            if len(actual) != len(expected):
                raise GeminiReportError("Gemini가 기존 평가 양식의 항목 수를 변경했습니다.")
            assessment["formatName"] = score_format["name"]
            for item, name in zip(actual, expected):
                item["name"] = name
        target = report_input.get("target") or {}
        return {
            "schemaVersion": "aura.clinic-report-output.v2",
            "target": {
                key: target.get(key)
                for key in (
                    "targetId", "schoolId", "schoolName", "roundNumbers",
                    "studentName", "startTime", "endTime"
                )
            },
            "assessment": assessment,
            "learningContent": learning,
        }

    def generate(
        self,
        *,
        report_input: dict[str, Any],
        score_mode: str = "auto",
        score_format: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        prompt = self.read_prompt()
        prompt_hash = self.prompt_hash(prompt)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": self._request_text(report_input, score_mode, score_format)}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": self._response_schema(),
            },
        }
        if self.explicit_cache:
            cache_name = self._explicit_cache_name(prompt, prompt_hash)
            if cache_name:
                payload["cachedContent"] = cache_name
                self.last_cache_mode = "explicit"
            else:
                payload["systemInstruction"] = {"parts": [{"text": prompt}]}
        else:
            payload["systemInstruction"] = {"parts": [{"text": prompt}]}
            self.last_cache_mode = "implicit"

        endpoint = f"models/{quote(self.model, safe='')}:generateContent"
        try:
            response = self._request("POST", endpoint, payload)
        except GeminiReportError as exc:
            if not self.explicit_cache or "(404)" not in str(exc):
                raise
            record = get_cache(CACHE_KEY, self.model, prompt_hash)
            if record:
                delete_cache(record.id)
            cache_name = self._explicit_cache_name(prompt, prompt_hash)
            if cache_name:
                payload["cachedContent"] = cache_name
            else:
                payload.pop("cachedContent", None)
                payload["systemInstruction"] = {"parts": [{"text": prompt}]}
            response = self._request("POST", endpoint, payload)
        generated = self._response_json(response)
        return self._validate_result(
            generated, report_input, score_mode, score_format
        ), prompt_hash
