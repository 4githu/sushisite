import json
import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from personal_project.reader_translation import _validate_payload
from personal_project.reader_translation import hermes_plugin
from personal_project.reader_translation.hermes_plugin import _validate_request


def test_server_and_plugin_preserve_neighbor_context_and_original_segment():
    segment = {'id': 'p9-original', 'text': 'enging by NAC', 'context_before': 'ROS scav -', 'context_after': ' further evidence.'}
    payload = {'segments': [segment], 'target_language': 'ko'}
    server, _ = _validate_payload(payload)
    plugin, _ = _validate_request(json.dumps(payload).encode())
    assert server == [segment]
    assert plugin == [segment]


@pytest.mark.parametrize('field', ['context_before', 'context_after', 'previous_translation'])
@pytest.mark.parametrize('bad', [None, 5, {}, 'x' * 1001])
def test_invalid_context_rejected_in_both_layers(field, bad):
    payload = {'segments': [{'id': 's', 'text': 'valid', field: bad}]}
    with pytest.raises(HTTPException):
        _validate_payload(payload)
    with pytest.raises(ValueError):
        _validate_request(json.dumps(payload).encode())


def test_combined_budget_includes_repeated_context():
    segments = [{'id': str(i), 'text': 'x', 'previous_translation': 'x' * 1000} for i in range(20)]
    with pytest.raises(HTTPException) as exc:
        _validate_payload({'segments': segments})
    assert exc.value.status_code == 413
    with pytest.raises(ValueError):
        _validate_request(json.dumps({'segments': segments}).encode())
    segments.pop()
    assert len(_validate_payload({'segments': segments})[0]) == 19
    assert len(_validate_request(json.dumps({'segments': segments}).encode())[0]) == 19


def test_legacy_payload_unchanged():
    payload = {'segments': [{'id': 'legacy', 'text': 'The cat.'}]}
    assert _validate_payload(payload)[0] == payload['segments']
    assert _validate_request(json.dumps(payload).encode())[0] == payload['segments']


def test_handler_passes_context_as_data_and_validates_mapping(monkeypatch, capsys):
    seen = {}
    def complete(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(text=json.dumps({'translations': [{'id': 'b', 'text': '둘'}, {'id': 'a', 'text': '하나'}]}))
    payload = {'segments': [{'id': 'a', 'text': 'scav -', 'context_after': 'enging by NAC'}, {'id': 'b', 'text': 'enging by NAC', 'context_before': 'scav -'}], 'target_language': 'Korean'}
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps(payload)))
    assert hermes_plugin._handle(SimpleNamespace(llm=SimpleNamespace(complete=complete)), None) == 0
    result = json.loads(capsys.readouterr().out)
    assert [item['id'] for item in result['translations']] == ['a', 'b']
    assert json.loads(seen['messages'][1]['content'])['segments'] == payload['segments']
    assert 'only to interpret' in seen['messages'][0]['content']


def test_previous_translation_is_preserved_as_reference():
    payload = {'segments': [{'id': 'p9-right', 'text': 'enging by NAC', 'context_before': 'ROS scav -', 'previous_translation': 'ROS 소거가'}]}
    assert _validate_payload(payload)[0] == payload['segments']
    assert _validate_request(json.dumps(payload).encode())[0] == payload['segments']
