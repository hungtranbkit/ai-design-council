"""Renders the text user_prompt sent to a provider for a given round.

MockProvider ignores this text and answers from structured `context` directly;
real LLM providers rely on this text (plus the JSON-schema instruction added
in council/providers/_llm_common.py) to know what to do. Keeping this
rendering in one place means a real provider gets the same information the
mock's `context` dict encodes, just as prose.
"""
from __future__ import annotations

import json
from typing import Any


def render_round1_prompt(brief_text: str, instructions: str) -> str:
    return (
        f"{instructions}\n\n"
        "You may NOT see any other agent's output in this round - this is an "
        "independent proposal.\n\n"
        f"--- PROJECT BRIEF ---\n{brief_text}\n"
    )


def render_round2_prompt(brief_text: str, instructions: str, target_role: str, target_proposal: dict[str, Any]) -> str:
    return (
        f"{instructions}\n\n"
        f"You are reviewing the proposal from: {target_role}\n\n"
        f"--- PROJECT BRIEF ---\n{brief_text}\n\n"
        f"--- {target_role}'S PROPOSAL ---\n{json.dumps(target_proposal, indent=2)}\n"
    )


def render_round3_prompt(
    brief_text: str,
    instructions: str,
    proposals: dict[str, Any],
    reviews: dict[str, dict[str, Any]],
) -> str:
    return (
        f"{instructions}\n\n"
        f"--- PROJECT BRIEF ---\n{brief_text}\n\n"
        f"--- ALL ROUND 1 PROPOSALS ---\n{json.dumps(proposals, indent=2)}\n\n"
        f"--- ALL ROUND 2 CROSS-REVIEWS ---\n{json.dumps(reviews, indent=2)}\n"
    )


def render_round4_prompt(
    brief_text: str,
    instructions: str,
    own_proposal: dict[str, Any],
    critiques_received: list[dict[str, Any]],
) -> str:
    return (
        f"{instructions}\n\n"
        f"--- PROJECT BRIEF ---\n{brief_text}\n\n"
        f"--- YOUR ROUND 1 PROPOSAL ---\n{json.dumps(own_proposal, indent=2)}\n\n"
        f"--- CRITIQUES YOU RECEIVED (round 2 + round 3) ---\n{json.dumps(critiques_received, indent=2)}\n"
    )


def render_round5_prompt(
    brief_text: str,
    instructions: str,
    proposals: dict[str, Any],
    reviews: dict[str, dict[str, Any]],
    devils_advocate_report: dict[str, Any],
    defenses: dict[str, Any],
) -> str:
    return (
        f"{instructions}\n\n"
        f"--- PROJECT BRIEF ---\n{brief_text}\n\n"
        f"--- ROUND 1 PROPOSALS ---\n{json.dumps(proposals, indent=2)}\n\n"
        f"--- ROUND 2 CROSS-REVIEWS ---\n{json.dumps(reviews, indent=2)}\n\n"
        f"--- ROUND 3 DEVIL'S ADVOCATE REPORT ---\n{json.dumps(devils_advocate_report, indent=2)}\n\n"
        f"--- ROUND 4 DEFENSES/REVISIONS ---\n{json.dumps(defenses, indent=2)}\n"
    )


def render_solo_prompt(brief_text: str, instructions: str) -> str:
    return f"{instructions}\n\n--- PROJECT BRIEF ---\n{brief_text}\n"
