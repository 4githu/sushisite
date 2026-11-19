"""Synthetic clinic product-path regression; never invokes the Mac bridge."""
import pytest
from personal_project import kakao_bridge, native_kakao


@pytest.mark.parametrize('failure', ['malformed_response', 'not_sent'])
def test_image_verified_note_failure_is_partial_and_never_replayed(monkeypatch, failure):
    calls = []
    def fake_invoke(command, **kwargs):
        calls.append((command, bool(kwargs.get('files'))))
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        if kwargs.get('files'):
            return {'sent': True}
        if failure == 'malformed_response':
            raise RuntimeError('synthetic invalid bridge response')
        return {'sent': False}
    monkeypatch.setattr(kakao_bridge, 'invoke', fake_invoke)
    report = {'schoolName': '합성학교', 'studentName': '합성학생'}
    job = native_kakao.create_clinic_job(981, 982, report)
    native_kakao.store_page(job['jobId'], 981, 982, 1, 'image/jpeg', b'\xff\xd8\xffsynthetic')
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.send_clinic_job(job['jobId'], 981, 982)
    assert exc.value.code == 'partial_delivery'
    assert exc.value.delivery_status == 'partial'
    assert calls == [('search', False), ('search', False), ('send', True), ('send', False)]
    with pytest.raises(native_kakao.NativeKakaoError):
        native_kakao.send_clinic_job(job['jobId'], 981, 982)
    assert len(calls) == 4
