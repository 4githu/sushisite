"""Synthetic recipient selection; never invokes the actual Kakao desktop."""
import subprocess
import json
from pathlib import Path

import pytest

from personal_project import kakao_bridge, native_kakao


@pytest.fixture(autouse=True)
def clean_jobs():
    yield
    with native_kakao._jobs_lock:
        for job in list(native_kakao._jobs.values()):
            native_kakao._remove_job(job)


BRIDGE_SOURCE = Path(__file__).resolve().parents[3] / 'ops/kakao_bridge.swift'


@pytest.fixture(scope='module')
def synthetic_bridge(tmp_path_factory):
    binary = tmp_path_factory.mktemp('swift-bridge') / 'bridge'
    subprocess.run(['swiftc', str(BRIDGE_SOURCE), '-o', str(binary)], check=True, timeout=120)
    return binary


def simulate(binary, snapshots):
    result = subprocess.run([str(binary)], input=json.dumps({
        'command': 'search-simulation', 'room': '학교 학생 생명클리닉',
        'snapshots': snapshots,
    }), text=True, capture_output=True, timeout=10)
    return json.loads(result.stdout)


def test_delayed_ax_row_is_not_misclassified_as_absent(synthetic_bridge):
    result = simulate(synthetic_bridge, [
        {'query': '학교 학생 생명클리닉', 'rows': [], 'empty': False},
        {'query': '학교 학생 생명클리닉', 'rows': ['학교 학생 생명클리닉'], 'empty': False},
        {'query': '학교 학생 생명클리닉', 'rows': ['학교 학생 생명클리닉'], 'empty': False},
        {'query': '학교 학생 생명클리닉', 'rows': ['학교 학생 생명클리닉'], 'empty': False},
    ])
    assert result['searchEvidence'] == 'unique_exact'


def test_single_transient_exact_match_must_not_open_room(synthetic_bridge):
    room='학교 학생 생명클리닉'
    one={'query':room,'rows':[room],'empty':False}
    assert simulate(synthetic_bridge,[one])['searchEvidence'] != 'unique_exact'
    assert simulate(synthetic_bridge,[one, {'query':room,'rows':[room,room], 'empty':False}])['searchEvidence'] == 'ambiguous'


def test_empty_requires_explicit_marker_and_recheck(synthetic_bridge):
    empty = {'query': '학교 학생 생명클리닉', 'rows': [], 'empty': True}
    cleared = {'query': '', 'rows': [], 'empty': False}
    assert simulate(synthetic_bridge, [empty, empty])['searchEvidence'] != 'confirmed_absent'
    assert simulate(synthetic_bridge, [empty] * 6)['searchEvidence'] != 'confirmed_absent'
    assert simulate(synthetic_bridge, [empty] * 3 + [{**cleared, 'empty': True}] + [empty] * 3)['searchEvidence'] != 'confirmed_absent'
    assert simulate(synthetic_bridge, [empty] * 3 + [cleared] + [empty] * 3)['searchEvidence'] == 'confirmed_absent'
    exact = {'query': empty['query'], 'rows': ['학교 학생 생명클리닉']}
    assert simulate(synthetic_bridge, [empty] * 3 + [cleared] + [exact] * 3)['searchEvidence'] == 'unique_exact'


def test_duplicate_and_missing_main_window_are_not_absent(synthetic_bridge):
    room = '학교 학생 생명클리닉'
    assert simulate(synthetic_bridge, [{'query': room, 'rows': [room, room], 'empty': False}])['searchEvidence'] == 'ambiguous'
    assert simulate(synthetic_bridge, [{'query': room, 'rows': [], 'empty': True, 'mainWindow': False}] * 6)['searchEvidence'] != 'confirmed_absent'
    locked_empty = {'query': room, 'rows': [], 'empty': True, 'locked': True}
    assert simulate(synthetic_bridge, [locked_empty] * 3 + [{'query': '', 'rows': [], 'empty': False, 'locked': True}] + [locked_empty] * 3)['searchEvidence'] != 'confirmed_absent'


def report():
    return {'schoolName': '학교', 'studentName': '학생'}


