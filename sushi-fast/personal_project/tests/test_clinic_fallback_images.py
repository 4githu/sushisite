from starlette.requests import Request
from personal_project import native_kakao, kakao_bridge, router


def test_fallback_server_route_sends_notice_and_rendered_images(monkeypatch, isolated_delivery_db):
    sends = []
    report = {'id': 7, 'schoolName': '합성학교', 'studentName': '가상학생'}
    monkeypatch.setattr(router.repository, 'get_or_create_target_report', lambda *_: report)
    monkeypatch.setattr(router.repository, 'update_target_report', lambda *a, **k: None)
    monkeypatch.setattr(router, '_target_report_pdf', lambda *_: b'synthetic pdf')
    monkeypatch.setattr(router.report_pdf, 'render_pages', lambda *a, **k: [b'\xff\xd8\xffsynthetic'])
    def invoke(command, **kw):
        if command == 'search':
            if kw['room'] == '본계정':
                return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
            return {'found': False, 'room': kw['room'], 'searchEvidence': 'confirmed_absent'}
        sends.append(kw)
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    request = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [(b'origin', b'https://aura.chobab.app')]})
    result = router.send_server_generated_clinic_report(50, request, 3)
    assert result['sent'] and result['destination'] == '본계정'
    assert len(sends) == 2 and sends[0]['files'] == [] and sends[0]['text']
    assert sends[1]['files'] and not sends[1]['text']
