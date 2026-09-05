"""Role Catalog: the 6 debating roles, the Moderator, and the ChatGPT
Observer, each with description, skills, and a runtime/provider + status
badge.

Deliberately keeps role/skill data (council/agents/skills.yaml,
role_skill_overrides.json) and runtime/provider data
(council/web/provider_status.py) as two separate sources merged only here,
for display - editing one never touches the other.

The ChatGPT Observer is NOT a pipeline participant (it never calls a
provider, never speaks in any round) - it is a synthetic catalog entry
representing the read-only summary feature itself (council/web/observer.py),
listed here so the product's full role lineup is visible in one place, per
the product spec. Its "runtime" is deliberately not an LLM provider - it
reads already-computed artifacts/events, deterministically, in V0.
"""
from __future__ import annotations

from council.agents import role_overrides
from council.agents.loader import load_council_roles, load_moderator
from council.agents.skills import skills_for_role
from council.web.provider_status import default_provider_name, provider_status_by_name

OBSERVER_ROLE_ID = "chatgpt_observer"


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
            "role_type": role_type,  # "debater" (rounds 1-4) | "moderator" (round 5) | "observer" (read-only)
            "status": status,  # whether this role participates in every meeting (V0: always "active")
            "runtime_provider": provider_name,
            "runtime_provider_status": provider["status"],
            "runtime_model": provider.get("default_model"),
        }

    roles = [_entry(r, role_type="debater", status="active") for r in load_council_roles()]
    roles.append(_entry(load_moderator(), role_type="moderator", status="active"))

    observer_skills = [s.id for s in skills_for_role(OBSERVER_ROLE_ID)]
    roles.append(
        {
            "id": OBSERVER_ROLE_ID,
            "display_name": "ChatGPT Observer",
            "description": (
                "Reads meeting state (transcript/events/artifacts) and produces a concise summary for the "
                "human - current round, key agreements/disagreements, mind changes, critical risks, and "
                "decisions waiting for a human choice. Not a debate participant: it never speaks in a round "
                "and never decides anything - the human always makes the final call."
            ),
            "focus_areas": ["reading meeting state", "flagging what needs human attention", "never deciding"],
            "skills": role_overrides.effective_skills(OBSERVER_ROLE_ID, observer_skills),
            "role_type": "observer",
            "status": "active",
            "runtime_provider": "deterministic",  # reads artifacts/events directly in V0, no LLM call
            "runtime_provider_status": "ready",
            "runtime_model": None,
        }
    )

    return {
        "roles": roles,
        "runtime_note": (
            "V0 chạy toàn bộ council trên một provider dùng chung (không chọn riêng theo role); "
            "chọn provider riêng cho từng role là tính năng dự kiến ở V1. ChatGPT Observer "
            "là một bộ tổng hợp deterministic riêng biệt trong V0 - không gọi LLM."
        ),
        "default_provider": provider_name,
        "default_provider_status": provider["status"],
    }
