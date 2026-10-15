"""CLI-only orchestration. Summaries contain no source text."""
import importlib.metadata
import json
import platform
import time
from uuid import uuid4

from rehear_ai.contracts import AssessmentResult, EvidencePack, RubricBundle
from rehear_ai.factory import EngineConfig, create_engine
from rehear_ai.validation import digest, validate_assessment


def environment():
    versions = {}
    for name in ("pydantic", "torch", "transformers", "peft"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"status": "offline_environment_only", "python": platform.python_version(),
        "packages": versions, "model_loaded": False, "real_model_verified": False}


def contract_schemas():
    return {"status": "schemas_only_not_official_rubric", "schemas": {
        cls.__name__: cls.model_json_schema() for cls in (EvidencePack, RubricBundle, AssessmentResult)}}


def load_inputs(args):
    text = args.input.read_text(encoding="utf-8")
    if args.input_format == "legacy-post":
        from .legacy_cases import post_presentation_case
        evidence = post_presentation_case(json.loads(text))
    else:
        evidence = EvidencePack.model_validate_json(text)
    rubric = RubricBundle.model_validate_json(args.rubric.read_text(encoding="utf-8"))
    if rubric.purpose == "TEST_ONLY" and not args.allow_test_rubric:
        raise ValueError("TEST_ONLY rubric requires explicit flag")
    return evidence, rubric


def config_from(path=None, engine=None, *, cache_off=False):
    raw = json.loads(path.read_text(encoding="utf-8")) if path else {}
    if not isinstance(raw, dict):
        raise ValueError("engine config must be a JSON object")
    if engine:
        raw["engine"] = engine
    if cache_off:
        raw["cache_enabled"] = False
    return EngineConfig.model_validate(raw)


def metadata(evidence, rubric, config=None):
    return {"run_id": str(uuid4()), "task": "research16", "input_hash": digest(evidence),
        "rubric_version": rubric.rubric_version, "rubric_digest": digest(rubric),
        "policy_version": rubric.policy_version, "policy_digest": digest(rubric.policy),
        "rubric_purpose": rubric.purpose,
        "engine": config.engine if config else "offline_replay",
        "model": config.model if config else None, "adapter": config.adapter if config else None,
        "prompt_version": config.prompt_version if config else None,
        "cache_enabled": config.cache_enabled if config else False,
        "settings": config.model_dump(mode="json") if config else None,
        "call_count": 0, "retry_count": 0, "cache_hits": 0, "failures": 0, "elapsed_s": 0.0,
        "status": "offline_replay" if config is None else "fake_contract_only" if config.engine == "fake"
                  else "local_generation_completed_not_quality_verified",
        "real_model_verified": False}


def replay(args, evidence, rubric):
    started = time.perf_counter()
    meta = metadata(evidence, rubric)
    if args.result:
        result = AssessmentResult.model_validate_json(args.result.read_text(encoding="utf-8"))
        validate_assessment(result, evidence, rubric)
        if result.evidence_digest != digest(evidence) or result.rubric_digest != digest(rubric):
            raise ValueError("replay result provenance differs")
        meta["validated_result_hash"] = digest(result)
    meta.update(elapsed_s=time.perf_counter() - started, criterion_count=len(rubric.criteria),
                evidence_count=len(evidence.items), reference_check="existence_only_not_semantic_support")
    return {"metadata": meta, "results": []}


def assess_run(evidence, rubric, config, *, repeat=1, bench=False):
    started = time.perf_counter()
    meta = metadata(evidence, rubric, config)
    engine = create_engine(config)
    results, timings = [], []
    try:
        if bench:
            cold = time.perf_counter()
            # CLI owns this new instance; no concurrent inference can be active.
            meta["load_kind"] = "no_model_fake" if config.engine == "fake" else "local_model_load"
            meta["load_completed"] = False
            try:
                engine._prepare()
                meta["load_completed"] = True
            finally:
                meta["cold_load_s"] = time.perf_counter() - cold
        for _ in range(repeat):
            calls_before = engine.call_count
            inference_started = time.perf_counter()
            try:
                result = engine.assess(evidence, rubric)
                meta["cache_hits"] += int(result.inference.cache_hit)
                results.append(result.model_dump(mode="json"))
                timings.append(time.perf_counter() - inference_started)
            finally:
                meta["retry_count"] += max(0, engine.call_count - calls_before - 1)
    except Exception as exc:
        meta.update(failures=1, status="assessment_error", error_type=type(exc).__name__)
    meta.update(call_count=engine.call_count, elapsed_s=time.perf_counter() - started,
                failed_attempts=engine.call_count - (len(results) - meta["cache_hits"]),
                completed=len(results), requested=repeat, identity=engine.identity.model_dump(mode="json"))
    meta["local_generation_executed"] = config.engine == "qwen_local" and bool(results)
    if bench:
        meta.update(first_generation_s=timings[0] if timings else None, warm_generation_s=timings[1:],
                    generation_timing="assess wall time including validation/retries; excludes prior cold load")
    return {"metadata": meta, "results": results}


def execute(args):
    evidence, rubric = load_inputs(args)
    document = {"schema_version": "research-run.v1", "task": "research16", "run_id": str(uuid4()),
                "input_hash": digest(evidence), "runs": []}
    if args.command == "replay":
        document["runs"].append(replay(args, evidence, rubric))
    else:
        repeat = args.repeat
        if not 1 <= repeat <= 100 or (args.command == "bench" and repeat < 2):
            raise ValueError("repeat must be 1–100; bench needs at least two generations")
        cache_off = args.command in {"repeat", "compare", "bench"} or repeat > 1
        config = config_from(args.config, args.engine, cache_off=cache_off)
        configs = [config]
        if args.command == "compare":
            other_engine = args.other_engine or (args.engine if args.other_config is None else None)
            configs.append(config_from(args.other_config, other_engine, cache_off=True))
        document["runs"] = [assess_run(evidence, rubric, item, repeat=repeat, bench=args.command == "bench") for item in configs]
        if args.command == "compare":
            document["comparison"] = {"same_task": True, "task": "research16",
                "same_input_hash": True, "same_rubric_digest": True,
                "quality_verified": False, "note": "same task contract; no expert accuracy claim"}
            if all(run["results"] for run in document["runs"]):
                left, right = [{c["criterion_id"]: c["score"] for c in run["results"][-1]["criteria"]}
                               for run in document["runs"]]
                document["comparison"]["criteria"] = [{"criterion_id": c.criterion_id,
                    "left_score": left[c.criterion_id], "right_score": right[c.criterion_id],
                    "equal_when_both_scored": left[c.criterion_id] == right[c.criterion_id]
                        if left[c.criterion_id] is not None and right[c.criterion_id] is not None else None}
                    for c in rubric.criteria]
    return document


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
