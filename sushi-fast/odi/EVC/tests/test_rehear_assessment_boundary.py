"""Research boundary tests. Every rubric here is synthetic TEST_ONLY, never official."""
import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import types
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError


BACKEND = Path(__file__).resolve().parents[3]


def contracts():
    return importlib.import_module("rehear_ai.contracts")


def toy_bundle():
    return contracts().RubricBundle.model_validate({
        "rubric_version": "TEST_ONLY-rubric-v1", "policy_version": "TEST_ONLY-policy-v1",
        "purpose": "TEST_ONLY", "source": "synthetic test; not an official research rubric",
        "policy": {"instructions": "TEST_ONLY: synthetic contract exercise, not a grading policy."},
        "criteria": [{"criterion_id": f"TEST_ONLY_{i:02d}", "label": f"Toy {i}",
            "definition": "TEST_ONLY placeholder, no real criterion meaning.",
            "anchors": [{"score": s, "description": f"TEST_ONLY anchor {s}"} for s in range(1, 6)]}
            for i in range(1, 17)]})


def raw_case():
    return {"source_id": "TEST_ONLY-case", "segments": [{"source_id": "segment-1", "step": 1,
        "client_time_s": 30, "segment_offset_s": 24, "transcript": "  Synthetic raw evidence.  ",
        "words": [{"word": "Synthetic", "start": .5, "end": 1.5, "confidence": .9}],
        "speech_metrics": {"duration_s": 3., "word_count": 3, "speech_rate_wps": 1.},
        "slide_index": 0, "slide_text": "Synthetic slide excerpt", "slide_text_truncated": True,
        "missing_inputs": ["gaze_delivery_score"]}], "qa_history": None,
        "omitted_source_ids": ["segment-omitted"], "truncated": True}


def pack():
    return importlib.import_module("rehear_ai.evidence").build_evidence_pack(raw_case(), source_version="TEST_ONLY-export-v1")


def factory(**kwargs):
    module = importlib.import_module("rehear_ai.factory")
    return module.create_engine(module.EngineConfig(**kwargs))


def test_rubric_ids_exactly_match_result():
    rubric, evidence = toy_bundle(), pack()
    result = factory().assess(evidence, rubric)
    validate = importlib.import_module("rehear_ai.validation").validate_assessment
    assert len(result.criteria) == 16
    assert {c.criterion_id for c in result.criteria} == {c.criterion_id for c in rubric.criteria}
    assert validate(result, evidence, rubric) == result
    for mutation in ("missing", "duplicate", "unknown"):
        bad = result.model_dump(mode="json")
        if mutation == "missing":
            bad["criteria"].pop()
        elif mutation == "duplicate":
            bad["criteria"][-1] = copy.deepcopy(bad["criteria"][0])
        else:
            bad["criteria"][-1]["criterion_id"] = "not-in-bundle"
        with pytest.raises(ValueError):
            validate(contracts().AssessmentResult.model_validate(bad), evidence, rubric)
    for kind in ("duplicate", "anchor"):
        bad = rubric.model_dump(mode="json")
        if kind == "duplicate":
            bad["criteria"][-1] = bad["criteria"][0]
        else:
            bad["criteria"][0]["anchors"][0]["score"] = 2
        with pytest.raises(ValidationError):
            contracts().RubricBundle.model_validate(bad)


@pytest.mark.parametrize("score", [True, False, 0, 6, 3.5, 3.0, "3"])
def test_score_is_strict_int_1_to_5(score):
    with pytest.raises(ValidationError):
        contracts().CriterionAssessment(criterion_id="TEST_ONLY_01", score=score,
            reason="TEST_ONLY", evidence_ids=["segment-1:transcript"], abstained=False)


