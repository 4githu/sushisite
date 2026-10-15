"""Logical audience configuration; no Unity coordinates or client inputs added."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AudienceRuntimeState, ClipPoolCatalog


def validate_audience_count(count: int) -> int:
    if type(count) is not int or not 1 <= count <= 50:
        raise ValueError("audience_count must be a strict integer from 1 to 50")
    return count


def resolve_audience_count(snapshot: dict | None) -> int:
    if snapshot is None:
        return 6
    if not isinstance(snapshot, dict):
        raise ValueError("template_snapshot must be an object")
    if "audience" not in snapshot:
        return 6
    audience = snapshot["audience"]
    if not isinstance(audience, dict):
        raise ValueError("snapshot audience must be an object")
    if "audience_count" not in audience:
        return 6
    return validate_audience_count(audience["audience_count"])


def build_audience_layout(count: int) -> tuple[tuple[str, str, str], ...]:
    """Contiguous balanced thirds, alternating left/right within each logical row.

    Six actors retain front 01/02, middle 03/04, rear 05/06. Larger rows
    reuse the existing seat categories; these are not unique physical seats.
    """
    validate_audience_count(count)
    rows = ("front", "middle", "rear")
    row_counts = [0, 0, 0]
    layout = []
    for index in range(count):
        row_index = index * 3 // count
        seat = "left" if row_counts[row_index] % 2 == 0 else "right"
        layout.append((f"audience_{index + 1:02d}", rows[row_index], seat))
        row_counts[row_index] += 1
    return tuple(layout)


def bind_audience_catalog(
    catalog: ClipPoolCatalog, audiences: list[AudienceRuntimeState],
) -> ClipPoolCatalog:
    """Bind ACT08's legacy 05/06 gate to this population's actual rear actors.

    Keep the on-disk catalog and the entire six-actor path unchanged. Rear
    adjacency/pair eligibility is checked separately by the reaction scheduler.
    """
    if len(audiences) == 6:
        return catalog
    bound = catalog.model_copy(deep=True)
    rear_ids = sorted(a.agent_id for a in audiences if a.profile.row == "rear")
    paired_rear_ids = set(rear_ids[:len(rear_ids) - len(rear_ids) % 2])
    for clip in bound.actions:
        if clip.behavior_id == "ACT_08":
            clip.scene_gate.allowed_agents = paired_rear_ids or None
            if not paired_rear_ids:
                # An empty row gate admits nobody, including an unpaired rear.
                clip.scene_gate.allowed_rows = set()
    return bound
