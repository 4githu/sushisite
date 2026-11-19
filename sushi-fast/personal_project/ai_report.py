from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from fastapi import HTTPException

from . import repository
from .make_report_test.db_repository import (
    build_report_input,
    find_completed_run,
    finish_run,
    get_active_score_format,
    list_completed_runs,
    migrate,
    save_generated_score_format,
    set_run_cache_mode,
    set_run_score_format,
    start_run,
)
from .make_report_test.gemini_report_service import GeminiReportError, GeminiReportService
from .make_report_test.model_registry import default_model_id, get_report_model, model_options
from .make_report_test.provider_report_service import ProviderReportService


def available_models() -> dict[str, Any]:
    return {"defaultModel": default_model_id(), "models": model_options()}


def saved_generations(user_id: int, target_id: int) -> dict[str, Any]:
    repository.get_or_create_target_report(user_id, target_id)
    migrate()
    return {"targetId": target_id, "results": list_completed_runs(target_id)}


def _input_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_DIAGNOSTIC_CODES = frozenset({
    "provider_error", "network_error", "cache_name_missing", "empty_response",
    "invalid_json", "invalid_json_root", "invalid_output_learning_content",
    "invalid_output_assessment", "invalid_output_score_count",
    "provider_blocked_safety", "provider_blocked_other", "provider_blocked_blocklist",
    "provider_blocked_prohibited_content", "provider_blocked_image_safety",
    "provider_blocked_recitation", "provider_blocked_spii",
})


def _diagnostic_code(exc: Exception) -> str:
    if not isinstance(exc, GeminiReportError):
        return "unclassified"
    code = getattr(exc, "diagnostic_code", None)
    if isinstance(code, str) and (code in _DIAGNOSTIC_CODES or re.fullmatch(r"api_http_[1-5][0-9]{2}", code)):
        return code
    return "unclassified"


def _safe_generation_error(stage: str, exc: Exception) -> str:
    name = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name):
        name = "Exception"
    return f"{stage}:{name}:{_diagnostic_code(exc)}"


