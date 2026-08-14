from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .schema import ActionClipSpec, ClipPoolCatalog, CoreClipSpec


DEFAULT_CLIP_POOL_PATH = Path(__file__).with_name("clip_pool.json")
EXPECTED_CORE_VARIATIONS = 44
EXPECTED_ACTION_VARIATIONS = 8


@lru_cache(maxsize=4)
def load_clip_pool(path: str | Path | None = None) -> ClipPoolCatalog:
    """Load and validate the complete reaction-rule clip catalog."""

    resolved = Path(path) if path is not None else DEFAULT_CLIP_POOL_PATH
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"EVC clip pool does not exist: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"EVC clip pool is not valid JSON: {resolved}: {exc}") from exc

    catalog = ClipPoolCatalog.model_validate(raw)
    if len(catalog.core) != EXPECTED_CORE_VARIATIONS:
        raise RuntimeError(
            f"EVC core clip pool must contain {EXPECTED_CORE_VARIATIONS} variations; "
            f"found {len(catalog.core)}"
        )
    if len(catalog.actions) != EXPECTED_ACTION_VARIATIONS:
        raise RuntimeError(
            f"EVC action clip pool must contain {EXPECTED_ACTION_VARIATIONS} variations; "
            f"found {len(catalog.actions)}"
        )

    expected_action_ids = {f"ACT_{index:02d}" for index in range(1, 9)}
    actual_action_ids = {clip.behavior_id for clip in catalog.actions}
    if actual_action_ids != expected_action_ids:
        raise RuntimeError(
            "EVC action pool must contain exactly ACT_01 through ACT_08; "
            f"found {sorted(actual_action_ids)}"
        )

    return catalog


def find_core_clip(catalog: ClipPoolCatalog, variation_id: str) -> CoreClipSpec:
    for clip in catalog.core:
        if clip.variation_id == variation_id:
            return clip
    raise KeyError(f"Unknown EVC core variation_id: {variation_id}")


def find_action_clip(catalog: ClipPoolCatalog, variation_id: str) -> ActionClipSpec:
    for clip in catalog.actions:
        if clip.variation_id == variation_id:
            return clip
    raise KeyError(f"Unknown EVC action variation_id: {variation_id}")


def validate_default_clip_pool() -> None:
    """Application-start hook that fails fast on an invalid catalog."""

    load_clip_pool()
