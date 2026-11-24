import json
import io
import stat
from pathlib import Path
from types import SimpleNamespace
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_project import reader_translation, router as personal_router
from personal_project.reader_translation import hermes_plugin


@pytest.fixture

def app():
    application = FastAPI()
    application.include_router(personal_router.router)
    return application


def _authenticated_client(app):
    client = TestClient(app)
    client.app.dependency_overrides[personal_router.current_user_id] = lambda: 71
    return client


def _configure_fake_cli(monkeypatch, tmp_path, output: str, *, extra_code: str = ""):
    hermes_home = tmp_path / "disposable-hermes-home"
    hermes_home.mkdir()
    (hermes_home / ".paiper-reader-worker").touch()
    observations = tmp_path / "fake-cli-observations.json"
    executable = tmp_path / "fake-hermes"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        f"observations = {str(observations)!r}\n"
        "request = json.loads(sys.stdin.buffer.read())\n"
        "with open(observations, 'w', encoding='utf-8') as stream:\n"
        "    json.dump({'argv': sys.argv[1:], 'env_keys': sorted(os.environ), 'env_home': os.environ.get('HOME')}, stream)\n"
        f"{extra_code}"
        f"sys.stdout.write({output!r})\n"
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("READER_TRANSLATION_PROVIDER", "hermes_plugin")
    monkeypatch.setenv("READER_TRANSLATION_HERMES_EXECUTABLE", str(executable))
    monkeypatch.setenv("READER_TRANSLATION_HERMES_HOME", str(hermes_home))
    return executable, observations


def test_requires_mainauth_cookie_identity(app, monkeypatch):
    monkeypatch.setattr(personal_router.JMT, "SECRET_KEY", "synthetic-unit-test-secret")
    monkeypatch.setattr(personal_router.JMT, "ALGORITHM", "HS256")
    response = TestClient(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "s1", "text": "Synthetic passage"}]},
    )
    assert response.status_code == 401


def test_rejects_malformed_json_and_preserves_validation(app, monkeypatch):
    client = _authenticated_client(app)
    response = client.post(
        "/api/personal/reader/translate",
        content=b"{not-json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_json"
    assert client.post("/api/personal/reader/translate", json={"segments": []}).status_code == 400
    duplicate_ids = [{"id": "same", "text": "first"}, {"id": "same", "text": "second"}]
    duplicate_response = client.post("/api/personal/reader/translate", json={"segments": duplicate_ids})
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"]["code"] == "duplicate_segment_id"
    too_many = [{"id": str(i), "text": "x"} for i in range(reader_translation.MAX_SEGMENTS + 1)]
    assert client.post("/api/personal/reader/translate", json={"segments": too_many}).status_code == 413
    too_long = [{"id": "s1", "text": "x" * (reader_translation.MAX_SEGMENT_CHARS + 1)}]
    assert client.post("/api/personal/reader/translate", json={"segments": too_long}).status_code == 413


def test_missing_or_incomplete_provider_config_fails_closed(app, monkeypatch, tmp_path):
    monkeypatch.delenv("READER_TRANSLATION_PROVIDER", raising=False)
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "s1", "text": "SYNTH_SOURCE_ONLY"}]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "translation_provider_unavailable"

    monkeypatch.setenv("READER_TRANSLATION_PROVIDER", "hermes_plugin")
    monkeypatch.delenv("READER_TRANSLATION_HERMES_EXECUTABLE", raising=False)
    monkeypatch.setenv("READER_TRANSLATION_HERMES_HOME", str(tmp_path / "isolated"))
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "s1", "text": "SYNTH_SOURCE_ONLY"}]},
    )
    assert response.status_code == 503
    assert "SYNTH_SOURCE_ONLY" not in response.text