def generate(
    user_id: int,
    target_id: int,
    *,
    model: str | None = None,
    score_mode: str = "auto",
    assessment_items: list[dict[str, Any]] | None = None,
    force: bool = False,
    highlight_semantics: dict[str, str] | None = None,
    include_question_checks: bool = False,
) -> dict[str, Any]:
    if score_mode not in {"auto", "none"}:
        raise HTTPException(status_code=422, detail="평가 모드는 auto 또는 none이어야 합니다.")
    repository.get_or_create_target_report(user_id, target_id)
    migrate()
    allowed_semantics = {"fixed", "unfixed", "not_reasked"}
    semantics = highlight_semantics or {
        "yellow": "fixed", "orange": "unfixed", "peach": "not_reasked"
    }
    if set(semantics) != {"yellow", "orange", "peach"} or any(value not in allowed_semantics for value in semantics.values()):
        raise HTTPException(status_code=422, detail="형광색 의미 설정을 확인해주세요.")
    if len(set(semantics.values())) != 3:
        raise HTTPException(status_code=422, detail="노랑·주황·살구의 의미는 서로 다르게 선택해주세요.")
    report_input = build_report_input(target_id, include_question_checks=include_question_checks)
    if (report_input.get("target") or {}).get("userId") != user_id:
        raise HTTPException(status_code=404, detail="학생 리포트를 찾을 수 없습니다.")

    clean_assessment: list[dict[str, Any]] = []
    for item in assessment_items or []:
        name = str(item.get("name") or "").strip()
        score = item.get("score")
        if not name or not isinstance(score, int) or not 1 <= score <= 5:
            raise HTTPException(status_code=422, detail="평가 항목은 이름과 1~5점 점수가 필요합니다.")
        clean_assessment.append({"name": name, "score": score})
    model_id = model or default_model_id()
    try:
        option = get_report_model(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previous_runs = list_completed_runs(target_id)
    score_format = get_active_score_format(report_input) if score_mode == "auto" else None
    effective_score_mode = score_mode

    # 한 번이라도 생성된 뒤에는 모델이 평가 항목명을 새로 만들지 못한다.
    if score_mode == "auto" and previous_runs and not score_format:
        previous_assessment = previous_runs[0].get("output", {}).get("assessment") or {}
        previous_names = [
            str(item.get("name") or "").strip()
            for item in previous_assessment.get("items", [])
            if str(item.get("name") or "").strip()
        ]
        if previous_names:
            score_format = {
                "id": None,
                "name": previous_assessment.get("formatName") or "학습 내용 및 암기 정도 평가",
                "items": previous_names,
                "source": "previous_generation",
            }
        else:
            effective_score_mode = "none"
    # 최초 생성에서 사용자가 입력한 항목은 항목명과 순서를 고정한다.
    if score_mode == "auto" and not previous_runs and clean_assessment:
        score_format = {
            "id": None,
            "name": "학습 내용 및 암기 정도 평가",
            "items": [item["name"] for item in clean_assessment],
            "source": "user",
        }

    # Snapshot the effective selection, not just its DB id: edits to the same row
    # must invalidate completed runs without introducing time-dependent hashes.
    score_format_snapshot = None
    if score_format is not None:
        score_format_snapshot = {
            "id": score_format.get("id"),
            "name": score_format.get("name"),
            "items": list(score_format["items"]),
            "source": score_format.get("source"),
        }
        for key in ("version", "revision"):
            if key in score_format:
                score_format_snapshot[key] = score_format[key]

    report_input["options"] = {
        "scoreFormatSnapshot": score_format_snapshot,
        "scoreMode": effective_score_mode,
        "requestedScoreMode": score_mode,
        "assessmentItems": clean_assessment,
        "highlightSemantics": semantics,
        "includeQuestionChecks": include_question_checks,
    }
    input_hash = _input_hash(report_input)
    prompt = GeminiReportService.read_prompt()
    prompt_hash = GeminiReportService.prompt_hash(prompt)

    previous = None if force else find_completed_run(target_id, model_id, input_hash, prompt_hash)
    if previous:
        return {
            "targetId": target_id,
            "defaultModel": default_model_id(),
            "results": [{**previous, "reused": True, "inputHash": input_hash}],
            "errors": [],
        }

    run_id = start_run(
        target_id,
        model_id,
        "explicit" if option.explicit_cache else "implicit",
        prompt_hash,
        input_json=report_input,
        score_mode=effective_score_mode,
        score_format_id=score_format.get("id") if score_format else None,
        provider=option.provider,
        input_hash=input_hash,
    )
    service = None
    stage = "provider_initialize"
    try:
        service = (
            GeminiReportService(model=model_id, explicit_cache=option.explicit_cache)
            if option.provider == "gemini"
            else ProviderReportService(option.provider, model_id)
        )
        stage = "provider_generate"
        output, _ = service.generate(
            report_input=report_input,
            score_mode=effective_score_mode,
            score_format=score_format,
        )
        if output.get("assessment") and clean_assessment:
            fixed_scores = {item["name"]: item["score"] for item in clean_assessment}
            for item in output["assessment"].get("items", []):
                if item.get("name") in fixed_scores:
                    item["score"] = fixed_scores[item["name"]]
        stage = "persist_generated_report"
        if output.get("assessment") and not previous_runs and (not score_format or score_format.get("id") is None):
            assessment = output["assessment"]
            format_id = save_generated_score_format(
                report_input,
                assessment.get("formatName") or "학습 내용 및 암기 정도 평가",
                [item.get("name", "") for item in assessment.get("items", [])],
            )
            if format_id:
                set_run_score_format(run_id, format_id)
        set_run_cache_mode(run_id, service.last_cache_mode)
        finish_run(run_id, response_json=output)
        result = {
            "runId": run_id,
            "provider": option.provider,
            "model": model_id,
            "cacheMode": service.last_cache_mode,
            "reused": False,
            "inputHash": input_hash,
            "output": output,
            "cacheNotice": service.cache_notice,
        }
    except Exception as exc:
        safe_error = _safe_generation_error(stage, exc)
        finish_run(run_id, error=safe_error)
        code = _diagnostic_code(exc)
        blocked = stage == "provider_generate" and code in {
            "provider_blocked_safety", "provider_blocked_other", "provider_blocked_blocklist",
            "provider_blocked_prohibited_content", "provider_blocked_image_safety",
            "provider_blocked_recitation", "provider_blocked_spii",
        }
        unavailable = stage == "provider_generate" and code == "api_http_503"
        raise HTTPException(
            status_code=422 if blocked else 502,
            detail={
                "code": ("ai_report_provider_blocked" if blocked else
                         "ai_report_provider_unavailable" if unavailable else "ai_report_generation_failed"),
                "message": (
                    "AI 제공자가 이 자료의 생성을 제한했습니다. 입력 자료를 검토해 주세요. "
                    "같은 자료로 재시도해도 해결되지 않을 수 있습니다."
                    if blocked else
                    "AI 제공자가 일시적으로 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."
                    if unavailable else "선택한 모델의 생성이 실패했습니다."
                ),
                "retryable": not blocked,
                "runId": run_id,
                "errors": [{"model": model_id, "message": safe_error}],
            },
        ) from exc
    finally:
        if service:
            service.close()
    return {
        "targetId": target_id,
        "defaultModel": default_model_id(),
        "results": [result],
        "errors": [],
    }
