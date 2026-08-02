from __future__ import annotations

import argparse
import json
from pathlib import Path

from personal_project.ai_report import generate
from personal_project.make_report_test.db_repository import build_report_input
from personal_project.make_report_test.model_registry import model_options


def main() -> int:
    parser = argparse.ArgumentParser(description="동일 아우라 JSON의 모델별 결과 비교")
    parser.add_argument("--target-id", type=int, default=57)
    parser.add_argument(
        "--models",
        nargs="+",
        default=[item["id"] for item in model_options()],
    )
    parser.add_argument("--score-mode", choices=("auto", "none"), default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "model-comparison",
    )
    args = parser.parse_args()
    report_input = build_report_input(args.target_id)
    user_id = int(report_input["target"]["userId"])
    response = generate(
        user_id,
        args.target_id,
        models=args.models,
        score_mode=args.score_mode,
        force=args.force,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for result in response["results"]:
        path = args.output_dir / f"{result['model']}.json"
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{result['model']}: {path} ({'DB 재사용' if result['reused'] else '새 생성'})")
    manifest = args.output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(response, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if response["errors"]:
        print(json.dumps(response["errors"], ensure_ascii=False, indent=2))
    return 0 if response["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