def test_success_maps_fake_cli_response_to_api_contract_and_hides_source(app, monkeypatch, tmp_path):
    source = "SYNTH_SOURCE_SENTINEL_3927"
    raw_output = json.dumps(
        {"translations": [{"id": "b", "text": "fake B"}, {"id": "a", "text": "fake A"}]}
    )
    _, observations = _configure_fake_cli(monkeypatch, tmp_path, raw_output)
    client = _authenticated_client(app)
    response = client.post(
        "/api/personal/reader/translate",
        json={
            "target_language": "Korean",
            "segments": [{"id": "a", "text": source}, {"id": "b", "text": "synthetic second"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"].startswith("no-store")
    assert response.json() == {
        "translations": [{"id": "a", "text": "fake A"}, {"id": "b", "text": "fake B"}]
    }
    observed = json.loads(observations.read_text())
    assert observed["argv"] == ["paiper-reader-translate"]
    assert source not in json.dumps(observed)
    assert not {
        "READER_TRANSLATION_PROVIDER",
        "READER_TRANSLATION_HERMES_EXECUTABLE",
        "READER_TRANSLATION_HERMES_HOME",
        "OPENAI_API_KEY",
        "HERMES_API_KEY",
    }.intersection(observed["env_keys"])
    assert source not in response.text


@pytest.mark.parametrize(
    "bad_output",
    [
        '{"translations":[{"id":"a","text":"one"},{"id":"a","text":"two"}]}',
        '{"translations":[{"id":"a","text":"one"}]}',
        '{"translations":[{"id":"unknown","text":"one"},{"id":"b","text":"two"}]}',
        'not-json-with-SYNTH_SOURCE_SENTINEL_5ea1',
        '{"translations":[{"id":"a","text":""},{"id":"b","text":"two"}]}',
    ],
)
def test_malformed_cli_ids_or_output_are_sanitized(app, monkeypatch, tmp_path, bad_output, caplog):
    source = "SYNTH_SOURCE_SENTINEL_5ea1"
    _configure_fake_cli(monkeypatch, tmp_path, bad_output)
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "a", "text": source}, {"id": "b", "text": "synthetic B"}]},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "translation_provider_error"
    assert source not in response.text
    assert "not-json" not in response.text
    kind = "malformed_json" if bad_output.startswith("not-json") else "invalid_schema"
    assert f"reader_cli_failure kind={kind}" in caplog.text
    assert source not in caplog.text


def test_timeout_and_nonzero_exit_are_sanitized(app, monkeypatch, tmp_path, caplog):
    source = "SYNTH_TIMEOUT_SOURCE"
    _configure_fake_cli(
        monkeypatch,
        tmp_path,
        '{"translations":[]}',
        extra_code="time.sleep(2)\n",
    )
    monkeypatch.setattr(reader_translation, "MAX_HERMES_TIMEOUT_SECONDS", 0.05)
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate", json={"segments": [{"id": "x", "text": source}]}
    )
    assert response.status_code == 502
    assert source not in response.text
    assert "reader_cli_failure kind=timeout" in caplog.text
    assert source not in caplog.text


def test_nonzero_child_exit_is_sanitized(app, monkeypatch, tmp_path, caplog):
    _configure_fake_cli(
        monkeypatch,
        tmp_path,
        '{"translations":[]}',
        extra_code="sys.stderr.write('SYNTH_ERROR_BODY')\nsys.exit(9)\n",
    )
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "x", "text": "SYNTH_FAILURE_SOURCE"}]},
    )
    assert response.status_code == 502
    assert "SYNTH_FAILURE_SOURCE" not in response.text
    assert "SYNTH_ERROR_BODY" not in response.text
    assert "reader_cli_failure kind=nonzero_exit returncode=9" in caplog.text
    assert "SYNTH_FAILURE_SOURCE" not in caplog.text
    assert "SYNTH_ERROR_BODY" not in caplog.text


def test_oversized_child_output_is_terminated_and_sanitized(app, monkeypatch, tmp_path, caplog):
    _configure_fake_cli(
        monkeypatch,
        tmp_path,
        "'x' * 10000",
        extra_code="sys.stdout.write('x' * 10000)\nsys.exit(0)\n",
    )
    monkeypatch.setattr(reader_translation, "MAX_HERMES_OUTPUT_BYTES", 128)
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "x", "text": "SYNTH_BOUNDED_SOURCE"}]},
    )
    assert response.status_code == 502
    assert "SYNTH_BOUNDED_SOURCE" not in response.text
    assert "reader_cli_failure kind=output_limit" in caplog.text
    assert "SYNTH_BOUNDED_SOURCE" not in caplog.text


def test_rejects_invalid_executable_and_profile_paths(app, monkeypatch, tmp_path):
    monkeypatch.setenv("READER_TRANSLATION_PROVIDER", "hermes_plugin")
    monkeypatch.setenv("READER_TRANSLATION_HERMES_EXECUTABLE", "hermes")
    monkeypatch.setenv("READER_TRANSLATION_HERMES_HOME", str(tmp_path / "hermes-home"))
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"segments": [{"id": "x", "text": "synthetic"}]},
    )
    assert response.status_code == 503


def test_requires_worker_marker_and_refuses_active_hermes_home(app, monkeypatch, tmp_path):
    executable, observations = _configure_fake_cli(
        monkeypatch, tmp_path, '{"translations":[{"id":"x","text":"fake"}]}'
    )
    worker_home = Path(os.environ["READER_TRANSLATION_HERMES_HOME"])
    marker = worker_home / ".paiper-reader-worker"
    marker.unlink()
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate", json={"segments": [{"id": "x", "text": "synthetic"}]}
    )
    assert response.status_code == 503
    assert not observations.exists()

    marker.touch()
    monkeypatch.setenv("HERMES_HOME", str(worker_home))
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate", json={"segments": [{"id": "x", "text": "synthetic"}]}
    )
    assert response.status_code == 503
    assert not observations.exists()


