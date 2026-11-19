"""Self-room fallback sends a recipient notice then report images."""
from personal_project import kakao_bridge, native_kakao


def test_missing_both_rooms_delivers_report_images_to_exact_self(monkeypatch):
    sent = []
    def invoke(command, **kwargs):
        room = kwargs['room']
        if command == 'search':
            if room != native_kakao.SELF_CHAT_TITLE:
                return {'found': False, 'room': room, 'searchEvidence': 'confirmed_absent'}
            return {'opened': True, 'room': room, 'searchEvidence': 'unique_exact'}
        sent.append(kwargs)
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    report = {'schoolName': '합성학교', 'studentName': '합성학생',
              'generatedReportJson': {'learningContent': {'paragraphs': ['합성 리포트']}}}
    job = native_kakao.create_clinic_job(1, 2, report)
    try:
        assert job['deliveryFormat'] == 'images'
        native_kakao.store_page(job['jobId'], 1, 2, 1, 'image/jpeg', b'\xff\xd8\xffsynthetic')
        response = native_kakao.send_clinic_job(job['jobId'], 1, 2)
        assert response['sent'] and response['deliveryStatus'] == 'verified'
        assert len(sent) == 2
        assert all(item['room'] == native_kakao.SELF_CHAT_TITLE for item in sent)
        assert '합성 리포트' not in sent[0]['text']
        assert sent[0]['files'] == []
        assert sent[1]['files'] and not sent[1]['text']
    finally:
        native_kakao.discard_clinic_job(job['jobId'], 1, 2)