def test_delayed_clinic_result_selects_only_original_room(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    result = native_kakao.create_clinic_job(3, 50, report())
    assert calls == ['학교 학생 생명클리닉']
    assert result['targetRoom'] == result['selectedRoom'] == calls[0]
    assert result['fallbackReason'] is None
    assert result['deliveryStatus'] == 'not_started'


@pytest.mark.parametrize('failure', [
    {'error': '검색 결과가 0개입니다.'},
    {'error': '화면 잠금'},
    {'error': '메인 창 부재'},
    {'error': '일치하는 검색 결과가 2개입니다.'},
    {'error': '검색 시간 초과'},
])
def test_uncertain_first_room_never_falls_back(monkeypatch, failure):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        return failure
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.create_clinic_job(3, 50, report())
    assert calls == ['학교 학생 생명클리닉']
    assert exc.value.target_room == calls[0]
    assert exc.value.selected_room is None
    assert exc.value.delivery_status == 'not_started'


def test_two_confirmed_absences_block_unverified_self_chat(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        return {'found': False, 'room': kw['room'], 'searchEvidence': 'confirmed_absent'}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.create_clinic_job(3, 50, report())
    assert calls == ['학교 학생 생명클리닉', '학교 학생 생명관리방', '본계정']
    assert exc.value.code == 'self_room_not_found'
    assert exc.value.fallback_reason == 'both_rooms_confirmed_absent'
    assert exc.value.selected_room is None


def test_confirmed_first_absence_selects_management_room(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        return {'found': False, 'room': kw['room'], 'searchEvidence': 'confirmed_absent'} if len(calls) == 1 else {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    result = native_kakao.create_clinic_job(3, 50, report())
    assert calls == ['학교 학생 생명클리닉', '학교 학생 생명관리방']
    assert result['selectedRoom'] == calls[1]
    assert result['fallbackReason'] == 'primary_confirmed_absent'


def test_delivery_timeout_reports_selected_room_and_unknown_status(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(command)
        if command == 'search':
            return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        raise subprocess.TimeoutExpired('mock bridge', 55)
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(3, 50, report())
    native_kakao.store_page(job['jobId'], 3, 50, 1, 'image/jpeg', b'\xff\xd8\xfffixture')
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.send_clinic_job(job['jobId'], 3, 50)
    assert calls == ['search', 'search', 'send']
    assert exc.value.target_room == exc.value.selected_room == job['targetRoom']
    assert exc.value.delivery_status == 'unknown'
    assert job['jobId'] not in native_kakao._jobs


def test_open_without_unique_search_evidence_never_creates_job(monkeypatch):
    monkeypatch.setattr(kakao_bridge, 'invoke', lambda command, **kw: {'opened': True, 'room': kw['room']})
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.create_clinic_job(3, 50, report())
    assert exc.value.code == 'recipient_unverified'
    assert exc.value.delivery_status == 'not_started'


def test_absence_evidence_for_other_room_cannot_trigger_fallback(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        return {'found': False, 'room': '다른 방', 'searchEvidence': 'confirmed_absent'}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.create_clinic_job(3, 50, report())
    assert calls == ['학교 학생 생명클리닉']
    assert exc.value.code == 'recipient_unverified'


def test_send_recheck_must_prove_exact_unique_destination(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(command)
        if command == 'search' and len(calls) == 1:
            return {'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'}
        return {'opened': True, 'room': '다른 방', 'searchEvidence': 'unique_exact'}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    job = native_kakao.create_clinic_job(3, 50, report())
    native_kakao.store_page(job['jobId'], 3, 50, 1, 'image/jpeg', b'\xff\xd8\xfffixture')
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.send_clinic_job(job['jobId'], 3, 50)
    assert calls == ['search', 'search']
    assert exc.value.code == 'recipient_unverified'


def test_error_http_contract_includes_recipient_evidence():
    from fastapi import HTTPException
    from personal_project.router import raise_native_kakao
    error = native_kakao.NativeKakaoError(409, 'not verified', 'recipient_unverified',
                                          target_room='original', fallback_reason='primary_confirmed_absent')
    with pytest.raises(HTTPException) as exc:
        raise_native_kakao(error)
    assert exc.value.detail == {'code': 'recipient_unverified', 'message': 'not verified',
                                'targetRoom': 'original', 'selectedRoom': None,
                                'fallbackReason': 'primary_confirmed_absent',
                                'deliveryStatus': 'not_started'}


def test_search_timeout_cannot_probe_next_room(monkeypatch):
    calls = []
    def invoke(command, **kw):
        calls.append(kw['room'])
        raise subprocess.TimeoutExpired('mock bridge', 55)
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    with pytest.raises(native_kakao.NativeKakaoError) as exc:
        native_kakao.create_clinic_job(3, 50, report())
    assert exc.value.code == 'recipient_timeout'
    assert exc.value.delivery_status == 'not_started'
    assert len(calls) == 1


@pytest.mark.parametrize('fail_on_search', [1, 2])
def test_generated_report_search_failure_logs_real_menu_shape(monkeypatch, tmp_path, caplog, fail_on_search, isolated_delivery_db):
    # Notification delivery has separate live coverage; this test counts report calls only.
    monkeypatch.setattr(kakao_bridge, "_notify_failure", lambda *args, **kwargs: None)
    from types import SimpleNamespace
    from fastapi import HTTPException
    from starlette.requests import Request
    from personal_project import report_pdf, router

    monkeypatch.setattr(router.repository, 'get_or_create_target_report', lambda *_: report())
    monkeypatch.setattr(router, '_target_report_pdf', lambda *_: b'%PDF-fixture')
    monkeypatch.setattr(report_pdf, 'render_pages', lambda *_args, **_kwargs: [b'\xff\xd8\xfffixture'])
    binary=tmp_path/'bridge'; binary.write_text('fixture')
    monkeypatch.setattr(kakao_bridge, 'BINARY', binary)
    menu={'menuFound':True,'menuOpenAttempted':True,'menuOpened':True,
          'actionItemFound':False,'actionItemEnabled':False,'actionAttempted':False,'actionSucceeded':False}
    result={'error':'카카오톡 편집 메뉴의 붙여넣기 동작을 확인하지 못했습니다.',
            'errorCode':'search_paste_menu_unavailable','uncertain':False,
            'diagnostics':{'stage':'paste-menu','menuActions':{'paste':menu},'searchText':'secret-fixture'}}
    calls=[]
    def run(*args, **kwargs):
        request=json.loads(kwargs['input'])
        calls.append(request['command'])
        if len(calls) < fail_on_search:
            return SimpleNamespace(stdout=json.dumps({'opened':True,'room':request['room'],'searchEvidence':'unique_exact'}))
        return SimpleNamespace(stdout=json.dumps(result))
    monkeypatch.setattr(kakao_bridge.subprocess, 'run', run)
    request=Request({'type':'http','method':'POST','path':'/',
                     'headers':[(b'origin',b'https://aura.chobab.app')]})
    with pytest.raises(HTTPException) as exc:
        router.send_server_generated_clinic_report(50, request, 3)
    assert exc.value.status_code == 409
    assert calls == ['search'] * fail_on_search
    assert 'error_code=search_paste_menu_unavailable' in caplog.text
    assert '"stage":"paste-menu"' in caplog.text
    for key, value in menu.items():
        assert f'"{key}":{str(value).lower()}' in caplog.text
    assert 'secret-fixture' not in caplog.text
    assert '학교 학생' not in caplog.text
    assert not native_kakao._jobs


def test_generated_report_store_failure_removes_temporary_clinic_job(monkeypatch, isolated_delivery_db):
    from fastapi import HTTPException
    from starlette.requests import Request
    from personal_project import report_pdf, router

    monkeypatch.setattr(router.repository, 'get_or_create_target_report', lambda *_: report())
    monkeypatch.setattr(router, '_target_report_pdf', lambda *_: b'%PDF-fixture')
    monkeypatch.setattr(report_pdf, 'render_pages', lambda *_args, **_kwargs: [b'page-fixture'])
    monkeypatch.setattr(kakao_bridge, 'invoke', lambda _command, **kw: {
        'opened': True, 'room': kw['room'], 'searchEvidence': 'unique_exact'
    })
    created_jobs = []
    create_clinic_job = native_kakao.create_clinic_job

    def track_created_job(*args, **kwargs):
        job = create_clinic_job(*args, **kwargs)
        created_jobs.append(native_kakao._jobs[job['jobId']].directory)
        return job

    monkeypatch.setattr(native_kakao, 'create_clinic_job', track_created_job)

    def fail_store(*_args, **_kwargs):
        raise ValueError('fixture page conversion failed')

    monkeypatch.setattr(native_kakao, 'store_page', fail_store)
    request = Request({'type': 'http', 'method': 'POST', 'path': '/',
                       'headers': [(b'origin', b'https://aura.chobab.app')]})
    with pytest.raises(HTTPException) as exc:
        router.send_server_generated_clinic_report(50, request, 3)

    assert exc.value.status_code == 413
    assert native_kakao._jobs == {}
    assert len(created_jobs) == 1
    assert not created_jobs[0].exists()
