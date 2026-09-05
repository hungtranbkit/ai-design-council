"""Loads agent role configs from council/agents/roles/*.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROLES_DIR = Path(__file__).parent / "roles"

# The 6 debating council members, in a fixed, stable order used throughout the
# pipeline (round1 iteration order, report ordering, etc).
COUNCIL_ROLE_IDS = (
    "product_ba",
    "ux_designer",
    "architect",
    "business_critic",
    "qa_security",
    "devils_advocate",
)


@dataclass
class RoleConfig:
    id: str
    display_name: str
    description: str
    system_prompt: str
    focus_areas: list[str] = field(default_factory=list)
    default_skills: list[str] = field(default_factory=list)
    round1_instructions: str = ""
    round2_instructions: str = ""
    round3_instructions: str = ""
    round4_instructions: str = ""
    round5_instructions: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> "RoleConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            display_name=data["display_name"],
            description=data.get("description", "").strip(),
            system_prompt=data.get("system_prompt", "").strip(),
            focus_areas=list(data.get("focus_areas", [])),
            default_skills=list(data.get("default_skills", [])),
            round1_instructions=data.get("round1_instructions", "").strip(),
            round2_instructions=data.get("round2_instructions", "").strip(),
            round3_instructions=data.get("round3_instructions", "").strip(),
            round4_instructions=data.get("round4_instructions", "").strip(),
            round5_instructions=data.get("round5_instructions", "").strip(),
        )


_CACHE: dict[str, RoleConfig] = {}


def load_role(role_id: str) -> RoleConfig:
    if role_id not in _CACHE:
        path = ROLES_DIR / f"{role_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"no role config for '{role_id}' at {path}")
        _CACHE[role_id] = RoleConfig.from_yaml(path)
    return _CACHE[role_id]


def load_council_roles() -> list[RoleConfig]:
    """The 6 debating agents, in fixed order."""
    return [load_role(rid) for rid in COUNCIL_ROLE_IDS]


def load_moderator() -> RoleConfig:
    return load_role("moderator")


def load_solo_designer() -> RoleConfig:
    return load_role("solo_designer")
