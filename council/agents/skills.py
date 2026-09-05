"""Skill catalog loader - data-driven, backs the Roles & Skills web UI.

Kept separate from the pipeline (roles/loader.py, orchestrator.py, mock.py):
skills are descriptive metadata shown in the UI and attached to roles for
display purposes. In V0 they do not alter MockProvider's deterministic
script - see council/web/role_overrides.py docstring for why, and the README
"Known V0 limitation" note.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_PATH = Path(__file__).parent / "skills.yaml"


@dataclass(frozen=True)
class SkillConfig:
    id: str
    name: str
    description: str


_CACHE: list[SkillConfig] | None = None


def load_skills() -> list[SkillConfig]:
    global _CACHE
    if _CACHE is None:
        data = yaml.safe_load(SKILLS_PATH.read_text(encoding="utf-8"))
        _CACHE = [SkillConfig(id=s["id"], name=s["name"], description=s.get("description", "")) for s in data["skills"]]
    return _CACHE


def skills_by_id() -> dict[str, SkillConfig]:
    return {s.id: s for s in load_skills()}