def test_payload_user_id_is_ignored_and_provider_failures_never_echo_source(app, monkeypatch, tmp_path):
    source = "SYNTH_SOURCE_EXCEPTION"
    _configure_fake_cli(
        monkeypatch,
        tmp_path,
        "{}",
        extra_code="sys.stderr.write('SYNTH_SOURCE_EXCEPTION')\nsys.exit(2)\n",
    )
    response = _authenticated_client(app).post(
        "/api/personal/reader/translate",
        json={"user_id": 999, "segments": [{"id": "stable-id", "text": source}]},
    )
    assert response.status_code == 502
    assert source not in response.text
    assert response.json()["detail"]["message"] == "번역 제공자 요청을 처리하지 못했습니다."


def test_plugin_response_rejects_extra_ids_and_orders_by_input():
    input_segments = [{"id": "first", "text": "synthetic"}, {"id": "second", "text": "fixture"}]
    result = {"translations": [{"id": "second", "text": "2"}, {"id": "first", "text": "1"}]}
    assert reader_translation._validate_plugin_response(result, input_segments) == [
        {"id": "first", "text": "1"}, {"id": "second", "text": "2"}
    ]
    with pytest.raises(ValueError):
        reader_translation._validate_plugin_response(
            {"translations": [{"id": "first", "text": "1"}, {"id": "extra", "text": "x"}]},
            input_segments,
        )


def test_context_survives_api_and_plugin_validation():
    from personal_project.reader_translation import _validate_payload
    payload = {"segments": [{"id": "p9-s4", "text": "enging by NAC.", "context_before": "ROS scav -", "context_after": "Next finding."}], "target_language": "ko"}
    api_segments, language = _validate_payload(payload)
    plugin_segments, _ = hermes_plugin._validate_request(json.dumps({"segments": api_segments, "target_language": language}).encode())
    assert plugin_segments == payload["segments"]


