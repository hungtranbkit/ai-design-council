"""Role Catalog: the 6 debating roles + the Moderator/ChatGPT Observer,
each with description, skills, and a runtime/provider + status badge.

Deliberately keeps role/skill data (council/agents/skills.yaml,
role_skill_overrides.json) and runtime/provider data
(council/web/provider_status.py) as two separate sources merged only here,
for display - editing one never touches the other.
"""
from __future__ import annotations

from council.agents import role_overrides
from council.agents.loader import load_council_roles, load_moderator
from council.web.provider_status import default_provider_name, provider_status_by_name


def build_role_catalog() -> dict:
    provider_name = default_provider_name()
    provider = provider_status_by_name(provider_name) or {"status": "planned", "default_model": None}

    def _entry(role, *, role_type: str, status: str) -> dict:
        return {
            "id": role.id,
            "display_name": role.display_name,
            "description": role.description,
            "focus_areas": role.focus_areas,
            "skills": role_overrides.effective_skills(role.id, role.default_skills),
            "role_type": role_type,  # "debater" (rounds 1-4) | "moderator" (round 5 + observer feed)
            "status": status,  # whether this role participates in every meeting (V0: always "active")
            "runtime_provider": provider_name,
            "runtime_provider_status": provider["status"],
            "runtime_model": provider.get("default_model"),
        }

    roles = [_entry(r, role_type="debater", status="active") for r in load_council_roles()]
    roles.append(_entry(load_moderator(), role_type="moderator", status="active"))

    return {
        "roles": roles,
        "runtime_note": (
            "V0 runs the whole council on one shared provider (not per-role); "
            "per-role provider selection is a planned V1 feature."
        ),
        "default_provider": provider_name,
        "default_provider_status": provider["status"],
    }
