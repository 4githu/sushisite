# odi/db/schema.py

from typing import Any, Literal

from pydantic import BaseModel, Field


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