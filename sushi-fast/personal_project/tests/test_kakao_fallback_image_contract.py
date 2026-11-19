import pytest
from personal_project import native_kakao, kakao_bridge


def create(monkeypatch, sends):
    def invoke(cmd, **kw):
        if cmd == 'search':
            if kw['room'] == '본계정':
                return {'opened': True, 'room': '본계정', 'searchEvidence': 'unique_exact'}
            return {'found': False, 'room': kw['room'], 'searchEvidence': 'confirmed_absent'}
        sends.append(kw)
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(31, 32, {'schoolName':'합성학교','studentName':'가상학생'})
    return job


def test_fallback_notice_precedes_same_images(monkeypatch):
    sends=[]
    job=create(monkeypatch, sends)
    assert job['deliveryFormat'] == 'images'
    native_kakao.store_page(job['jobId'],31,32,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    result=native_kakao.send_clinic_job(job['jobId'],31,32)
    assert result['sent'] and result['deliveryFormat'] == 'images'
    assert len(sends)==2 and sends[0]['text'] and not sends[0]['files']
    assert '합성학교 가상학생 생명클리닉' in sends[0]['text']
    assert sends[0]['keepRoomOpen'] is True
    assert not sends[1]['text'] and len(sends[1]['files'])==1
    assert all(s['room']=='본계정' for s in sends)


def test_notice_only_does_not_count_as_success(monkeypatch):
    sends=[]
    job=create(monkeypatch, sends)
    native_kakao.store_page(job['jobId'],31,32,1,'image/jpeg',b'\xff\xd8\xffsynthetic')
    old=kakao_bridge.invoke
    def invoke(cmd,**kw):
        if cmd=='send' and kw['files']:
            raise TimeoutError('synthetic')
        return old(cmd,**kw)
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.send_clinic_job(job['jobId'],31,32)
    assert exc.value.delivery_status == 'partial'
    assert exc.value.delivery_result['stages']['text']=='verified'
    assert exc.value.delivery_result['stages']['images']=='unknown'
