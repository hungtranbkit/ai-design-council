"""Shared role_id -> human-readable display name, used by both the CLI report
renderer and the web UI so the two never drift apart."""
from __future__ import annotations

DISPLAY_NAMES: dict[str, str] = {
    "product_ba": "Product/BA",
    "ux_designer": "UX Designer",
    "architect": "Architect",
    "business_critic": "Business Critic",
    "qa_security": "QA + Security",
    "devils_advocate": "Devil's Advocate",
    "moderator": "Moderator / ChatGPT Observer",
    "solo_designer": "Solo Designer",
}


def display_name(role_id: str) -> str:
    return DISPLAY_NAMES.get(role_id, role_id)
