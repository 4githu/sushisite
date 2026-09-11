# odi/db/schema.py

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


JsonDict = dict[str, Any]


class UserCreateRequest(BaseModel):
    user_id: str | int
    auth_id: str | int | None = None
    config: JsonDict
    recent_template: JsonDict | None = None


class LoginRequest(BaseModel):
    auth_id: str | int


class ConfigUpdateRequest(BaseModel):
    config: JsonDict

    @field_validator("config")
    @classmethod
    def validate_stt_preference(cls, value: JsonDict) -> JsonDict:
        provider = value.get("preferences", {}).get("stt_provider")
        if provider is not None and provider not in ("deepgram", "azure"):
            raise ValueError("preferences.stt_provider must be deepgram or azure")
        return value


class RecentTemplateUpdateRequest(BaseModel):
    template: JsonDict | None = None


class TemplateCreateRequest(BaseModel):
    owner_id: str | int
    template_id: str | None = None
    template: JsonDict


class TemplateUpdateRequest(BaseModel):
    template: JsonDict


class PreSessionStartRequest(BaseModel):
    user_id: str | int
    expires_minutes: int = Field(default=30, ge=1, le=180)


class PreSessionStateUpdateRequest(BaseModel):
    state: Literal["waiting", "running", "finished", "expired", "cancelled"]


class PreSessionFinishRequest(BaseModel):
    user_id: str | int
    feedback: JsonDict


class SessionCreateRequest(BaseModel):
    user_id: str | int
    template_id: str | None = None
    template: JsonDict
    feedback: JsonDict | None = None
    state: Literal["running", "completed", "failed", "cancelled"] = "completed"


class SessionFinishRequest(BaseModel):
    feedback: JsonDict


class SessionMediaUpdateRequest(BaseModel):
    video_url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=200)
    source: Literal["demo", "recording", "upload", "external"] = "external"
