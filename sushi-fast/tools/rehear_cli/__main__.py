import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .runs import contract_schemas, environment, execute, write_json


def parser():
    cli = argparse.ArgumentParser(description="Independent Research16 tools; fake does not score presentations")
    commands = cli.add_subparsers(dest="command", required=True)
    for command in ("doctor", "contracts"):
        commands.add_parser(command).add_argument("--output", type=Path)
    for command in ("eval", "repeat", "compare", "replay", "bench"):
        sub = commands.add_parser(command)
        for name in ("input", "rubric", "output"):
            sub.add_argument("--" + name, type=Path, required=True)
        sub.add_argument("--allow-test-rubric", action="store_true")
        sub.add_argument("--input-format", choices=("evidence", "legacy-post"), default="evidence")
        if command == "replay":
            sub.add_argument("--result", type=Path, help="validate an existing result without inference")
        else:
            sub.add_argument("--engine", choices=("fake", "qwen_local"))
            sub.add_argument("--config", type=Path)
            sub.add_argument("--repeat", type=int, default=3 if command in {"repeat", "bench"} else 1)
        if command == "compare":
            sub.add_argument("--other-engine", choices=("fake", "qwen_local"))
            sub.add_argument("--other-config", type=Path)
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        metadata_path = args.output.with_suffix(args.output.suffix + ".run.json") if args.command == "eval" else None
        if args.output and (args.output.exists() or (metadata_path and metadata_path.exists())):
            raise ValueError("output already exists")
        if args.command in {"doctor", "contracts"}:
            document = environment() if args.command == "doctor" else contract_schemas()
            if args.output:
                write_json(args.output, document)
            print(json.dumps(document, ensure_ascii=False))
            return 0
        document = execute(args)
        failed = any(run["metadata"]["failures"] for run in document["runs"])
        first = document["runs"][0]
        meta = first["metadata"]
        if args.command == "eval":
            # Retain stage03's AssessmentResult file contract; run data is a sidecar.
            write_json(metadata_path, {**document, "runs": [{"metadata": r["metadata"]} for r in document["runs"]]})
            if not failed:
                write_json(args.output, first["results"][-1])
        else:
            write_json(args.output, document)
        summary = {"status": "assessment_error" if failed else meta["status"], "task": "research16",
            "run_id": document["run_id"], "input_hash": document["input_hash"],
            "call_count": sum(r["metadata"]["call_count"] for r in document["runs"]),
            "cache_enabled": meta["cache_enabled"], "rubric_purpose": meta["rubric_purpose"],
            "criterion_count": 16, "repeat": getattr(args, "repeat", 0),
            "failures": sum(r["metadata"]["failures"] for r in document["runs"])}
        if failed:
            summary["error_type"] = next(r["metadata"]["error_type"] for r in document["runs"] if r["metadata"]["failures"])
        print(json.dumps(summary), file=sys.stderr if failed else sys.stdout)
        return 2 if failed else 0
    except (ValueError, OSError, ImportError, KeyError, TypeError, IndexError) as exc:
        error = {"status": "assessment_error", "error_type": type(exc).__name__,
                 "message": "input/output, contract or optional runtime unavailable; no raw input is logged"}
        if isinstance(exc, ValidationError):
            error["locations"] = [list(item["loc"]) for item in exc.errors(include_input=False)]
        print(json.dumps(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
