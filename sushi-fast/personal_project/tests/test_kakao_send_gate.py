"""Run the real Swift send gate with inert snapshots; never invoke Kakao/AX/clipboard."""
import json
import subprocess
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[3] / "ops/kakao_bridge.swift"
ROOM = "synthetic-target"
GOOD = {"session": {"CGSSessionScreenIsLocked": False},
        "windows": [ROOM], "composerOwned": True, "buttonOwned": True,
        "frontmostTargetApp": True, "keyWindowOwned": True, "buttonBoundsOwned": True,
        "composerFocused": True, "buttonEnabled": True}


@pytest.mark.parametrize("samples,final,expected_clicks", [
    ([False, True], True, 1),
    ([False, False], True, 0),
    ([None], True, 0),
    ([True], False, 0),
    ([True], None, 0),
])
def test_readiness_and_final_gate_fail_closed(bridge, samples, final, expected_clicks):
    stages = [{**GOOD, "buttonEnabled": item} for item in samples]
    result = simulate(bridge, readiness=stages, last={**GOOD, "buttonEnabled": final})
    assert result["clicks"] == expected_clicks
    assert result["committed"] is (expected_clicks == 1)
    assert result["uncertain"] is False


@pytest.mark.parametrize("change", [
    {"windows": ["other-room"]}, {"composerOwned": False},
    {"composerFocused": False}, {"frontmostTargetApp": False},
    {"keyWindowOwned": False}, {"session": {"CGSSessionScreenIsLocked": True}},
])
def test_readiness_context_change_never_clicks(bridge, change):
    result = simulate(bridge, readiness=[{**GOOD, "buttonEnabled": False},
                                         {**GOOD, **change, "buttonEnabled": True}])
    assert result["clicks"] == 0
    assert result["committed"] is False
    assert result["uncertain"] is False


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    binary = tmp_path_factory.mktemp("send-gate") / "bridge"
    subprocess.run(["swiftc", str(SOURCE), "-o", str(binary)], check=True, timeout=120)
    return binary


def simulate(bridge, kind="text", first=None, last=None, **extra):
    payload = {"command": "send-simulation", "kind": kind, "room": ROOM,
               "stages": [GOOD if first is None else first, GOOD if last is None else last], **extra}
    proc = subprocess.run([str(bridge)], input=json.dumps(payload), text=True,
                          capture_output=True, timeout=10)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


@pytest.mark.parametrize("session", [None, {}, {"CGSSessionScreenIsLocked": None},
                                     {"CGSSessionScreenIsLocked": 0},
                                     {"CGSSessionScreenIsLocked": "false"},
                                     {"CGSSessionScreenIsLocked": True}])
@pytest.mark.parametrize("kind", ["text", "attachment"])
def test_lock_observation_fail_closed_before_preparation_and_click(bridge, kind, session):
    bad = {**GOOD, "session": session}
    assert simulate(bridge, kind, first=bad) == {
        "clicks": 0, "committed": False, "uncertain": False, "manualCheck": False}
    assert simulate(bridge, kind, last=bad) == {
        "clicks": 0, "committed": False, "uncertain": False, "manualCheck": True}


@pytest.mark.parametrize("kind", ["text", "attachment"])
@pytest.mark.parametrize("change", [
    {"windows": []}, {"windows": [ROOM, ROOM]}, {"windows": ["other-room"]},
    {"composerOwned": False}, {"buttonOwned": False},
    {"frontmostTargetApp": False}, {"keyWindowOwned": False},
    {"buttonBoundsOwned": False},
])
def test_preclick_window_or_control_change_never_clicks(bridge, kind, change):
    result = simulate(bridge, kind, last={**GOOD, **change})
    assert result == {"clicks": 0, "committed": False, "uncertain": False,
                      "manualCheck": True}


@pytest.mark.parametrize("kind", ["text", "attachment"])
def test_only_explicit_unlocked_unique_room_clicks_once(bridge, kind):
    assert simulate(bridge, kind) == {"clicks": 1, "committed": True, "uncertain": False}
    assert simulate(bridge, kind, clickFails=True) == {
        "clicks": 1, "committed": False, "uncertain": True, "manualCheck": True}


def test_only_kakao_line_start_list_rendering_is_equivalent(bridge):
    result = simulate(bridge, expectedText="synthetic title\n- synthetic amount: $123.45",
                      actualText="synthetic title\n•\tsynthetic amount: $123.45")
    assert result == {"clicks": 1, "committed": True, "uncertain": False,
                      "textMatches": True}


