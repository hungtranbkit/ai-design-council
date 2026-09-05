"""User-editable skill assignment overrides for the Roles & Skills web screen.

Deliberately NOT stored back into council/agents/roles/*.yaml: those files
carry hand-tuned system_prompt/instructions text that MockProvider's demo
script and the pipeline depend on verbatim, and a yaml.safe_dump round-trip
would reformat (and risk corrupting) that prose. Overrides live in their own
small JSON file instead, merged over each role's `default_skills` at read
time. Editing this file changes what the UI *displays* for a role's skills;
it does not change MockProvider's deterministic behavior (see README's V0
limitations note).
"""
from __future__ import annotations

import json
from pathlib import Path

OVERRIDES_PATH = Path(__file__).parent / "role_skill_overrides.json"


def load_overrides() -> dict[str, list[str]]:
    if not OVERRIDES_PATH.exists():
        return {}
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def save_overrides(overrides: dict[str, list[str]]) -> None:
    OVERRIDES_PATH.write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def effective_skills(role_id: str, default_skills: list[str]) -> list[str]:
    overrides = load_overrides()
    return overrides.get(role_id, default_skills)


def set_role_skills(role_id: str, skill_ids: list[str]) -> dict[str, list[str]]:
    overrides = load_overrides()
    overrides[role_id] = skill_ids
    save_overrides(overrides)
    return overrides
