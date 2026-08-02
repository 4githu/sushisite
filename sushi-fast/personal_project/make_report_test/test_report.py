from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import DEFAULT_CACHE_TTL_SECONDS, DEFAULT_MODEL
from .db_repository import (
    build_report_input,
    find_target_id,
    finish_run,
    get_active_score_format,
    get_score_mode,
    migrate,
    normalize_report_input,
    save_generated_score_format,
    set_score_mode,
    set_run_cache_mode,
    set_run_score_format,
    start_run,
)
from .gemini_report_service import GeminiReportService


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="아우라 Gemini 클리닉 리포트 생성 테스트")
    source = result.add_mutually_exclusive_group()
    source.add_argument("--target-id", type=int, help="기존 aura_round_targets.id")
    source.add_argument("--input-json", type=Path, help="아우라 클리닉 입력 JSON 파일")
    result.add_argument("--student-name", default="경승현", help="target-id 생략 시 찾을 학생")
    result.add_argument("--round-number", type=int, default=6, help="target-id 생략 시 찾을 회차")
    result.add_argument(
        "--score-mode",
        choices=("auto", "none"),
        help="auto=기존 학교 양식 재사용/없으면 생성, none=평가 없이 학습 내용만",
    )
    result.add_argument("--model", default=DEFAULT_MODEL)
    result.add_argument("--no-cache", action="store_true", help="진단용: 명시적 캐시를 사용하지 않음")
    result.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL_SECONDS)
    result.add_argument("--api-key", help="권장하지 않음: 쉘 기록에 키가 남을 수 있음")
    result.add_argument("--output", type=Path, help="응답을 저장할 UTF-8 JSON 파일")
    result.add_argument("--dry-run", action="store_true", help="API 호출 없이 입력과 DB만 확인")
    return result


def main() -> int:
    args = parser().parse_args()
    migrate()
    target_id = args.target_id
    if target_id is None and args.input_json is None:
        target_id = find_target_id(args.student_name, args.round_number)
        print(f"테스트 대상 자동 선택: {args.student_name} {args.round_number}회차 (target-id={target_id})")
    raw_input = (
        json.loads(args.input_json.read_text(encoding="utf-8"))
        if args.input_json is not None
        else build_report_input(target_id)
    )
    if not isinstance(raw_input, dict):
        raise ValueError("입력 JSON의 최상위 값은 객체여야 합니다.")
    report_input = normalize_report_input(raw_input)
    input_score_mode = (report_input.get("options") or {}).get("scoreMode")
    if input_score_mode not in {None, "auto", "none"}:
        raise ValueError("input.options.scoreMode은 auto 또는 none이어야 합니다.")
    score_mode = args.score_mode or input_score_mode or get_score_mode(report_input)
    if args.score_mode:
        set_score_mode(report_input, score_mode)
    score_format = get_active_score_format(report_input) if score_mode == "auto" else None
    prompt = GeminiReportService.read_prompt()
    prompt_hash = GeminiReportService.prompt_hash(prompt)
    mode = "implicit" if args.no_cache else "explicit"
    if args.dry_run:
        print("[DRY RUN]")
        cache_label = "disabled" if args.no_cache else "auto(explicit -> implicit fallback)"
        print(f"model={args.model}, cache={cache_label}, prompt_sha256={prompt_hash}")
        print(json.dumps(report_input, ensure_ascii=False, indent=2))
        print(f"score_mode={score_mode}, score_format={score_format or '새로 생성'}")
        return 0
    run_id = start_run(
        target_id,
        args.model,
        mode,
        prompt_hash,
        input_json=report_input,
        score_mode=score_mode,
        score_format_id=score_format["id"] if score_format else None,
    )
    service = None
    try:
        service = GeminiReportService(
            api_key=args.api_key,
            model=args.model,
            explicit_cache=not args.no_cache,
            cache_ttl_seconds=args.cache_ttl,
        )
        report, _ = service.generate(
            report_input=report_input,
            score_mode=score_mode,
            score_format=score_format,
        )
        if score_mode == "auto" and score_format is None and report.get("assessment"):
            assessment = report["assessment"]
            format_id = save_generated_score_format(
                report_input,
                str(assessment.get("formatName") or "기본 평가 양식"),
                [str(item.get("name", "")) for item in assessment.get("items", [])],
            )
            if format_id is not None:
                report["assessment"]["formatId"] = format_id
                set_run_score_format(run_id, format_id)
        set_run_cache_mode(run_id, service.last_cache_mode)
        finish_run(run_id, response_json=report)
        if service.cache_notice:
            print(f"캐시 안내: {service.cache_notice}", file=sys.stderr)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"리포트 저장 완료: {args.output}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        finish_run(run_id, error=str(exc))
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    finally:
        if service:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
