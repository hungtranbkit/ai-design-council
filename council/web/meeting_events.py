"""Builds an ordered, typed transcript ("meeting events") purely by reading a
run's already-persisted artifact JSON files. This is read-only and additive:
it does not re-run or alter the pipeline, does not duplicate its business
logic, and works identically for a run made via the CLI or via the web UI
(as long as the run has agents/round1..4 + debate/round3 + consensus.json -
runs made before `calls.json` existed still work, just without real
per-event timestamps).

One event is emitted per "speaking turn" (one per provider call) for rounds
1 and 2, and one event per individual finding/response/changed-decision/
consensus-item for rounds 3-5 - those are the moments worth their own
timeline entry in a real meeting. See the module-level ROUND_LABELS and the
event `type` values for the taxonomy the UI filters against.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from council.agents.display import display_name
from council.pipeline.orchestrator import REVIEW_ASSIGNMENTS
from council.agents.loader import COUNCIL_ROLE_IDS

ROUND_LABELS = {
    1: "Independent Proposal",
    2: "Cross Review",
    3: "Devil's Advocate",
    4: "Defense / Revision",
    5: "Consensus",
}

# Event `type` values, and which quick-filter each belongs to. Filter names
# match the product spec exactly: proposal / agree / disagree / risk /
# mind_change / decision / unresolved (+ all). "disagree" is broadened to
# also catch Devil's Advocate critiques and round-2 proposed changes - all
# three are forms of pushing back on the status quo. Round-4 "defense"
# responses (defend/partially_accept) aren't given their own chip - they stay
# visible under "All"; the headline round-4 moments are the mind changes.
#
# "agree" needs the same has_* flag treatment as "risk": CrossReview's own
# schema validator requires at least one of disagree/missing_requirements/
# proposed_changes on every review (pure agreement is rejected), so
# "agreement" can never be an event's *dominant* type in practice - a review
# that partially agrees while still pushing back would otherwise be
# invisible to this filter. has_agreements catches that partial-agreement
# content regardless of the event's dominant type.
FILTER_TYPES = {
    "all": None,  # everything
    "proposal": {"proposal"},
    "agree": {"agreement"},  # plus any event with has_agreements=True
    "disagree": {"disagreement", "critique", "proposed_change"},
    "risk": {"risk"},  # plus any event with has_risks=True
    "mind_change": {"mind_change"},
    "decision": {"decision"},  # any status (accepted/rejected/unresolved)
    "unresolved": {"decision"},  # further filtered to meta.status == "unresolved" below
}


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_calls_index(run_dir: Path) -> list[dict]:
    """Returns the persisted calls.json list, or [] if this run predates it."""
    calls = _read_json(run_dir / "calls.json")
    return calls or []


def build_events(run_dir: Path) -> list[dict]:
    """Reconstructs the full (unfiltered, unpaginated) event list for a
    council-mode run. Returns [] for a run directory that has no round1 data
    (e.g. a single-agent run - those aren't "meetings", see meeting_store)."""
    round1_dir = run_dir / "agents" / "round1"
    if not round1_dir.exists():
        return []

    round1 = {}
    for role_id in COUNCIL_ROLE_IDS:
        data = _read_json(round1_dir / f"{role_id}.json")
        if data is not None:
            round1[role_id] = data
    if not round1:
        return []

    round2_dir = run_dir / "agents" / "round2"
    round4_dir = run_dir / "agents" / "round4"
    round3 = _read_json(run_dir / "debate" / "round3_devils_advocate.json") or {"findings": []}
    consensus = _read_json(run_dir / "consensus.json") or {"items": []}
    calls = _load_calls_index(run_dir)
    # calls.json records calls strictly in execution order matching the loops
    # below, so we can pull timestamps out by position as we go.
    call_cursor = {"i": 0}

    def next_timestamp() -> str | None:
        i = call_cursor["i"]
        call_cursor["i"] += 1
        if i < len(calls):
            return calls[i].get("timestamp") or None
        return None

    events: list[dict] = []
    order = 0

    def emit(**kwargs) -> None:
        nonlocal order
        base = {
            "order": order,
            "target_role": None,
            "target_name": None,
            "details": [],
            "meta": {},
            "has_risks": False,
            "has_disagreement": False,
            "has_agreements": False,
            "timestamp": None,
        }
        base.update(kwargs)
        events.append(base)
        order += 1

    # --- Round 1: Independent Proposal (1 event per role) -------------------
    for role_id in COUNCIL_ROLE_IDS:
        p = round1.get(role_id)
        if p is None:
            continue
        ts = next_timestamp()
        emit(
            round=1,
            round_label=ROUND_LABELS[1],
            speaker_role=role_id,
            speaker_name=display_name(role_id),
            type="proposal",
            title="Independent proposal",
            text=p.get("summary", ""),
            details=(
                [f"Requirement: {r}" for r in p.get("requirements", [])]
                + [f"Decision: {d}" for d in p.get("decisions", [])]
                + [f"Edge case: {e}" for e in p.get("edge_cases", [])]
                + [f"Risk: {r}" for r in p.get("risks", [])]
                + [f"Assumption: {a}" for a in p.get("assumptions", [])]
            ),
            has_risks=bool(p.get("risks")),
            timestamp=ts,
        )

    # --- Round 2: Cross Review (1 event per reviewer->target call) ---------
    for reviewer_id, targets in REVIEW_ASSIGNMENTS.items():
        for target_id in targets:
            key = f"{reviewer_id}__reviews__{target_id}"
            review = _read_json(round2_dir / f"{key}.json")
            ts = next_timestamp()
            if review is None:
                continue
            if review.get("disagree"):
                dom_type, title = "disagreement", "Disagreement"
            elif review.get("missing_requirements") or review.get("proposed_changes"):
                dom_type, title = "proposed_change", "Proposed change"
            elif review.get("risks"):
                dom_type, title = "risk", "Risk flagged"
            else:
                dom_type, title = "agreement", "Agreement"
            details = (
                [f"Agree: {a}" for a in review.get("agree", [])]
                + [f"Disagree: {d}" for d in review.get("disagree", [])]
                + [f"Missing: {m}" for m in review.get("missing_requirements", [])]
                + [f"Risk: {r}" for r in review.get("risks", [])]
                + [f"Proposed change: {c}" for c in review.get("proposed_changes", [])]
            )
            emit(
                round=2,
                round_label=ROUND_LABELS[2],
                speaker_role=reviewer_id,
                speaker_name=display_name(reviewer_id),
                target_role=target_id,
                target_name=display_name(target_id),
                type=dom_type,
                title=f"{title} (reviewing {display_name(target_id)})",
                text=(review.get("disagree") or review.get("proposed_changes") or review.get("agree") or [""])[0],
                details=details,
                has_risks=bool(review.get("risks")),
                has_disagreement=bool(review.get("disagree")),
                has_agreements=bool(review.get("agree")),
                timestamp=ts,
            )

    # --- Round 3: Devil's Advocate (1 event per finding) --------------------
    ts = next_timestamp()  # single call produced all findings
    for finding in round3.get("findings", []):
        emit(
            round=3,
            round_label=ROUND_LABELS[3],
            speaker_role="devils_advocate",
            speaker_name=display_name("devils_advocate"),
            target_role=finding.get("target_role"),
            target_name=display_name(finding["target_role"]) if finding.get("target_role") else None,
            type="critique",
            title=f"Critique: {finding['category'].replace('_', ' ')} ({finding['severity']})",
            text=finding["description"],
            meta={"category": finding["category"], "severity": finding["severity"]},
            timestamp=ts,
        )

    # --- Round 4: Defense / Revision (1 event per response + per mind change)
    for role_id in COUNCIL_ROLE_IDS:
        if role_id == "devils_advocate":
            continue
        defense = _read_json(round4_dir / f"{role_id}.json")
        ts = next_timestamp()
        if defense is None:
            continue
        for resp in defense.get("responses", []):
            stance = resp["stance"]
            title = {"defend": "Defended position", "revise": "Revised position", "partially_accept": "Partially accepted critique"}.get(stance, stance)
            emit(
                round=4,
                round_label=ROUND_LABELS[4],
                speaker_role=role_id,
                speaker_name=display_name(role_id),
                type="defense",
                title=f"{title} (re: {resp['critique_source']})",
                text=resp["rationale"],
                details=[f"Critique: {resp['critique_summary']}"],
                meta={"stance": stance, "critique_source": resp["critique_source"]},
                timestamp=ts,
            )
        for cd in defense.get("changed_decisions", []):
            emit(
                round=4,
                round_label=ROUND_LABELS[4],
                speaker_role=role_id,
                speaker_name=display_name(role_id),
                type="mind_change",
                title=f"Mind change: {cd['topic'].replace('_', ' ')}",
                text=cd["reason"],
                details=[f"Before: {cd['old_decision']}", f"After: {cd['new_decision']}"],
                meta={"topic": cd["topic"], "triggered_by": cd["triggered_by"]},
                timestamp=ts,
            )

    # --- Round 5: Consensus (1 event per topic) -----------------------------
    ts = next_timestamp()
    for item in consensus.get("items", []):
        emit(
            round=5,
            round_label=ROUND_LABELS[5],
            speaker_role="moderator",
            speaker_name=display_name("moderator"),
            type="decision",
            title=f"Decision: {item['topic'].replace('_', ' ')} - {item['status'].upper()}",
            text=item["rationale"],
            details=(
                ([f"Decision: {item['decision']}"] if item.get("decision") else [])
                + [f"Evidence: {e}" for e in item.get("evidence", [])]
                + ([f"Dissent: {item['dissent']}"] if item.get("dissent") else [])
            ),
            meta={"topic": item["topic"], "status": item["status"]},
            timestamp=ts,
        )

    return events


def events_matching(events: list[dict], filter_name: str) -> list[dict]:
    filter_name = (filter_name or "all").lower()
    if filter_name not in FILTER_TYPES or FILTER_TYPES[filter_name] is None:
        return events
    wanted_types = FILTER_TYPES[filter_name]
    if filter_name == "risk":
        return [e for e in events if e["type"] in wanted_types or e.get("has_risks")]
    if filter_name == "agree":
        return [e for e in events if e["type"] in wanted_types or e.get("has_agreements")]
    if filter_name == "unresolved":
        return [e for e in events if e["type"] in wanted_types and e.get("meta", {}).get("status") == "unresolved"]
    return [e for e in events if e["type"] in wanted_types]
