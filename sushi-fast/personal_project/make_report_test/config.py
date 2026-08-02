from __future__ import annotations

import os
from pathlib import Path

from .model_registry import default_model_id


HERE = Path(__file__).resolve().parent
PERSONAL_PROJECT_DIR = HERE.parent
DB_PATH = PERSONAL_PROJECT_DIR / "personal_project.db"
PROMPT_PATH = HERE / "report_prompt.txt"
PROMPT_RULES_PATH = HERE / "prompt_rules.txt"
ENV_PATH = HERE.parents[1] / ".env"

# API 키 외 설정을 환경변수로 흩어 놓지 않도록 안정적인 기본값은 코드에 둔다.
DEFAULT_MODEL = default_model_id()
DEFAULT_CACHE_TTL_SECONDS = 86_400
DEFAULT_TEMPERATURE = 0.2
CACHE_KEY = "aura_clinic_report_json_v3"


class ConfigurationError(RuntimeError):
    pass


def read_named_api_key(name: str, path: Path = ENV_PATH) -> str | None:
    """python-dotenv 없이 sushi-fast/.env의 API 키 한 항목만 읽는다."""
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'") or None
    return None


def _read_api_key_file(path: Path = ENV_PATH) -> str | None:
    return read_named_api_key("GEMINI_API_KEY", path)


def get_api_key(explicit_key: str | None = None) -> str:
    key = explicit_key or os.getenv("GEMINI_API_KEY") or _read_api_key_file()
    if not key:
        raise ConfigurationError(
            "GEMINI_API_KEY가 없습니다. sushi-fast/.env에 "
            "GEMINI_API_KEY=... 한 줄만 추가하거나 --api-key를 사용하세요."
        )
    return key
