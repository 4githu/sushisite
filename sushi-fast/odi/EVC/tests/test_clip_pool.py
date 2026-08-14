import json

import pytest
from pydantic import ValidationError

from odi.EVC.clip_pool import find_action_clip, find_core_clip, load_clip_pool
from odi.EVC.schema import ClipPoolCatalog


def test_default_clip_pool_contains_every_spec_variation() -> None:
    catalog = load_clip_pool()

    assert len(catalog.core) == 44
    assert len(catalog.actions) == 8
    assert len({clip.variation_id for clip in [*catalog.core, *catalog.actions]}) == 52
    assert {clip.behavior_id for clip in catalog.actions} == {
        f"ACT_{index:02d}" for index in range(1, 9)
    }
    assert {clip.behavior_id.split("_")[0] for clip in catalog.core} == {
        "BL",
        "AL",
        "EM",
        "CT",
    }


def test_every_variation_has_a_complete_unity_layer_mapping() -> None:
    catalog = load_clip_pool()

    for clip in [*catalog.core, *catalog.actions]:
        assert clip.channels == {action.layer for action in clip.unity_actions}
        assert all(action.duration > 0 for action in clip.unity_actions)


def test_scene_constraints_are_encoded_for_laptop_and_rear_row_actions() -> None:
    catalog = load_clip_pool()

    typing = find_action_clip(catalog, "ACT_01.laptop_typing")
    side_conversation = find_action_clip(catalog, "ACT_08.side_conversation")

    assert typing.scene_gate.requires_laptop is True
    assert side_conversation.scene_gate.allowed_agents == {
        "audience_05",
        "audience_06",
    }
    assert side_conversation.scene_gate.allowed_rows == {"rear"}


def test_representative_core_mappings_preserve_contract_ids() -> None:
    catalog = load_clip_pool()

    nod = find_core_clip(catalog, "CT_01.comprehension_nod")
    skeptical = find_core_clip(catalog, "EM_05.skeptical_monitoring")

    assert nod.behavior_id == "CT_01"
    assert nod.unity_actions[0].action_id == "body.comprehension_nod"
    assert skeptical.critical is True


def test_catalog_rejects_duplicate_variation_ids() -> None:
    catalog = load_clip_pool()
    raw = catalog.model_dump(mode="json")
    raw["core"].append(raw["core"][0])

    with pytest.raises(ValidationError):
        ClipPoolCatalog.model_validate(json.loads(json.dumps(raw)))