@pytest.mark.parametrize(("expected", "actual"), [
    ("synthetic title\n- synthetic amount: $123.45",
     "synthetic title\n•\tsynthetic amount: $123.46"),
    ("synthetic title\n- exact synthetic body",
     "synthetic title\n•\tchanged synthetic body"),
    ("synthetic  body", "synthetic body"),
    ("prefix - synthetic item", "prefix •\tsynthetic item"),
    ("synthetic café", "synthetic cafe\u0301"),
])
def test_composer_equivalence_rejects_amount_body_or_other_differences(bridge, expected, actual):
    result = simulate(bridge, expectedText=expected, actualText=actual)
    assert result == {"clicks": 0, "committed": False, "uncertain": False,
                      "manualCheck": True, "textMatches": False}


def test_missing_text_comparison_operand_fails_closed(bridge):
    payload = {"command": "send-simulation", "kind": "text", "room": ROOM,
               "stages": [GOOD, GOOD], "expectedText": "synthetic text"}
    proc = subprocess.run([str(bridge)], input=json.dumps(payload), text=True,
                          capture_output=True, timeout=10)
    result = json.loads(proc.stdout)
    assert proc.returncode != 0
    assert result["committed"] is False
    assert result["uncertain"] is False
    assert result["manualCheck"] is False


def test_missing_private_lock_key_requires_explicit_console_and_owned_login(bridge):
    evidence = {"IOConsoleLocked": False, "sessionOnConsole": True, "sessionLoginDone": True, "sessionOwnedByCaller": True}
    good = {**GOOD, "session": evidence}
    assert simulate(bridge, first=good, last=good)["clicks"] == 1
    for key, bad in [("IOConsoleLocked", True), ("IOConsoleLocked", 0), ("sessionOnConsole", False), ("sessionLoginDone", False), ("sessionOwnedByCaller", False)]:
        invalid = {**GOOD, "session": {**evidence, key: bad}}
        assert simulate(bridge, last=invalid)["clicks"] == 0
    for key in evidence:
        incomplete = {k: v for k, v in evidence.items() if k != key}
        assert simulate(bridge, last={**GOOD, "session": incomplete})["clicks"] == 0
    contradictory = {**evidence, "CGSSessionScreenIsLocked": True}
    assert simulate(bridge, last={**GOOD, "session": contradictory})["clicks"] == 0


@pytest.mark.parametrize("kind", ["text", "attachment"])
def test_click_error_is_reconciled_only_with_observed_delivery(bridge, kind):
    assert simulate(bridge, kind, clickFails=True, deliveryObserved=True) == {
        "clicks": 1, "committed": True, "uncertain": False}
    assert simulate(bridge, kind, clickFails=True, deliveryObserved=False) == {
        "clicks": 1, "committed": False, "uncertain": True, "manualCheck": True}


@pytest.mark.parametrize("kind", ["text", "attachment"])
def test_successful_ax_return_without_delivery_remains_uncertain(bridge, kind):
    assert simulate(bridge, kind, deliveryObserved=False) == {
        "clicks": 1, "committed": False, "uncertain": True, "manualCheck": True}


@pytest.mark.parametrize("kind", ["text", "attachment"])
def test_receipt_cannot_override_a_failed_recipient_gate(bridge, kind):
    result = simulate(bridge, kind, last={**GOOD, "windows": ["other-room"]}, deliveryObserved=True)
    assert result["clicks"] == 0
    assert result["uncertain"] is False


def test_status_contains_only_non_sensitive_input_diagnostics(bridge):
    proc = subprocess.run([str(bridge)], input=json.dumps({"command": "status"}), text=True,
                          capture_output=True, timeout=10)
    assert proc.returncode == 0
    status = json.loads(proc.stdout)
    assert set(status) == {
        "trusted", "running", "locked", "eventPostingPreflightAllowed",
        "secureEventInputEnabled", "modifiers", "uid",
    }
    for key in ("trusted", "running", "locked", "eventPostingPreflightAllowed", "secureEventInputEnabled"):
        assert type(status[key]) is bool
    assert set(status["modifiers"]) == {"command", "shift", "option", "control"}
    assert all(type(value) is bool for value in status["modifiers"].values())
    assert type(status["uid"]) is int
