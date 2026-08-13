from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import EVC_DEBUG_LOG, EVC_DEBUG_LOG_DIR, EVC_DEBUG_RETENTION_DAYS
from .schema import EVCUpdateResponseV2


logger = logging.getLogger("sushisite.evc")


def build_update_log_event(
    response: EVCUpdateResponseV2,
    *,
    latency_ms: float,
    stt_provider: str,
    evaluation_provider: str,
) -> dict:
    return {
        "event": "evc_update_completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(response.session_id),
        "request_id": str(response.request_id),
        "step": response.step,
        "latency_ms": round(latency_ms, 3),
        "stt_provider": stt_provider,
        "evaluation_provider": evaluation_provider,
        "warning_codes": list(response.warnings),
        "no_op_reason": response.no_op_reason,
        "aggregate_state": response.evc_state.model_dump(),
        "selected_variations": [
            {
                "agent_id": decision.agent_id,
                "core": (
                    decision.core_behavior.variation_id
                    if decision.core_behavior is not None
                    else None
                ),
                "action": (
                    decision.action_overlay.variation_id
                    if decision.action_overlay is not None
                    else None
                ),
            }
            for decision in response.audiences
        ],
        "command_count": len(response.commands),
    }


def record_update(
    response: EVCUpdateResponseV2,
    *,
    latency_ms: float,
    stt_provider: str,
    evaluation_provider: str,
) -> None:
    """Emit metadata only; observability must never fail a pipeline request."""

    try:
        event = build_update_log_event(
            response,
            latency_ms=latency_ms,
            stt_provider=stt_provider,
            evaluation_provider=evaluation_provider,
        )
        logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        if EVC_DEBUG_LOG:
            session_dir = EVC_DEBUG_LOG_DIR / str(response.session_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            path = session_dir / f"step_{response.step:04d}_{response.request_id}.json"
            path.write_text(
                json.dumps(event, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            prune_debug_logs(EVC_DEBUG_LOG_DIR, EVC_DEBUG_RETENTION_DAYS)
    except Exception:
        logger.exception("failed to record EVC observability metadata")


def prune_debug_logs(directory: Path, retention_days: int, now: float | None = None) -> int:
    if retention_days <= 0 or not directory.exists():
        return 0
    threshold = (time.time() if now is None else now) - retention_days * 86400
    removed = 0
    for path in directory.rglob("*.json"):
        try:
            if path.stat().st_mtime < threshold:
                path.unlink()
                removed += 1
        except OSError:
            continue
    for child in sorted(directory.rglob("*"), reverse=True):
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    return removed