def test_abstention_and_reference_validation():
    model = contracts().CriterionAssessment
    for invalid in ({"score": None, "abstained": False}, {"score": 3, "abstained": True},
                    {"score": None, "abstained": True, "abstain_reason": " "},
                    {"score": 3, "abstained": False, "abstain_reason": "missing"}):
        with pytest.raises(ValidationError):
            model(criterion_id="TEST_ONLY_01", reason="Synthetic reason", evidence_ids=[], **invalid)
    rubric, evidence = toy_bundle(), pack()
    result = factory().assess(evidence, rubric)
    bad = result.model_dump(mode="json")
    bad["criteria"][0].update(score=3, abstained=False, abstain_reason=None,
        evidence_ids=["does-not-exist"], reason="Synthetic invalid citation")
    validate = importlib.import_module("rehear_ai.validation").validate_assessment
    with pytest.raises(ValueError):
        validate(contracts().AssessmentResult.model_validate(bad), evidence, rubric)


def test_evidence_preserves_offsets_and_missing_inputs():
    evidence = pack()
    items = {item.evidence_id: item for item in evidence.items}
    transcript = items["segment-1:transcript"]
    assert transcript.payload["text"] == "  Synthetic raw evidence.  "
    assert transcript.client_time_s == 30
    words = transcript.payload["words"]
    assert words[0]["start"] == .5 and words[0]["presentation_start_s"] == 24.5
    assert transcript.payload["segment_offset_s"] == 24
    slide = items["segment-1:slide"]
    assert slide.payload["precision"] == "segment_observation_only" and slide.truncated is True
    assert {"f0", "volume", "gaze_time_series", "slide_timeline", "qa_history"} <= set(evidence.missing_inputs)
    assert evidence.coverage.truncated and evidence.coverage.omitted_source_ids == ("segment-omitted",)
    no_offset = raw_case()
    no_offset["segments"][0].pop("segment_offset_s")
    changed = importlib.import_module("rehear_ai.evidence").build_evidence_pack(no_offset, source_version="TEST_ONLY")
    assert changed.items[0].payload["words"][0]["presentation_start_s"] is None
    assert "word_presentation_offsets" in changed.missing_inputs
    with pytest.raises(ValueError):
        broken = raw_case()
        broken["segments"].append(broken["segments"][0])
        importlib.import_module("rehear_ai.evidence").build_evidence_pack(broken, source_version="TEST_ONLY")


def test_backend_adapter_reuses_raw_metrics_and_excludes_model_judgments():
    adapter = importlib.import_module("odi.EVC.assessment_adapter")
    from odi.EVC.tests.test_report_generation import segment
    from odi.EVC.schema import SpeechTextResult, SpeechWord
    record = segment(1, .5, 30)
    record.evaluation.segment_note = "SYNTHETIC_MODEL_JUDGMENT"
    stt = SpeechTextResult(transcript=record.transcript, words=[SpeechWord(word="synthetic", start=.1, end=.4)])
    result = adapter.build_evidence_pack([record], source_version="TEST_ONLY-DTO-v1",
        stt_by_step={1: stt}, segment_offsets_s={1: 27})
    dumped = result.model_dump_json()
    assert "SYNTHETIC_MODEL_JUDGMENT" not in dumped
    assert all("evc_state" not in item.payload for item in result.items)
    assert "evc_state" in result.excluded_inputs
    assert "vocal_delivery_score" not in dumped and "organization" not in dumped
    assert result.items[0].payload["words"][0]["presentation_start_s"] == 27.1
    assert any(item.payload.get("speech_rate_wps") == record.speech_metrics.speech_rate_wps for item in result.items)


