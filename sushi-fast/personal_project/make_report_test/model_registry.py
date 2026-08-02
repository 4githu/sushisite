from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ReportModel:
    id: str
    provider: str
    label: str
    description: str
    is_default: bool = False
    explicit_cache: bool = False
    key_env: str = "GEMINI_API_KEY"


REPORT_MODELS = (
    ReportModel(
        id="gemini-3.5-flash-lite",
        provider="gemini",
        label="Gemini Flash-Lite · 저가",
        description="기본 모델 · 저렴한 구조화 JSON 생성",
        is_default=True,
    ),
    ReportModel(
        id="gpt-5-nano",
        provider="openai",
        label="OpenAI GPT-5 nano",
        description="OpenAI의 저비용 텍스트 모델",
        key_env="OPENAI_API_KEY",
    ),
    ReportModel(
        id="claude-3-5-haiku-latest",
        provider="anthropic",
        label="Claude 3.5 Haiku",
        description="Anthropic의 빠른 저비용 모델",
        key_env="ANTHROPIC_API_KEY",
    ),
)


def _key_from_env_file(name: str) -> str | None:
    path = Path(__file__).resolve().parents[2] / ".env"
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


def model_options() -> list[dict]:
    result = []
    for model in REPORT_MODELS:
        value = asdict(model)
        value.pop("key_env", None)
        available = bool(os.getenv(model.key_env) or _key_from_env_file(model.key_env))
        value["available"] = available
        value["unavailable_reason"] = None if available else f"{model.key_env}가 필요합니다."
        result.append(value)
    return result


def get_report_model(model_id: str) -> ReportModel:
    for model in REPORT_MODELS:
        if model.id == model_id:
            return model
    allowed = ", ".join(model.id for model in REPORT_MODELS)
    raise ValueError(f"지원하지 않는 리포트 모델입니다: {model_id} (가능: {allowed})")


def default_model_id() -> str:
    return next(model.id for model in REPORT_MODELS if model.is_default)