def test_plugin_cli_uses_plain_llm_json_when_structured_mode_is_unsupported(monkeypatch):
    source = "SYNTH_PLUGIN_SOURCE_OLLAMA"
    calls = []

    class FakeLlm:
        def __init__(self):
            self.structured_calls = 0

        def complete_structured(self, **_kwargs):
            self.structured_calls += 1
            raise RuntimeError("HTTP 501: Ollama does not support this response format")

        def complete(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return SimpleNamespace(text=json.dumps({
                "translations": [
                    {"id": "right", "text": "fake right"},
                    {"id": "left", "text": "fake left"},
                ]
            }))

    class BufferStream:
        def __init__(self, buffer):
            self.buffer = buffer

    stdin = SimpleNamespace(buffer=io.BytesIO(json.dumps({
        "target_language": "Korean",
        "segments": [{"id": "left", "text": source}, {"id": "right", "text": "synthetic"}],
    }).encode()))
    output = io.BytesIO()
    monkeypatch.setattr(hermes_plugin.sys, "stdin", stdin)
    monkeypatch.setattr(hermes_plugin.sys, "stdout", BufferStream(output))

    fake_llm = FakeLlm()
    assert hermes_plugin._handle(SimpleNamespace(llm=fake_llm), SimpleNamespace()) == 0
    assert fake_llm.structured_calls == 0
    assert json.loads(output.getvalue()) == {
        "translations": [{"id": "left", "text": "fake left"}, {"id": "right", "text": "fake right"}]
    }
    assert len(calls) == 1
    messages, kwargs = calls[0]
    assert kwargs["purpose"] == "paiper-reader.translation"
    assert kwargs["timeout"] == 300
    assert source in json.dumps(messages)
    assert "valid JSON" in json.dumps(messages)
    assert "Return only valid JSON" in messages[0]["content"]
    assert "Preserve equations, symbols, units, citations, and numbers" in messages[0]["content"]
    assert "Do not invent missing content" in messages[0]["content"]


@pytest.mark.parametrize(
    "response_text",
    [
        "not-json",
        'Here is the translation: {"translations":[]}',
        "```json" + chr(10) + '{"translations":[]}' + chr(10) + "```",
        '{"translations":[{"id":"left","text":"one"},{"id":"left","text":"two"}]}',
        '{"translations":[{"id":"left","text":"one"}]}',
        '{"translations":[{"id":"left","text":"one"},{"id":"extra","text":"two"}]}',
        '{"translations":[{"id":"left","text":"one","extra":"x"},{"id":"right","text":"two"}]}',
        '{"translations":[],"extra":"x"}',
    ],
)
def test_plugin_cli_rejects_non_exact_plain_json_without_echoing(monkeypatch, capsys, response_text):
    source = "SYNTH_PLAIN_JSON_REJECT_SOURCE"

    class FakeLlm:
        def complete(self, _messages, **_kwargs):
            return SimpleNamespace(text=response_text)

    class BufferStream:
        def __init__(self, buffer):
            self.buffer = buffer

    stdin = SimpleNamespace(buffer=io.BytesIO(json.dumps({
        "segments": [{"id": "left", "text": source}, {"id": "right", "text": "synthetic"}],
    }).encode()))
    output = io.BytesIO()
    monkeypatch.setattr(hermes_plugin.sys, "stdin", stdin)
    monkeypatch.setattr(hermes_plugin.sys, "stdout", BufferStream(output))

    assert hermes_plugin._handle(SimpleNamespace(llm=FakeLlm()), SimpleNamespace()) == 2
    assert output.getvalue() == b""
    assert source not in capsys.readouterr().err


def test_plugin_cli_uses_fake_structured_llm_and_emits_exact_api_shape(monkeypatch):
    source = "SYNTH_PLUGIN_SOURCE_4d12"
    calls = []

    class FakeLlm:
        def complete(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return SimpleNamespace(text=json.dumps({
                "translations": [
                    {"id": "right", "text": "fake right"},
                    {"id": "left", "text": "fake left"},
                ]
            }))

    class BufferStream:
        def __init__(self, buffer):
            self.buffer = buffer

    stdin = SimpleNamespace(buffer=io.BytesIO(json.dumps({
        "target_language": "Korean",
        "segments": [{"id": "left", "text": source}, {"id": "right", "text": "synthetic"}],
    }).encode()))
    output = io.BytesIO()
    monkeypatch.setattr(hermes_plugin.sys, "stdin", stdin)
    monkeypatch.setattr(hermes_plugin.sys, "stdout", BufferStream(output))
    assert hermes_plugin._handle(SimpleNamespace(llm=FakeLlm()), SimpleNamespace()) == 0
    assert json.loads(output.getvalue()) == {
        "translations": [{"id": "left", "text": "fake left"}, {"id": "right", "text": "fake right"}]
    }
    assert len(calls) == 1
    messages, kwargs = calls[0]
    assert kwargs["purpose"] == "paiper-reader.translation"
    assert kwargs["temperature"] == 0.0
    assert source in json.dumps(messages)
    assert "Do not provide analysis or reasoning" in messages[0]["content"]
    assert "Return only valid JSON" in messages[0]["content"]


@pytest.mark.parametrize(
    "response_text",
    [
        '{"translations":[{"id":"left","text":"one"},{"id":"left","text":"two"}]}',
        '{"translations":[{"id":"left","text":"one"}]}',
        '{"translations":[{"id":"unknown","text":"one"},{"id":"right","text":"two"}]}',
        "not-json-with-SYNTH_SOURCE_SENTINEL_5ea1",
        '{"translations":[{"id":"left","text":""},{"id":"right","text":"two"}]}',
    ],
)
def test_plugin_cli_rejects_malformed_plain_output_without_echoing_input(monkeypatch, response_text, capsys):
    source = "SYNTH_PLUGIN_REJECT_SOURCE"

    class FakeLlm:
        def complete(self, _messages, **_kwargs):
            return SimpleNamespace(text=response_text)

    class BufferStream:
        def __init__(self, buffer):
            self.buffer = buffer

    stdin = SimpleNamespace(buffer=io.BytesIO(json.dumps({
        "segments": [{"id": "left", "text": source}, {"id": "right", "text": "synthetic"}]
    }).encode()))
    output = io.BytesIO()
    monkeypatch.setattr(hermes_plugin.sys, "stdin", stdin)
    monkeypatch.setattr(hermes_plugin.sys, "stdout", BufferStream(output))
    assert hermes_plugin._handle(SimpleNamespace(llm=FakeLlm()), SimpleNamespace()) == 2
    assert output.getvalue() == b""
    assert source not in capsys.readouterr().err


def test_plugin_registers_standalone_cli_command():
    registrations = []
    hermes_plugin.register(SimpleNamespace(register_cli_command=lambda **kwargs: registrations.append(kwargs)))
    assert {r["name"] for r in registrations} == {"paiper-reader-translate", "paiper-reader-explain-image"}
    assert all(r["setup_fn"] is not None and r["handler_fn"] is not None for r in registrations)


def test_child_preserves_os_home_while_selecting_hermes_profile(app, monkeypatch, tmp_path):
    _, observations = _configure_fake_cli(monkeypatch, tmp_path, '{"translations":[{"id":"x","text":"synthetic"}]}')
    response = _authenticated_client(app).post('/api/personal/reader/translate', json={'segments':[{'id':'x','text':'synthetic'}]})
    assert response.status_code == 200
    assert json.loads(observations.read_text())['env_home'] == os.environ.get('HOME', str(Path.home()))