def test_fake_and_core_work_without_gpu_or_openai_key(tmp_path):
    script = '''
import importlib.abc, json, sys
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','transformers','peft','openai','odi','fastapi','tools'}:
            raise ImportError('forbidden dependency: '+fullname)
sys.meta_path.insert(0,Deny())
from rehear_ai.contracts import EvidencePack, RubricBundle
from rehear_ai.factory import create_engine, EngineConfig
evidence=EvidencePack.model_validate_json(open(sys.argv[1]).read())
rubric=RubricBundle.model_validate_json(open(sys.argv[2]).read())
result=create_engine(EngineConfig()).assess(evidence,rubric)
assert len(result.criteria)==16 and result.inference.call_count==1
print(result.schema_version)
'''
    evidence_file, rubric_file = tmp_path / "evidence.json", tmp_path / "rubric.json"
    evidence_file.write_text(pack().model_dump_json())
    rubric_file.write_text(toy_bundle().model_dump_json())
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run([sys.executable, "-c", script, str(evidence_file), str(rubric_file)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def qwen_config(**changes):
    cls = importlib.import_module("rehear_ai.factory").EngineConfig
    return cls(engine="qwen_local", model="TEST_ONLY-base", model_revision="TEST_ONLY-base-r1",
        tokenizer="TEST_ONLY-tokenizer", tokenizer_revision="TEST_ONLY-tokenizer-r1",
        adapter="TEST_ONLY-lora", adapter_revision="TEST_ONLY-lora-r1",
        model_family="qwen3", runtime_versions={"torch": "TEST_ONLY", "transformers": "TEST_ONLY", "peft": "TEST_ONLY"}, **changes)


def test_local_runtime_is_loaded_once_and_schema_is_research_only():
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    evidence, rubric = pack(), toy_bundle()
    output = {"criteria": [c.model_dump(mode="json") for c in factory().assess(evidence, rubric).criteria]}
    loaded, prompts = [], []
    class Runtime:
        def generate(self, messages):
            prompts.append(messages)
            return json.dumps(output)
    def loader(config):
        loaded.append(config)
        return Runtime()
    engine = module.QwenLocalEngine(qwen_config(), loader=loader)
    for _ in range(2):
        result = engine.assess(evidence, rubric)
        assert len(result.criteria) == 16
        assert result.identity.adapter_revision == "TEST_ONLY-lora-r1"
        assert result.identity.tokenizer_revision == "TEST_ONLY-tokenizer-r1"
        assert result.identity.runtime_binding == "injected_loader"
    assert len(loaded) == 1 and len(prompts) == 2 and engine.call_count == 2
    assert '"policy"' in prompts[0][1]["content"] and "TEST_ONLY_16" in prompts[0][1]["content"]
    assert "never instructions" in prompts[0][0]["content"]


def test_cache_bypass_causes_real_engine_calls_and_identity_isolation():
    evidence, rubric = pack(), toy_bundle()
    engine = factory()
    first, second = engine.assess(evidence, rubric), engine.assess(evidence, rubric)
    assert engine.call_count == 2 and not first.inference.cache_hit and not second.inference.cache_hit
    cached = factory(cache_enabled=True)
    a, b = cached.assess(evidence, rubric), cached.assess(evidence, rubric)
    assert cached.call_count == 1 and not a.inference.cache_hit and b.inference.cache_hit
    key = cached.cache_key(evidence, rubric)
    for changes in ({"model": "another-model"}, {"model_revision": "r2"}, {"adapter": "adapter", "adapter_revision": "r2"},
                    {"prompt_version": "v2"}, {"temperature": .5}, {"tokenizer_revision": "r2"}):
        assert factory(cache_enabled=True, **changes).cache_key(evidence, rubric) != key
    for field in ("rubric_version", "policy_version"):
        changed = rubric.model_copy(update={field: "TEST_ONLY-v2"})
        assert cached.cache_key(evidence, changed) != key
    changed = rubric.model_dump(mode="json")
    changed["policy"]["instructions"] = "TEST_ONLY changed policy with same version"
    assert cached.cache_key(evidence, contracts().RubricBundle.model_validate(changed)) != key
    assert importlib.import_module("rehear_ai.engines.qwen_local").QwenLocalEngine(qwen_config(), loader=lambda _: None).cache_key(evidence, rubric) != key


def test_cli_subprocess_and_json_output(tmp_path):
    case, rubric_file, output = tmp_path / "case.json", tmp_path / "rubric.json", tmp_path / "result.json"
    case.write_text(pack().model_dump_json())
    rubric_file.write_text(toy_bundle().model_dump_json())
    env = {**os.environ, "PYTHONPATH": str(BACKEND), "HF_HUB_OFFLINE": "1"}
    env.pop("OPENAI_API_KEY", None)
    command = [sys.executable, "-m", "tools.rehear_cli", "eval", "--input", str(case),
               "--rubric", str(rubric_file), "--engine", "fake", "--output", str(output)]
    blocked = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert blocked.returncode != 0 and not output.exists()
    result = subprocess.run([*command, "--allow-test-rubric"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    parsed = contracts().AssessmentResult.model_validate_json(output.read_text())
    assert len(parsed.criteria) == 16 and parsed.inference.call_count == 1
    assert parsed.coverage.scored_criteria == 0 and parsed.coverage.abstained_criteria == 16
    assert parsed.rubric_purpose == "TEST_ONLY"
    repeated_path = tmp_path / "repeated.json"
    repeated_command = [str(repeated_path) if value == str(output) else value for value in command]
    repeated = subprocess.run([*repeated_command, "--allow-test-rubric", "--repeat", "2"], cwd=tmp_path,
        env=env, capture_output=True, text=True, timeout=20)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["call_count"] == 2
    assert contracts().AssessmentResult.model_validate_json(repeated_path.read_text()).inference.cache_enabled is False
    preserved = output.read_bytes()
    collision = subprocess.run([*command, "--allow-test-rubric"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert collision.returncode != 0 and output.read_bytes() == preserved
    output.unlink()
    case.write_text('{"invalid": "SYNTHETIC_PRIVATE_INPUT"}')
    failed = subprocess.run([*command, "--allow-test-rubric"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert failed.returncode != 0 and not output.exists()
    assert "assessment_error" in failed.stderr
    assert "SYNTHETIC_PRIVATE_INPUT" not in failed.stderr


def test_service_contract_does_not_require_research_result():
    adapter = importlib.import_module("odi.EVC.assessment_adapter")
    from odi.EVC.schema import EVCUpdateResponseV2, SessionResponseV2
    from odi.EVC.report_schema import ReportFinishResponse
    from odi.EVC.config import OPENAI_EVC_MODEL
    for cls in (EVCUpdateResponseV2, SessionResponseV2, ReportFinishResponse):
        assert not any("research" in field or "assessment" in field for field in cls.model_fields)
    assert OPENAI_EVC_MODEL == "gpt-4.1-nano" or os.getenv("OPENAI_EVC_MODEL")
    records = {}
    result = factory().assess(pack(), toy_bundle())
    adapter.store_internal_result(records, run_id="TEST_ONLY-run", result=result, evidence=pack(), rubric=toy_bundle())
    assert records["TEST_ONLY-run"]["schema_version"] == result.schema_version
    assert len(records["TEST_ONLY-run"]["criteria"]) == 16
    assert "content_metrics" not in records["TEST_ONLY-run"]


def test_tool_removal_leaves_runtime_importable(tmp_path):
    contracts()
    target = tmp_path / "isolated"
    shutil.copytree(BACKEND / "rehear_ai", target / "rehear_ai", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(BACKEND / "odi" / "EVC", target / "odi" / "EVC", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (target / "odi" / "__init__.py").touch()
    script = "from rehear_ai.factory import create_engine; from odi.EVC.assessment_adapter import build_evidence_pack; from odi.EVC.state_engine import initialize_audiences; import importlib.util; assert importlib.util.find_spec('tools') is None"
    env = {**os.environ, "PYTHONPATH": str(target)}
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_missing_local_runtime_is_explicit_and_does_not_download(monkeypatch):
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    def missing(_):
        raise module.importlib.metadata.PackageNotFoundError
    monkeypatch.setattr(module.importlib.metadata, "version", missing)
    engine = module.QwenLocalEngine(qwen_config())
    with pytest.raises(module.LocalRuntimeUnavailable, match="missing local dependency"):
        engine.assess(pack(), toy_bundle())
    assert engine.call_count == 0


def test_local_loader_passes_revisions_template_and_adapter_without_real_ml(monkeypatch, tmp_path):
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    calls = []
    class Tokens(dict):
        def __init__(self):
            super().__init__(input_ids=types.SimpleNamespace(shape=(1, 3)))
        def to(self, device):
            calls.append(("tokens_device", device))
            return self
    class Tokenizer:
        chat_template = "TEST_ONLY chat template"
        def apply_chat_template(self, messages, **kwargs):
            calls.append(("chat", kwargs))
            return Tokens()
        def decode(self, ids, **kwargs):
            assert ids == [9, 10]
            return '{"criteria": []}'
    class Model:
        config = types.SimpleNamespace(model_type="qwen3")
        def to(self, **kwargs):
            calls.append(("model_device", kwargs))
        def eval(self):
            calls.append(("eval",))
        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            return [[1, 2, 3, 9, 10]]
    class AutoTokenizer:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("tokenizer", path, kwargs))
            return Tokenizer()
    class AutoModel:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("model", path, kwargs))
            return Model()
    class Peft:
        @staticmethod
        def from_pretrained(model, path, **kwargs):
            calls.append(("adapter", path, kwargs))
            return model
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(inference_mode=nullcontext, float32="TEST_ONLY-float32"))
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(AutoTokenizer=AutoTokenizer, AutoModelForCausalLM=AutoModel))
    monkeypatch.setitem(sys.modules, "peft", types.SimpleNamespace(PeftModel=Peft))
    monkeypatch.setattr(module.importlib.metadata, "version", lambda _: "TEST_ONLY")
    paths = {}
    for name in ("model", "tokenizer", "adapter"):
        path = tmp_path / name
        path.mkdir()
        paths[name] = str(path)
    config = qwen_config().model_copy(update=paths)
    runtime = module.load_transformers_runtime(config)
    assert runtime.generate([{ "role": "user", "content": "TEST_ONLY"}]) == '{"criteria": []}'
    for kind, revision in (("model", config.model_revision), ("tokenizer", config.tokenizer_revision), ("adapter", config.adapter_revision)):
        call = next(c for c in calls if c[0] == kind)
        assert call[2]["revision"] == revision and call[2]["local_files_only"] is True
        if kind != "adapter":
            assert call[2]["trust_remote_code"] is False
    chat = next(c for c in calls if c[0] == "chat")[1]
    assert chat["enable_thinking"] is False and chat["add_generation_prompt"] is True
    generated = next(c for c in calls if c[0] == "generate")[1]
    assert generated["do_sample"] is False and generated["max_new_tokens"] == config.max_new_tokens
    assert generated["max_time"] == config.timeout_s


def test_invalid_model_output_is_not_cached_and_errors_do_not_echo_source():
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    outputs = ['{"criteria": []}', "SYNTHETIC_PRIVATE_MODEL_OUTPUT"]
    class Runtime:
        def generate(self, _):
            return outputs.pop(0)
    engine = module.QwenLocalEngine(qwen_config(cache_enabled=True), loader=lambda _: Runtime())
    for _ in range(2):
        with pytest.raises(ValueError):
            engine.assess(pack(), toy_bundle())
    assert engine.call_count == 2 and not engine._cache
    class FailingRuntime:
        def generate(self, _):
            raise ValueError("SYNTHETIC_PRIVATE_UPSTREAM_INPUT")
    engine = module.QwenLocalEngine(qwen_config(), loader=lambda _: FailingRuntime())
    with pytest.raises(importlib.import_module("rehear_ai.engines.base").AssessmentEngineError) as error:
        engine.assess(pack(), toy_bundle())
    assert "SYNTHETIC_PRIVATE" not in str(error.value)


@pytest.mark.parametrize("field", ["organization", "vocal_delivery_score", "message_clarity"])
def test_neutral_export_rejects_model_judgments_as_measurements(field):
    raw = raw_case()
    raw["segments"][0]["speech_metrics"][field] = .5
    with pytest.raises(ValueError):
        importlib.import_module("rehear_ai.evidence").build_evidence_pack(raw, source_version="TEST_ONLY")


def test_rubric_content_and_evidence_integrity_and_explicit_qa():
    evidence, rubric = pack(), toy_bundle()
    result = factory().assess(evidence, rubric)
    validate = importlib.import_module("rehear_ai.validation").validate_assessment
    changed = rubric.model_dump(mode="json")
    changed["criteria"][0]["definition"] = "TEST_ONLY altered definition, same version"
    with pytest.raises(ValueError):
        validate(result, evidence, contracts().RubricBundle.model_validate(changed))
    case = raw_case()
    case["qa_history"] = [{"source_id": "qa-1", "question": "Synthetic question?", "answer": None}]
    exported = importlib.import_module("rehear_ai.evidence").build_evidence_pack(case, source_version="TEST_ONLY")
    assert "qa_history" not in exported.missing_inputs and "qa_answer" in exported.missing_inputs
    assert exported.coverage.available_sources == 2
    with pytest.raises(ValueError):
        validate(result, exported, rubric)


def test_pipeline_dto_to_evidence_fake_and_internal_store_without_public_projection(tmp_path):
    import asyncio
    from odi.EVC.pipeline import create_pipeline_session, update_pipeline, read_pipeline_session
    from odi.EVC.schema import SmartStartOptions, SegmentContext
    from odi.EVC.session_store import SessionStore
    from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider
    adapter = importlib.import_module("odi.EVC.assessment_adapter")
    async def run():
        store = SessionStore()
        started = await create_pipeline_session(SmartStartOptions(presentation_title="TEST_ONLY export", seed=2026), store=store)
        await update_pipeline(session_id=started.session_id, token=started.session_token, request_id=uuid4(), expected_step=0,
            context=SegmentContext(client_time_s=30), audio_path=tmp_path / "unused.wav", stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(), store=store)
        record = await store.get_authorized_session(started.session_id, started.session_token)
        exported = adapter.build_evidence_pack(record.report_segments, source_version="TEST_ONLY-EVC-v1",
            stt_by_step={1: STTProvider().transcribe("unused", "ko-KR")}, segment_offsets_s={1: 27})
        result = factory().assess(exported, toy_bundle())
        internal = {}
        adapter.store_internal_result(internal, run_id="TEST_ONLY-run", result=result, evidence=exported, rubric=toy_bundle())
        assert internal["TEST_ONLY-run"]["evidence_digest"] == result.evidence_digest
        read = await read_pipeline_session(started.session_id, started.session_token, store=store)
        assert "assessment" not in read.model_dump() and record.report_feedback is None
        assert record.report_segments[0].client_time_s == 30
    asyncio.run(run())


def test_local_engine_rejects_concurrent_work_until_generation_finishes():
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    base = importlib.import_module("rehear_ai.engines.base")
    evidence, rubric = pack(), toy_bundle()
    output = {"criteria": [c.model_dump(mode="json") for c in factory().assess(evidence, rubric).criteria]}
    entered, release = threading.Event(), threading.Event()
    class Runtime:
        def generate(self, _):
            entered.set()
            release.wait(3)
            return output
    engine = module.QwenLocalEngine(qwen_config(), loader=lambda _: Runtime())
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(engine.assess, evidence, rubric)
        try:
            assert entered.wait(1)
            with pytest.raises(base.AssessmentEngineError, match="already loading or generating"):
                engine.assess(evidence, rubric)
        finally:
            release.set()
        assert future.result(timeout=2).inference.call_count == 1


def test_local_retry_calls_generation_again_without_reloading():
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    evidence, rubric = pack(), toy_bundle()
    output = {"criteria": [c.model_dump(mode="json") for c in factory().assess(evidence, rubric).criteria]}
    outputs = [{"criteria": []}, output]
    loads = []
    class Runtime:
        def generate(self, _):
            return outputs.pop(0)
    def loader(_):
        loads.append(1)
        return Runtime()
    engine = module.QwenLocalEngine(qwen_config(retries=1), loader=loader)
    result = engine.assess(evidence, rubric)
    assert len(loads) == 1 and engine.call_count == result.inference.call_count == 2


@pytest.mark.parametrize("retries", [0, 1])
def test_late_local_output_is_rejected_and_not_cached(monkeypatch, retries):
    module = importlib.import_module("rehear_ai.engines.qwen_local")
    base = importlib.import_module("rehear_ai.engines.base")
    evidence, rubric = pack(), toy_bundle()
    output = {"criteria": [c.model_dump(mode="json") for c in factory().assess(evidence, rubric).criteria]}
    clock = [10.]
    monkeypatch.setattr(base, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    class Runtime:
        def generate(self, _):
            clock[0] += 5
            return output
    engine = module.QwenLocalEngine(qwen_config(timeout_s=2, cache_enabled=True, retries=retries), loader=lambda _: Runtime())
    with pytest.raises(base.AssessmentEngineError, match="deadline"):
        engine.assess(evidence, rubric)
    assert engine.call_count == 1 and not engine._cache
