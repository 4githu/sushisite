"""Unconfirmed fallback sends cannot be repeated automatically (synthetic)."""
import pytest
from personal_project import kakao_bridge, native_kakao


@pytest.mark.parametrize('result', [None, {'sent': False}, {'sent': 'true'}])
def test_fallback_unconfirmed_text_never_retries(monkeypatch, result):
    sends = []
    def invoke(command, **kwargs):
        if command == 'search':
            return ({'opened': True, 'room': '본계정', 'searchEvidence': 'unique_exact'}
                    if kwargs['room'] == '본계정' else {'found': False, 'room': kwargs['room'], 'searchEvidence': 'confirmed_absent'})
        sends.append(kwargs)
        return result
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(7001, 7002, {'schoolName': '합성학교', 'studentName': '합성학생'})
    native_kakao.store_page(job['jobId'], 7001, 7002, 1, 'image/jpeg', b'\xff\xd8\xffsynthetic')
    try:
        with pytest.raises(native_kakao.NativeKakaoError) as error:
            native_kakao.send_clinic_job(job['jobId'], 7001, 7002)
        assert error.value.code == 'delivery_unknown'
        with pytest.raises(native_kakao.NativeKakaoError):
            native_kakao.send_clinic_job(job['jobId'], 7001, 7002)
        assert len(sends) == 1
    finally:
        native_kakao.discard_clinic_job(job['jobId'], 7001, 7002)
