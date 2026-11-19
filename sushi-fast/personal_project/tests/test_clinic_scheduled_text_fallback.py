"""Scheduled fallback does not depend on PDF/image rendering."""
from personal_project import clinic_scheduled_delivery as scheduled


def test_scheduled_text_fallback_does_not_render(monkeypatch):
    from personal_project import router
    calls = []
    monkeypatch.setattr(scheduled.repository, 'get_or_create_target_report', lambda *_: {'generatedReportJson': {'synthetic': True}})
    monkeypatch.setattr(scheduled.native_kakao, 'create_clinic_job', lambda *_: {'jobId': 'synthetic', 'deliveryFormat': 'text'})
    monkeypatch.setattr(scheduled.native_kakao, 'send_clinic_job', lambda *_: calls.append('send') or {'sent': True, 'deliveryStatus': 'verified', 'deliveryFormat': 'text'})
    monkeypatch.setattr(scheduled.native_kakao, 'discard_clinic_job', lambda *_: calls.append('discard'))
    def fail_render(*args, **kwargs):
        raise AssertionError('text fallback must not render PDF or image')
    monkeypatch.setattr(router, '_target_report_pdf', fail_render)
    monkeypatch.setattr(scheduled.report_pdf, 'render_pages', fail_render)
    result = scheduled._deliver(1, 2)
    assert result['deliveryFormat'] == 'text'
    assert calls == ['send', 'discard']
