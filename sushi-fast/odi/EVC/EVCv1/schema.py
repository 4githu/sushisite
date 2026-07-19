from typing import Any
from pydantic import BaseModel, Field, field_validator


class AudienceState(BaseModel):
    E: float = Field(description="-1~1, Engagement")
    V: float = Field(description="-1~1, Evaluative Valence")
    C: float = Field(description="-1~1, Cognitive Clarity")

    @field_validator("E", "V", "C")
    @classmethod
    def clamp_state(cls, value: float) -> float:
        return max(-1.0, min(1.0, value))


class AudiencePersona(BaseModel):
    id: int
    persona: dict[str, Any] = Field(default_factory=dict)


class AudienceEVC(BaseModel):
    id: int
    state: AudienceState
    currentThought: str = ""
    overallImpression: str = ""


class EVCState(BaseModel):
    summary_delta : str
    audiences: list[AudienceEVC]
