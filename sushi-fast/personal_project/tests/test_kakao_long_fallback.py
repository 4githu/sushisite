import pytest
from personal_project import native_kakao, kakao_bridge


def test_long_report_fallback_sends_notice_then_images_not_report_text(monkeypatch):
    calls = []
    def invoke(command, **kwargs):
        if command == 'search':
            if kwargs['room'] == '본계정':
                return {'opened': True, 'room': '본계정', 'searchEvidence': 'unique_exact'}
            return {'found': False, 'room': kwargs['room'], 'searchEvidence': 'confirmed_absent'}
        calls.append(kwargs)
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    report = {'schoolName':'합성학교','studentName':'가상학생','generatedReportJson':{'learningContent':{'paragraphs':['합성문장' * 300]}}}
    job = native_kakao.create_clinic_job(631, 632, report)
    native_kakao.store_page(job['jobId'],631,632,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    result = native_kakao.send_clinic_job(job['jobId'], 631, 632)
    assert result['sent']
    assert len(calls) == 2
    assert '합성문장' not in calls[0]['text']
    assert calls[0]['text'] and not calls[0]['files'] and calls[1]['files'] and not calls[1]['text']
    assert calls[0]['keepRoomOpen']
    assert not calls[-1]['keepRoomOpen']


def test_image_failure_after_notice_is_partial_and_never_replayed(monkeypatch):
    calls = []
    def invoke(command, **kwargs):
        if command == 'search':
            if kwargs['room'] == '본계정':
                return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'}
            return {'found':False,'room':kwargs['room'],'searchEvidence':'confirmed_absent'}
        calls.append(kwargs)
        return {'sent':len(calls) == 1}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(633, 634, {'schoolName':'합성학교','studentName':'가상학생','generatedReportJson':{'learningContent':{'paragraphs':['합성문장' * 300]}}})
    native_kakao.store_page(job['jobId'],633,634,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    with pytest.raises(native_kakao.NativeKakaoError) as error:
        native_kakao.send_clinic_job(job['jobId'], 633, 634)
    assert error.value.code == 'partial_delivery'
    assert error.value.delivery_status == 'partial'
    assert error.value.delivery_result['sentCount'] == 0
    assert error.value.delivery_result['stages']['text'] == 'verified'
    assert len(calls) == 2
