"""Synthetic bridge failures: no real Kakao calls or student data."""
import pytest
from personal_project import kakao_bridge, native_kakao


@pytest.mark.parametrize('response', ['exception', 'invalid_type'])
def test_image_bridge_response_loss_is_unknown_and_not_replayed(monkeypatch, response):
    sends = []
    def invoke(command, **kwargs):
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        sends.append(kwargs)
        if response == 'exception':
            raise RuntimeError('synthetic lost response')
        return None
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(742, 743, {'schoolName': '합성학교', 'studentName': '합성학생'})
    native_kakao.store_page(job['jobId'], 742, 743, 1, 'image/jpeg', b'\xff\xd8\xffsynthetic')
    with pytest.raises(native_kakao.NativeKakaoError) as error:
        native_kakao.send_clinic_job(job['jobId'], 742, 743)
    assert error.value.code == 'delivery_unknown'
    assert error.value.delivery_status == 'unknown'
    with pytest.raises(native_kakao.NativeKakaoError):
        native_kakao.send_clinic_job(job['jobId'], 742, 743)
    assert len(sends) == 1
