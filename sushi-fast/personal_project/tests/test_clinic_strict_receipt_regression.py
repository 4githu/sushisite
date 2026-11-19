"""Synthetic bridge responses must never promote malformed receipts to success."""
import pytest
from personal_project import kakao_bridge, native_kakao

@pytest.mark.parametrize('stage,value,expected', [
    ('image', 'true', 'unknown'), ('image', 1, 'unknown'),
    ('text', 'true', 'partial'), ('text', 1, 'partial'),
])
def test_only_literal_boolean_success_is_verified(monkeypatch, stage, value, expected):
    sends = []
    def invoke(command, **kwargs):
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        current = 'image' if kwargs.get('files') else 'text'
        sends.append(current)
        return {'sent': value if current == stage else True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(5001, 5002, {'schoolName': '합성학교', 'studentName': '합성학생'})
    native_kakao.store_page(job['jobId'], 5001, 5002, 1, 'image/jpeg', b'\xff\xd8\xfffixture')
    with pytest.raises(native_kakao.NativeKakaoError) as failure:
        native_kakao.send_clinic_job(job['jobId'], 5001, 5002)
    assert failure.value.delivery_status == expected
    with pytest.raises(native_kakao.NativeKakaoError):
        native_kakao.send_clinic_job(job['jobId'], 5001, 5002)
    assert sends == (['image'] if stage == 'image' else ['image', 'text'])
