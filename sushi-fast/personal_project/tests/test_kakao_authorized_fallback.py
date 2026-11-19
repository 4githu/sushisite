from starlette.requests import Request
import pytest
from personal_project import native_kakao, kakao_bridge, router


def fixture_report():
    return {'schoolName':'합성학교','studentName':'가상학생','roundLabel':'검증 회차',
            'generatedReportJson':{'learningContent':{'paragraphs':['가상 학습 내용']},'problemSolvingNote':'가상 문제 풀이'},
            'contentJson':{'blocks':[{'children':[{'text':'직접 작성한 합성 본문'}]}]}}


@pytest.fixture(autouse=True)
def clean_jobs():
    yield
    with native_kakao._jobs_lock:
        for job in list(native_kakao._jobs.values()):native_kakao._remove_job(job)


def test_two_absent_rooms_deliver_report_text_to_authorized_self(monkeypatch):
    calls=[]
    def invoke(command,**kw):
        calls.append((command,kw))
        if command=='search':
            if kw['room']!='본계정':return {'found':False,'room':kw['room'],'searchEvidence':'confirmed_absent'}
            return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'}
        return {'sent':True,'verifiedBy':'outgoing_rows'}
    monkeypatch.setattr(kakao_bridge,'invoke',invoke)
    job=native_kakao.create_clinic_job(3,50,fixture_report())
    assert job['deliveryFormat']=='images'
    native_kakao.store_page(job['jobId'],3,50,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    result=native_kakao.send_clinic_job(job['jobId'],3,50)
    assert result['sent'] is True and result['destination']=='본계정'
    sends=[kw for cmd,kw in calls if cmd=='send']
    assert len(sends)==2 and sends[0]['room']=='본계정' and sends[0]['text'] and not sends[0]['files']
    assert sends[1]['room']=='본계정' and sends[1]['files'] and not sends[1]['text']
    assert job['jobId'] not in native_kakao._jobs


def test_server_route_fallback_renders_pdf(monkeypatch, isolated_delivery_db):
    monkeypatch.setattr(router.repository,'get_or_create_target_report',lambda *_:{**fixture_report(), 'id': 7})
    monkeypatch.setattr(router.repository,'update_target_report',lambda *args, **kwargs: None)
    def invoke(command,**kw):
        if command=='send':return {'sent':True}
        return {'opened':True,'room':'본계정','searchEvidence':'unique_exact'} if kw['room']=='본계정' else {'found':False,'room':kw['room'],'searchEvidence':'confirmed_absent'}
    monkeypatch.setattr(kakao_bridge,'invoke',invoke)
    monkeypatch.setattr(router,'_target_report_pdf',lambda *_:b'%PDF-fixture')
    monkeypatch.setattr(router.report_pdf,'render_pages',lambda *_,**__: [b'\xff\xd8\xffsynthetic'])
    request=Request({'type':'http','method':'POST','path':'/','headers':[(b'origin',b'https://aura.chobab.app')]})
    result=router.send_server_generated_clinic_report(50,request,3)
    assert result['sent'] and result['destination']=='본계정'


def test_changed_self_title_stops_send(monkeypatch):
    n=0
    def invoke(command,**kw):
        nonlocal n
        assert command=='search'
        if kw['room']!='본계정':return {'found':False,'room':kw['room'],'searchEvidence':'confirmed_absent'}
        n+=1
        return {'opened':True,'room':'본계정' if n==1 else '다른 방','searchEvidence':'unique_exact'}
    monkeypatch.setattr(kakao_bridge,'invoke',invoke)
    job=native_kakao.create_clinic_job(3,50,fixture_report())
    native_kakao.store_page(job['jobId'],3,50,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.send_clinic_job(job['jobId'],3,50)
    assert exc.value.code == 'recipient_unverified'
