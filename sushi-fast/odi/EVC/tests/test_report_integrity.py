"""Stage 04: synthetic evidence, isolated SQLite, no provider/network calls."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from odi.db import odidb
from odi.EVC.report_v2.report_aggregation import aggregate_report
from odi.EVC.report_v2.report_generation import generate_report_insight, ReportInsightProviderError
from odi.EVC.report_v2.report_service import _apply_metric_narratives
from odi.EVC.report_schema import AIInsight, AIInsightItem, DetailMetricNarrative, ReportNarrativeOutput
from odi.EVC.report_metric_catalog import DETAIL_METRIC_SPECS
from odi.EVC.tests.test_report_generation import segment


def metric(report, name):
    return next(m for m in report.detail_analysis.delivery_metrics if m.id == name)


def missing_gaze(step=1):
    value = segment(step, 0, step * 5)
    value.evaluation.missing_inputs = ["gaze_delivery_score"]
    return value


def narrative():
    return ReportNarrativeOutput(ai_insight=AIInsight(title="합성", description="계약 검사"),
        metric_narratives=[DetailMetricNarrative(id=s.id, reason="측정된 결과입니다.",
            coaching="측정값을 개선하세요.", evidence_ids=["segment-1"]) for s in DETAIL_METRIC_SPECS])


def test_all_missing_gaze_is_null_not_fifty():
    source = missing_gaze()
    report = aggregate_report(segments=[source])
    gaze = metric(report, "gaze")
    assert gaze.score is None and gaze.coaching is None and gaze.evidence_ids == []
    assert "수집" in gaze.reason
    assert source.evaluation.delivery.gaze_delivery == 0  # realtime neutral unchanged


def test_partial_gaze_coverage_is_explicit():
    report = aggregate_report(segments=[missing_gaze(), segment(2, .8, 10)])
    gaze = metric(report, "gaze")
    assert gaze.score == 90  # use observed segments only, never impute missing to 50
    assert gaze.evidence_ids == ["segment-2"]
    assert "1/2" in gaze.reason
    assert "gaze_coverage:1/2:valid_segments_only" in report.generation.warnings
    _apply_metric_narratives(report, narrative())
    assert "1/2" in metric(report, "gaze").reason


def test_unmeasured_pronunciation_reason_not_overwritten():
    report = aggregate_report(segments=[segment(1, .5, 5)])
    before = metric(report, "pronunciation").model_dump()
    _apply_metric_narratives(report, narrative())
    assert metric(report, "pronunciation").model_dump() == before
    assert metric(report, "gaze").reason == "측정된 결과입니다."  # fully measured narratives still work


def test_report_cache_isolated_between_providers():
    class Provider:
        model = "same-model"
        def __init__(self, label): self.label, self.calls = label, 0
        def generate(self, payload):
            self.calls += 1
            return AIInsight(title=self.label, description="합성")
    async def run():
        a, b = Provider("A"), Provider("B")
        payload = {"segments": [{"evidence_id": "segment-1"}]}
        assert (await generate_report_insight(payload, provider=a)).title == "A"
        assert (await generate_report_insight(payload, provider=b)).title == "B"
        await generate_report_insight(payload, provider=b)
        assert a.calls == b.calls == 1
        b.policy_version = "changed"
        await generate_report_insight(payload, provider=b)
        assert b.calls == 2
    asyncio.run(run())


def test_invalid_reference_rejected_and_failure_visible():
    class Provider:
        def generate(self, payload):
            return AIInsight(title="합성", description="잘못된 참조", strengths=[AIInsightItem(
                title="합성", description="합성", action="합성", evidence_ids=["absent"])])
    async def run():
        with pytest.raises(ReportInsightProviderError, match="invalid_evidence_reference"):
            await generate_report_insight({"segments": [{"evidence_id": "segment-1"}]},
                provider=Provider(), retries=0)
        from odi.EVC.report_service import finish_session_with_report
        from odi.EVC.report_schema import ReportFinishRequest
        from odi.EVC.tests.test_answer_service import setup
        store, record, token = await setup(1)
        record.report_segments = [segment(1, .5, 5)]
        result = await finish_session_with_report(session_id=record.session_id, token=token,
            payload=ReportFinishRequest(request_id=uuid4()), provider=Provider(), store=store)
        assert "ai_insight_fallback" in result.report.generation.warnings
        assert result.report.generation.generator == "deterministic-v2"
    asyncio.run(run())


def bind_db(monkeypatch, path):
    from odi.EVC.tests.test_report_followup import init_test_db, create_linked_pre_session
    init_test_db(path)
    template, pin = create_linked_pre_session(path)
    odidb.claim_pre_session(pin, db_path=path)
    # Existing repository injects db_path at these storage seams.
    names = ["upsert_presentation_segment", "list_presentation_segments", "list_presentation_reactions",
        "get_pre_session_by_pin", "get_template", "get_evc_session_id_by_pre_session_pin",
        "start_report_job", "finish_linked_pre_session", "fail_report_job",
        "save_presentation_qa", "get_presentation_qa"]
    for name in names:
        original = getattr(odidb, name)
        def bound(*args, _fn=original, **kwargs):
            return _fn(*args, **{**kwargs, "db_path": path})
        monkeypatch.setattr(odidb, name, bound)
    return template, pin


def test_recovery_restores_qa_and_order(monkeypatch, tmp_path):
    async def run():
        from odi.EVC.tests.test_answer_service import setup, wav, Provider
        from odi.EVC.answer_service import submit_answer
        from odi.EVC.qa_persistence import restore_qa_state
        from odi.EVC.report_service import recover_pre_session_report
        template, pin = bind_db(monkeypatch, tmp_path / "qa.db")
        store, record, token = await setup(2)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        odidb.upsert_presentation_segment(evc_session_id=str(record.session_id), step=1,
            segment=segment(1, .5, 5).model_dump(mode="json"), owner_user_id="owner", pre_session_pin=pin)
        async def stt(_): return "합성 답변"
        provider = Provider()
        for index in range(2):
            await submit_answer(session_id=record.session_id, token=token, index=index,
                request_id=uuid4(), audio=wav(), transcriber=stt, provider=provider, store=store,
                next_audience_id="audience_02" if index == 0 else "")
        expected_questions = [q.model_dump() for q in record.generated_questions]
        expected_answers = copy.deepcopy(record.qa_answers)
        record.generated_questions, record.qa_answers = [], {}
        restore_qa_state(record)
        assert [q.model_dump() for q in record.generated_questions] == expected_questions
        assert record.qa_answers == expected_answers
        assert record.qa_answers[0]["question_id"] == "q1"
        assert record.qa_answers[0]["source_steps"] == [1]
        assert record.qa_answers[1]["audience_id"] == "audience_02"
        with pytest.raises(PermissionError):
            odidb.get_presentation_qa(str(record.session_id), owner_user_id="attacker", pre_session_pin=pin)
        await store.delete_session(record.session_id, token)
        result = await recover_pre_session_report(pin_code=pin, owner_user_id="owner", request_id=uuid4())
        assert [h.answer for h in result.report.qa_history] == ["합성 답변"] * 2
        assert [h.question_index for h in result.report.qa_history] == [0, 1]
        assert result.report.qa_feedback.questions[1].question == expected_questions[1]["question"]
    asyncio.run(run())


def test_qa_retry_is_idempotent(monkeypatch, tmp_path):
    async def run():
        from odi.EVC.tests.test_answer_service import setup, wav, Provider
        from odi.EVC.answer_service import submit_answer
        template, pin = bind_db(monkeypatch, tmp_path / "retry.db")
        store, record, token = await setup(2)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        provider = Provider()
        async def stt(_): return "합성 답변"
        args = dict(session_id=record.session_id, token=token, index=0, request_id=uuid4(),
            audio=wav(), transcriber=stt, provider=provider, store=store, next_audience_id="audience_02")
        original = odidb.save_presentation_qa
        failed = False
        def fail_commit(**kwargs):
            nonlocal failed
            if any(a.get("response") for a in kwargs["state"]["answers"].values()) and not failed:
                failed = True
                raise OSError("synthetic commit failure")
            return original(**kwargs)
        monkeypatch.setattr(odidb, "save_presentation_qa", fail_commit)
        with pytest.raises(OSError): await submit_answer(**args)
        assert not record.qa_answers[0].get("response")
        assert record.generated_questions[1].question == "기존 질문 2?"
        first = await submit_answer(**args)
        assert await submit_answer(**args) == first
        assert len(provider.payloads) == 1
        state = odidb.get_presentation_qa(str(record.session_id), owner_user_id="owner", pre_session_pin=pin)
        assert len(state["answers"]) == 1 and state["answers"]["0"]["response"] == first
    asyncio.run(run())


def test_db_failure_does_not_advance_step_without_committed_response(monkeypatch):
    async def run():
        from odi.EVC.pipeline import update_pipeline as update_pipeline_session, create_pipeline_session
        from odi.EVC.schema import SmartStartOptions, SegmentContext
        from odi.EVC.session_store import SessionStore
        from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider
        store = SessionStore()
        started = await create_pipeline_session(SmartStartOptions(presentation_title="합성", seed=7), store=store)
        record = await store.get_authorized_session(started.session_id, started.session_token)
        record.pre_session_pin = "synthetic"
        before = [a.model_dump() for a in record.audiences]
        rng = {key: value.getstate() for key, value in record.rngs.items()}
        saved = []
        def fail(**kwargs): raise OSError("synthetic commit failure")
        monkeypatch.setattr(odidb, "upsert_presentation_segment", fail)
        args = dict(session_id=record.session_id, token=started.session_token, request_id=uuid4(),
            expected_step=0, context=SegmentContext(client_time_s=5, current_slide_index=0),
            audio_path=Path("synthetic-unused.wav"), stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(), store=store)
        with pytest.raises(OSError): await update_pipeline_session(**args)
        assert record.step == 0 and not record.request_cache and not record.report_segments
        assert not record.transcript_segments and not record.segment_notes
        assert [a.model_dump() for a in record.audiences] == before
        assert {key: value.getstate() for key, value in record.rngs.items()} == rng
        monkeypatch.setattr(odidb, "upsert_presentation_segment", lambda **kw: saved.append(kw))
        first = await update_pipeline_session(**args)
        assert await update_pipeline_session(**args) == first
        assert record.step == 1 and len(saved) == len(record.report_segments) == 1
    asyncio.run(run())


def test_migrated_case_and_measurement_inventory():
    from tools.rehear_cli.migration import PRIVATE_ROOT, verify_inventory
    root = Path(__file__).resolve().parents[4]
    manifest = root / "docs/rehear-ai/legacy-benchmark-inventory.json"
    inventory = json.loads(manifest.read_text())
    assert len(inventory["files"]) == 127
    assert {f["category"] for f in inventory["files"]} >= {"case", "historical_result", "measurement_definition"}
    # The private archive is intentionally absent from public checkouts.
    if (root / PRIVATE_ROOT).exists():
        assert verify_inventory(root, manifest)["verified_files"] == 127


def test_cli_delete_does_not_break_product(tmp_path):
    import shutil
    root = Path(__file__).resolve().parents[3]
    for name in ("rehear_ai", "odi"):
        shutil.copytree(root / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONPYCACHEPREFIX": str(tmp_path / "bytecode")}
    code = "from rehear_ai.factory import create_engine; from odi.EVC import pipeline, answer_service; from odi.EVC.report_service import recover_pre_session_report"
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert not (tmp_path / "tools").exists()
    excluded = {"test_report_integrity.py", "test_rehear_assessment_boundary.py",
                "test_audience_count_contract.py", "test_playback_freshness.py"}
    paths = [str(p.relative_to(tmp_path)) for p in sorted((tmp_path / "odi/EVC/tests").glob("test_*.py"))
             if p.name not in excluded]
    plugin = tmp_path / "offline_product.py"
    plugin.write_text("import socket\ndef blocked(*a, **kw): raise AssertionError('network forbidden')\n"
                      "def pytest_sessionstart(session): socket.socket.connect=blocked; socket.create_connection=blocked\n")
    products = subprocess.run([sys.executable, "-m", "pytest", "-p", "offline_product", "-q", *paths],
        cwd=tmp_path, env={**env, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}, capture_output=True, text=True, timeout=60)
    assert products.returncode == 0, products.stdout + products.stderr
    assert "129 passed" in products.stdout


@pytest.mark.parametrize("command", ["doctor", "contracts", "replay", "repeat", "compare", "bench"])
def test_offline_cli_commands_and_metadata(command, tmp_path):
    from odi.EVC.tests.test_rehear_assessment_boundary import pack, toy_bundle
    backend = Path(__file__).resolve().parents[3]
    evidence, rubric, output = [tmp_path / name for name in ("evidence.json", "rubric.json", "result.json")]
    evidence.write_text(pack().model_dump_json())
    rubric.write_text(toy_bundle().model_dump_json())
    args = [sys.executable, "-m", "tools.rehear_cli", command]
    if command not in {"doctor", "contracts"}:
        args += ["--input", str(evidence), "--rubric", str(rubric), "--output", str(output), "--allow-test-rubric"]
    if command == "repeat":
        config = tmp_path / "config.json"
        config.write_text('{"cache_enabled": true}')
        args += ["--repeat", "3", "--config", str(config)]
    result = subprocess.run(args, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(backend)},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Synthetic raw evidence" not in result.stdout + result.stderr
    summary = json.loads(result.stdout)
    if command in {"doctor", "contracts"}: return
    document = json.loads(output.read_text())
    assert document["task"] == "research16" and document["schema_version"] == "research-run.v1"
    for run in document["runs"]:
        meta = run["metadata"]
        assert {"run_id", "input_hash", "task", "engine", "model", "adapter", "rubric_version",
                "policy_version", "prompt_version", "call_count", "retry_count", "cache_hits", "failures", "elapsed_s"} <= meta.keys()
        assert meta["input_hash"] == document["input_hash"]
        assert meta["task"] == "research16"
        if command == "repeat":
            assert meta["call_count"] == 3 and meta["cache_hits"] == 0 and not meta["cache_enabled"]
        if command == "bench":
            assert meta["cold_load_s"] >= 0 and len(meta["warm_generation_s"]) >= 1
            assert meta["elapsed_s"] >= meta["cold_load_s"]
        if command == "replay": assert meta["call_count"] == 0
    if command == "compare":
        assert len(document["runs"]) == 2
        assert document["comparison"]["same_task"] is True


def test_archive_verifier_detects_missing_and_changed_sources(tmp_path):
    from tools.rehear_cli.migration import LEGACY_ROOTS, migrate, verify_inventory
    for name in LEGACY_ROOTS:
        source = tmp_path / "sushi-fast" / name
        (source / "data").mkdir(parents=True)
        (source / "results").mkdir()
        (source / "data/case.json").write_text('{"text":"SYNTHETIC_PRIVATE_TEXT"}')
        (source / "results/run.json").write_text('{"elapsed_ms":12}')
        (source / "timing.py").write_text("# synthetic measurement definition\n")
    manifest = tmp_path / "inventory.json"
    assert migrate(tmp_path, manifest)["verified_source_files"] == 6
    value = json.loads(manifest.read_text())
    assert "SYNTHETIC_PRIVATE_TEXT" not in manifest.read_text()
    source = tmp_path / "sushi-fast" / LEGACY_ROOTS[0] / "data/case.json"
    source.write_text("changed")
    with pytest.raises(ValueError, match="source content differs"):
        verify_inventory(tmp_path, manifest, require_sources=True)
    archive = tmp_path / value["files"][0]["destination"]
    archive.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="archive content differs"):
        verify_inventory(tmp_path, manifest)


@pytest.mark.parametrize("independent", [False, True])
def test_sqlite_rollback_and_retry_leave_one_segment(monkeypatch, tmp_path, independent):
    import sqlite3
    from odi.EVC.tests.test_playback_freshness import start, update_args
    from odi.EVC.pipeline import update_pipeline
    from odi.EVC.session_store import SessionStore
    async def run():
        db = tmp_path / "commit.db"
        template, pin = bind_db(monkeypatch, db)
        store = SessionStore()
        started, record = await start(store, independent=independent)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        args = update_args(started)
        with odidb.get_conn(db) as conn:
            conn.execute("CREATE TRIGGER reject_segment AFTER INSERT ON presentation_segments BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError):
            await update_pipeline(**args, store=store)
        assert odidb.list_presentation_segments(str(record.session_id)) == []
        assert record.step == 0 and not record.request_cache and not record.report_segments
        with odidb.get_conn(db) as conn:
            conn.execute("DROP TRIGGER reject_segment")
        result = await update_pipeline(**args, store=store)
        assert await update_pipeline(**args, store=store) == result
        assert record.step == 1
        assert len(odidb.list_presentation_segments(str(record.session_id))) == 1
        assert len(record.report_segments) == len(record.transcript_segments) == 1
    asyncio.run(run())


def test_legacy_case_replay_keeps_unknown_inputs_unknown():
    from tools.rehear_cli.legacy_cases import post_presentation_case
    case = {"id": "TEST_ONLY-legacy", "slides": [{"text": "合成 slide"}],
        "segments": [{"client_time_s": 30, "slide_index": 0, "text": "  synthetic text  "}],
        "qa_answers": [{"answer": "unpaired", "duration_s": 5}]}
    evidence = post_presentation_case(case)
    assert evidence.items[0].payload["text"] == "  synthetic text  "
    assert evidence.items[0].payload["segment_offset_s"] is None
    assert "qa_history" in evidence.missing_inputs
    assert "legacy_case_not_observed_session" in evidence.missing_inputs
    assert not any(i.kind in {"metrics", "qa"} for i in evidence.items)


def test_initial_questions_persist_before_ready(monkeypatch, tmp_path):
    from odi.EVC.tests.test_answer_service import setup
    from odi.EVC.question_service import generate_session_questions
    from odi.EVC.schema import GeneratedQuestionSet
    async def run():
        template, pin = bind_db(monkeypatch, tmp_path / "initial.db")
        store, record, token = await setup(2)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        questions = record.generated_questions
        record.generated_questions = []
        record.question_generation_status = "not_started"
        class Provider:
            calls = 0
            def generate(self, payload):
                self.calls += 1
                return GeneratedQuestionSet(questions=questions)
        provider = Provider()
        args = dict(session_id=record.session_id, token=token, request_id=uuid4(), question_count=2,
                    provider=provider, store=store, min_transcript_chars=1)
        result = await generate_session_questions(**args)
        assert await generate_session_questions(**args) == result
        state = odidb.get_presentation_qa(str(record.session_id), owner_user_id="owner", pre_session_pin=pin)
        assert state["questions"] == [q.model_dump(mode="json") for q in questions]
        assert state["generation_request_id"] == str(args["request_id"]) and provider.calls == 1
    asyncio.run(run())


def test_run_metadata_counts_real_retries_cache_and_failures(monkeypatch):
    from tools.rehear_cli import runs
    from rehear_ai.engines.fake import FakeEngine
    from rehear_ai.config import EngineConfig
    from odi.EVC.tests.test_rehear_assessment_boundary import pack, toy_bundle
    class Flaky(FakeEngine):
        def _infer(self, messages):
            if self.call_count == 1: return {"criteria": []}
            return super()._infer(messages)
    config = EngineConfig(retries=1, cache_enabled=True)
    engine = Flaky(config)
    monkeypatch.setattr(runs, "create_engine", lambda config: engine)
    meta = runs.assess_run(pack(), toy_bundle(), config, repeat=3)["metadata"]
    assert meta["call_count"] == 2 and meta["retry_count"] == 1 and meta["cache_hits"] == 2
    assert meta["failed_attempts"] == 1 and meta["failures"] == 0
    class Broken(FakeEngine):
        def _infer(self, messages): raise RuntimeError("SYNTHETIC_PRIVATE_FAILURE")
    monkeypatch.setattr(runs, "create_engine", lambda config: Broken(config))
    value = runs.assess_run(pack(), toy_bundle(), EngineConfig())
    assert value["metadata"]["call_count"] == 1 and value["metadata"]["failures"] == 1
    assert "SYNTHETIC_PRIVATE_FAILURE" not in json.dumps(value)


def test_bench_separates_load_first_and_warm_generation(monkeypatch):
    from tools.rehear_cli import runs
    from rehear_ai.engines.fake import FakeEngine
    from rehear_ai.config import EngineConfig
    from odi.EVC.tests.test_rehear_assessment_boundary import pack, toy_bundle
    clock = [0.]
    class Timed(FakeEngine):
        loaded = False
        def _prepare(self):
            if not self.loaded: clock[0] += 5
            self.loaded = True
        def _infer(self, messages):
            clock[0] += 2
            return super()._infer(messages)
    monkeypatch.setattr(runs.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(runs, "create_engine", Timed)
    meta = runs.assess_run(pack(), toy_bundle(), EngineConfig(), repeat=3, bench=True)["metadata"]
    assert meta["cold_load_s"] == 5 and meta["first_generation_s"] == 2
    assert meta["warm_generation_s"] == [2, 2] and meta["elapsed_s"] == 11
    assert meta["call_count"] == 3


def test_selected_speech_audience_is_persisted_without_claiming_playback(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from odi.EVC import router as routes
    from odi.EVC.tests.test_answer_service import setup, wav
    from odi.EVC.answer_service import submit_answer
    async def run():
        template, pin = bind_db(monkeypatch, tmp_path / "speech.db")
        store, record, token = await setup(1)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        monkeypatch.setattr(routes, "session_store", store)
        async def tts(*_): return wav()
        monkeypatch.setattr(routes, "synthesize", tts)
        app = FastAPI()
        app.include_router(routes.router)
        headers = {"X-EVC-Session-Token": token, "X-Speech-Voice": "ko-KR-InJoonNeural", "X-Audience-Id": "audience_01"}
        path = f"/xreal_rehear/evc/sessions/{record.session_id}/questions/0/speech"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post(path, headers={**headers, "X-EVC-Session-Token": "wrong"})).status_code == 401
            assert not record.qa_audience_bindings
            assert (await client.post(path, headers=headers)).status_code == 200
        async def stt(_): return "합성 답변"
        await submit_answer(session_id=record.session_id, token=token, index=0, request_id=uuid4(),
                            audio=wav(), store=store, transcriber=stt)
        state = odidb.get_presentation_qa(str(record.session_id), owner_user_id="owner", pre_session_pin=pin)
        assert state["audience_bindings"] == {"0": "audience_01"}
        assert state["answers"]["0"]["audience_id"] == "audience_01"
    asyncio.run(run())


def test_qa_transaction_failure_restored_retry_and_retention(monkeypatch, tmp_path):
    import sqlite3
    from odi.EVC.tests.test_answer_service import setup, wav, Provider
    from odi.EVC.answer_service import submit_answer
    from odi.EVC.qa_persistence import restore_qa_state
    async def run():
        db = tmp_path / "qa-transaction.db"
        template, pin = bind_db(monkeypatch, db)
        store, record, token = await setup(2)
        record.owner_user_id, record.template_id, record.pre_session_pin = "owner", template, pin
        provider = Provider()
        stt_calls = []
        async def stt(_): stt_calls.append(1); return "합성 답변"
        args = dict(session_id=record.session_id, token=token, index=0, request_id=uuid4(),
            audio=wav(), transcriber=stt, provider=provider, store=store, next_audience_id="audience_02")
        with odidb.get_conn(db) as conn:
            conn.execute("CREATE TRIGGER reject_qa AFTER UPDATE ON presentation_qa WHEN NEW.state_json LIKE '%\"response\"%' BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError): await submit_answer(**args)
        state = odidb.get_presentation_qa(str(record.session_id), owner_user_id="owner", pre_session_pin=pin)
        assert state["answers"]["0"]["transcript"] == "합성 답변" and not state["answers"]["0"].get("response")
        assert not record.qa_answers[0].get("response")
        with odidb.get_conn(db) as conn: conn.execute("DROP TRIGGER reject_qa")
        result = await submit_answer(**args)
        restore_qa_state(record)
        assert await submit_answer(**args) == result
        assert len(stt_calls) == len(provider.payloads) == 1
        with odidb.get_conn(db) as conn:
            conn.execute("UPDATE presentation_qa SET expires_at='2000-01-01T00:00:00Z'")
        odidb.delete_expired_presentation_data(db_path=db)
        assert odidb.get_presentation_qa(str(record.session_id), owner_user_id="owner", pre_session_pin=pin) is None
    asyncio.run(run())

