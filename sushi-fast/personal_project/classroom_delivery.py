"""Daily 09:00 KST delivery in the existing backend process and Kakao lock."""
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from . import aura_classroom_outbox as outbox, native_kakao, repository
from .aura_classroom_input import read_owner_rounds

CONFIG_PATH = Path(os.getenv("AURA_CLASSROOM_CONFIG_PATH", str(Path(__file__).resolve().parents[1] / ".runtime/aura-classroom.json")))
logger = logging.getLogger(__name__)
_stop = threading.Event()
_thread = None
_initialized = False
_last_state = "starting"


def settings():
    if not CONFIG_PATH.is_file():
        return {"enabled": False}
    data = json.loads(CONFIG_PATH.read_text())
    if not isinstance(data.get("owner_id"), int) or isinstance(data.get("owner_id"), bool) or data["owner_id"] <= 0:
        raise ValueError("invalid classroom owner configuration")
    return data


def configure(owner_id, enabled):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    value = {"owner_id": owner_id, "enabled": bool(enabled), "hour_kst": 9,
             "room": outbox.PRIMARY_ROOM, "purpose": outbox.PURPOSE}
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.chmod(0o600)
    temporary.replace(CONFIG_PATH)
    return {"enabled": value["enabled"], "hourKst": 9, "targetRoom": outbox.PRIMARY_ROOM}


def preview(owner_id, now=None):
    now = now or datetime.now(outbox.KST)
    plan = outbox.compose(now, read_owner_rounds(owner_id, now))
    return {"targetRoom": outbox.PRIMARY_ROOM, **plan}


def _bridge(command, **args):
    if os.getenv("DISABLE_KAKAO_BRIDGE") == "1":
        raise RuntimeError("Native Kakao bridge is disabled")
    from .kakao_bridge import invoke
    return invoke(command, redact_errors=True, operation_id="classroom_request", **args)


def run_once(now=None):
    global _initialized
    config = settings()
    if not config.get("enabled"):
        return {"state": "disabled"}
    now = now or datetime.now(outbox.KST)
    if now.astimezone(outbox.KST).hour != 9:
        return {"state": "outside_window"}
    # Same process as all existing Kakao actions: approval does not bypass their lock.
    if not native_kakao._send_lock.acquire(blocking=False):
        return {"state": "transport_busy"}
    try:
        with repository.connection() as db:
            if not _initialized:
                outbox.init(db)
                _initialized = True
            existing = outbox.status(db, config["owner_id"], now.astimezone(outbox.KST).date().isoformat())
            if existing:
                return existing
            health = _bridge("status")
            if not isinstance(health, dict) or health.get("trusted") is not True:
                return {"state": "setup_required", "reason": "accessibility_required"}
            if health.get("running") is not True:
                return {"state": "waiting_for_kakao"}
            if health.get("locked") is not False:
                return {"state": "waiting_for_unlock"}
            return outbox.tick(db, config["owner_id"], now,
                               lambda owner: read_owner_rounds(owner, now), _bridge, approved=True)
    finally:
        native_kakao._send_lock.release()


def status(owner_id):
    config = settings()
    if config.get("owner_id") != owner_id:
        config = {"enabled": False}
    today = datetime.now(outbox.KST).date().isoformat()
    with repository.connection() as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='aura_classroom_outbox'").fetchone()
        result = outbox.status(db, owner_id, today) if exists else None
    return {"enabled": bool(config.get("enabled")), "hourKst": 9,
            "targetRoom": outbox.PRIMARY_ROOM, "today": result, "runtimeState": _last_state}


def _loop():
    global _last_state
    last = None
    while not _stop.is_set():
        try:
            result = run_once()
            _last_state = result.get("state", "unknown")
            key = (result.get("state"), result.get("reason"), result.get("runDate"))
            if key != last:
                logger.info("classroom scheduler state=%s reason=%s run_date=%s", *key)
                last = key
        except Exception as error:
            # No exception strings: bridge and source exceptions may contain private data.
            logger.error("classroom scheduler error_type=%s", type(error).__name__)
        _stop.wait(30)


def start():
    global _thread, _last_state
    if os.getenv("DISABLE_KAKAO_BRIDGE") == "1":
        _last_state = "disabled_by_environment"
        return
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="aura-classroom-scheduler", daemon=True)
        _thread.start()


def stop():
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2)


class AutomationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def build_router(owner_dependency, read_owner_dependency):
    router = APIRouter(prefix="/aura/classroom-requests", tags=["aura-classroom-requests"])

    @router.get("/status")
    def get_status(owner_id: int = Depends(read_owner_dependency)):
        return status(owner_id)

    @router.post("/preview")
    def get_preview(response: Response, owner_id: int = Depends(owner_dependency)):
        response.headers["Cache-Control"] = "no-store"
        return preview(owner_id)

    @router.post("/automation")
    def set_automation(data: AutomationSettings, owner_id: int = Depends(owner_dependency)):
        return configure(owner_id, data.enabled)

    router.add_event_handler("startup", start)
    router.add_event_handler("shutdown", stop)
    return router
