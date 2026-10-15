import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from rehear_ai.contracts import EvidencePack, RubricBundle
from rehear_ai.factory import EngineConfig, create_engine
from rehear_ai.engines.base import AssessmentEngineError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent Research16 assessment; fake is not a scoring model")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("eval")
    for name in ("input", "rubric", "output"):
        evaluate.add_argument("--" + name, type=Path, required=True)
    evaluate.add_argument("--engine", choices=("fake", "qwen_local"))
    evaluate.add_argument("--config", type=Path)
    evaluate.add_argument("--allow-test-rubric", action="store_true")
    evaluate.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.repeat <= 100:
            raise ValueError("repeat must be 1–100")
        if args.output.exists():
            raise ValueError("output already exists; choose a new result path")
        evidence = EvidencePack.model_validate_json(args.input.read_text(encoding="utf-8"))
        rubric = RubricBundle.model_validate_json(args.rubric.read_text(encoding="utf-8"))
        if rubric.purpose == "TEST_ONLY" and not args.allow_test_rubric:
            raise ValueError("TEST_ONLY rubric requires --allow-test-rubric; it is not official research data")
        raw_config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
        if not isinstance(raw_config, dict):
            raise ValueError("engine config must be a JSON object")
        if args.engine is not None:
            raw_config["engine"] = args.engine
        engine = create_engine(EngineConfig.model_validate(raw_config))
        for _ in range(args.repeat):
            result = engine.assess(evidence, rubric)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as target:
            target.write(result.model_dump_json(indent=2) + "\n")
        print(json.dumps({"status": "fake_contract_only" if engine.config.engine == "fake" else "local_generation_completed_not_quality_verified",
            "schema_version": result.schema_version, "criterion_count": len(result.criteria),
            "call_count": engine.call_count, "repeat": args.repeat, "cache_enabled": engine.config.cache_enabled,
            "rubric_purpose": rubric.purpose, "output": str(args.output)}, ensure_ascii=False))
        return 0
    except (ValidationError, ValueError, OSError, AssessmentEngineError, ImportError) as exc:
        if isinstance(exc, ValidationError):
            error = {"message": "input/result contract validation failed",
                "locations": [list(item["loc"]) for item in exc.errors(include_input=False)]}
        elif isinstance(exc, (OSError, ImportError)):
            error = {"message": "input/output or optional runtime unavailable; verify paths and pinned dependencies"}
        else:
            error = {"message": str(exc)}
        print(json.dumps({"status": "assessment_error", "error_type": type(exc).__name__, **error}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
