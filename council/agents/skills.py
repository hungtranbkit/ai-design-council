"""Skill catalog loader - data-driven, backs the Skill Catalog + Role Catalog
web UI.

Kept separate from the pipeline (roles/loader.py, orchestrator.py, mock.py):
skills are descriptive metadata shown in the UI and attached to roles for
display purposes. In V0 they do not alter MockProvider's deterministic
script - see council/agents/role_overrides.py docstring for why, and the
README "Known V0 limitation" note.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKILLS_PATH = Path(__file__).parent / "skills.yaml"


@dataclass(frozen=True)
class SkillConfig:
    id: str
    name: str
    description: str
    category: str = "general"
    recommended_roles: tuple[str, ...] = ()
    enabled: bool = True
    prompt_fragment: str | None = None


_CACHE: list[SkillConfig] | None = None


def load_skills() -> list[SkillConfig]:
    global _CACHE
    if _CACHE is None:
        data = yaml.safe_load(SKILLS_PATH.read_text(encoding="utf-8"))
        _CACHE = [
            SkillConfig(
                id=s["id"],
                name=s["name"],
                description=s.get("description", ""),
                category=s.get("category", "general"),
                recommended_roles=tuple(s.get("recommended_roles", [])),
                enabled=s.get("enabled", True),
                prompt_fragment=s.get("prompt_fragment"),
            )
            for s in data["skills"]
        ]
    return _CACHE


def skills_by_id() -> dict[str, SkillConfig]:
    return {s.id: s for s in load_skills()}


def skills_for_role(role_id: str) -> list[SkillConfig]:
    """Skills whose recommended_roles include this role id - the pool a
    role's default_skills is drawn from."""
    return [s for s in load_skills() if role_id in s.recommended_roles]


def skills_by_category() -> dict[str, list[SkillConfig]]:
    grouped: dict[str, list[SkillConfig]] = {}
    for s in load_skills():
        grouped.setdefault(s.category, []).append(s)
    return grouped
