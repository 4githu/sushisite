from __future__ import annotations

import os
from pathlib import Path


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")


OPENAI_EVC_MODEL = os.getenv("OPENAI_EVC_MODEL", "gpt-4.1-nano")
DEEPGRAM_PRIMARY_MODEL = os.getenv("DEEPGRAM_PRIMARY_MODEL", "nova-3")
EVC_DEBUG_LOG = _bool_env(
    "EVC_DEBUG_LOG",
    _bool_env("DEBUG_EVC_LOG", False),
)
EVC_INCLUDE_DIAGNOSTICS = _bool_env("EVC_INCLUDE_DIAGNOSTICS", False)
EVC_SESSION_TTL_S = _int_env("EVC_SESSION_TTL_S", 7200)
EVC_MAX_SESSIONS = _int_env("EVC_MAX_SESSIONS", 100)
EVC_MAX_AUDIO_BYTES = _int_env("EVC_MAX_AUDIO_BYTES", 15 * 1024 * 1024)
EVC_MAX_SLIDE_BYTES = _int_env("EVC_MAX_SLIDE_BYTES", 25 * 1024 * 1024)
EVC_STT_TIMEOUT_S = _int_env("EVC_STT_TIMEOUT_S", 30)
EVC_LLM_TIMEOUT_S = _int_env("EVC_LLM_TIMEOUT_S", 20)
EVC_PROVIDER_RETRIES = _int_env("EVC_PROVIDER_RETRIES", 1, minimum=0)
EVC_DEBUG_RETENTION_DAYS = _int_env("EVC_DEBUG_RETENTION_DAYS", 7)
EVC_UPLOAD_DIR = Path(os.getenv("EVC_UPLOAD_DIR", "evc_uploads"))
EVC_DEBUG_LOG_DIR = Path(os.getenv("EVC_DEBUG_LOG_DIR", "evc_logs"))
