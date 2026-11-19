from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from personal_project import ai_report
from personal_project.make_report_test.gemini_report_service import GeminiReportError


@pytest.mark.parametrize('exc', [
    RuntimeError('sensitive fixture'),
    GeminiReportError('sensitive fixture', diagnostic_code='private_student_fixture'),
])
def test_untrusted_diagnostic_is_not_returned(exc):
    exc.diagnostic_code = getattr(exc, 'diagnostic_code', 'api_http_503')
    result = ai_report._safe_generation_error('provider_generate', exc)
    assert result.endswith(':unclassified')
    assert 'private_student_fixture' not in result


@pytest.mark.parametrize('stage', ['provider_initialize', 'persist_generated_report'])
@pytest.mark.parametrize('diagnostic', ['api_http_503', 'provider_blocked_prohibited_content'])
def test_provider_diagnostic_outside_generate_is_not_attributed_to_provider(monkeypatch, stage, diagnostic):
    stored = []
    class FakeService:
        last_cache_mode = 'implicit'
        cache_notice = None
        @staticmethod
        def read_prompt():
            return 'fixture'
        @staticmethod
        def prompt_hash(_):
            return 'hash'
        def __init__(self, **kwargs):
            if stage == 'provider_initialize':
                raise GeminiReportError('fixture', diagnostic_code=diagnostic)
        def generate(self, **kwargs):
            return {}, None
        def close(self):
            pass
    monkeypatch.setattr(ai_report.repository, 'get_or_create_target_report', lambda *a: None)
    monkeypatch.setattr(ai_report, 'migrate', lambda: None)
    monkeypatch.setattr(ai_report, 'build_report_input', lambda *a, **kw: {'target': {'userId': 10}})
    monkeypatch.setattr(ai_report, 'get_report_model', lambda _: SimpleNamespace(provider='gemini', explicit_cache=False))
    monkeypatch.setattr(ai_report, 'list_completed_runs', lambda _: [])
    monkeypatch.setattr(ai_report.GeminiReportService, 'read_prompt', lambda: 'fixture')
    monkeypatch.setattr(ai_report.GeminiReportService, 'prompt_hash', lambda _: 'hash')
    monkeypatch.setattr(ai_report, 'find_completed_run', lambda *a: None)
    monkeypatch.setattr(ai_report, 'start_run', lambda *a, **kw: 123)
    monkeypatch.setattr(ai_report, 'finish_run', lambda *a, **kw: stored.append(kw))
    monkeypatch.setattr(ai_report, 'GeminiReportService', FakeService)
    if stage == 'persist_generated_report':
        def fail(*args):
            raise GeminiReportError('fixture', diagnostic_code=diagnostic)
        monkeypatch.setattr(ai_report, 'set_run_cache_mode', fail)
    with pytest.raises(HTTPException) as raised:
        ai_report.generate(10, 20, model='gemini-test', score_mode='none')
    assert raised.value.detail['code'] == 'ai_report_generation_failed'
