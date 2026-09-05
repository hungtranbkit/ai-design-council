"""Request/response models for the web API. Kept separate from
council/pipeline/schemas.py - those are the pipeline's data contract between
agents; these are the web layer's HTTP contract with the browser (and with
an external ChatGPT reading /summary)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class NewMeetingRequest(BaseModel):
    brief_text: str = Field(min_length=1)
    brief_name: str = "session"
    provider: str = "mock"
    model: str | None = None  # overrides the provider's default model; ignored for provider="mock"
    role_skills: dict[str, list[str]] = Field(default_factory=dict)
    playback_enabled: bool = True


class DecisionInput(BaseModel):
    topic: str
    human_choice: str  # "approve" | "reject" | "defer" | "pending" | "acknowledge"
    note: str = ""


class DecisionsRequest(BaseModel):
    decisions: list[DecisionInput]


class RoleSkillsUpdate(BaseModel):
    role_id: str
    skill_ids: list[str]
