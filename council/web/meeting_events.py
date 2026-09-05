"""Builds an ordered, typed transcript ("meeting events") purely by reading a
run's already-persisted artifact JSON files. This is read-only and additive:
it does not re-run or alter the pipeline, does not duplicate its business
logic, and works identically for a run made via the CLI or via the web UI.

Supports both pipelines - the original 5-round one and the 10-round one
(council/pipeline/orchestrator_extended.py) - dispatching on meta.json's
`round_count` (None/5 = legacy 5-round, 10 = extended). A run made before
this field existed has no meta.json round_count at all, so it defaults to
the legacy 5-round reader - full backward compatibility, nothing to migrate.

One event is emitted per "speaking turn" (one per provider call) for the
independent-proposal and cross-review rounds, and one event per individual
finding/response/changed-decision/consensus-item for the aggregate rounds -
those are the moments worth their own timeline entry in a real meeting. See
ROUND_LABELS_5/ROUND_LABELS_10 and the event `type` values for the taxonomy
the UI filters against.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from council.agents.display import display_name
from council.agents.loader import COUNCIL_ROLE_IDS
from council.pipeline.orchestrator import REVIEW_ASSIGNMENTS
from council.pipeline.orchestrator_extended import (
    R3_REVIEW_ASSIGNMENTS,
    R4_REVIEW_ASSIGNMENTS,
    ROUND_LABELS as ROUND_LABELS_10,
)

ROUND_LABELS_5 = {
    1: "Independent Proposal",
    2: "Cross Review",
    3: "Devil's Advocate",
    4: "Defense / Revision",
    5: "Consensus",
}

# Event `type` values, and which quick-filter each belongs to. Filter names
# match the product spec exactly: proposal / agree / disagree / risk /
# mind_change / decision / unresolved (+ all). "disagree" is broadened to
# also catch Devil's Advocate critiques and cross-review proposed changes -
# all three are forms of pushing back on the status quo. "defense" responses,
# the 10-round pipeline's "problem_understanding"/"alternative"/"convergence"
# events aren't given their own chip - they stay visible under "All"; the
# headline moments are the mind changes and decisions. "premortem" (10-round
# Round 8) is tagged has_risks=True since a failure scenario *is* a risk, so
# it surfaces under the Risk filter too.
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


class _EventBuilder:
    """Shared emit()/timestamp-cursor machinery for both round readers."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.calls = _load_calls_index(run_dir)
        self._call_i = 0
        self.events: list[dict] = []
        self._order = 0

    def next_timestamp(self) -> str | None:
        i = self._call_i
        self._call_i += 1
        if i < len(self.calls):
            return self.calls[i].get("timestamp") or None
        return None

    def emit(self, **kwargs) -> None:
        base = {
            "order": self._order,
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
        self.events.append(base)
        self._order += 1


def _emit_proposal_like(b: _EventBuilder, *, role_id: str, round_num: int, round_label: str, title: str, p: dict, ts) -> None:
    """Shared shape for anything that looks like a Proposal (requirements/
    decisions/edge_cases/risks/assumptions) - used by both the 5-round
    Round 1 and the 10-round Round 2."""
    b.emit(
        round=round_num,
        round_label=round_label,
        speaker_role=role_id,
        speaker_name=display_name(role_id),
        type="proposal",
        title=title,
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


def _emit_cross_review(b: _EventBuilder, *, reviewer_id: str, target_id: str, round_num: int, round_label: str, review: dict, ts) -> None:
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
    b.emit(
        round=round_num,
        round_label=round_label,
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


def _emit_devils_advocate(b: _EventBuilder, *, round_num: int, round_label: str, findings: list[dict], ts) -> None:
    for finding in findings:
        b.emit(
            round=round_num,
            round_label=round_label,
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


def _emit_defense(b: _EventBuilder, *, role_id: str, round_num: int, round_label: str, defense: dict, ts) -> None:
    for resp in defense.get("responses", []):
        stance = resp["stance"]
        title = {"defend": "Defended position", "revise": "Revised position", "partially_accept": "Partially accepted critique"}.get(stance, stance)
        b.emit(
            round=round_num,
            round_label=round_label,
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
        b.emit(
            round=round_num,
            round_label=round_label,
            speaker_role=role_id,
            speaker_name=display_name(role_id),
            type="mind_change",
            title=f"Mind change: {cd['topic'].replace('_', ' ')}",
            text=cd["reason"],
            details=[f"Before: {cd['old_decision']}", f"After: {cd['new_decision']}"],
            meta={"topic": cd["topic"], "triggered_by": cd["triggered_by"]},
            timestamp=ts,
        )


def _emit_consensus(b: _EventBuilder, *, round_num: int, round_label: str, items: list[dict], ts) -> None:
    for item in items:
        b.emit(
            round=round_num,
            round_label=round_label,
            speaker_role="moderator",
            speaker_name=display_name("moderator"),
            type="decision",
            title=f"Decision: {item['topic'].replace('_', ' ')} - {item['status'].upper()}",
            text=item["rationale"],
            details=(
                ([f"Decision: {item['decision']}"] if item.get("decision") else [])
                + [f"Evidence: {e}" for e in item.get("evidence", [])]
                + ([f"Dissent: {item['dissent']}"] if item.get("dissent") else [])
                + ([f"Implementation priority: {item['implementation_priority']}"] if item.get("implementation_priority") else [])
            ),
            meta={"topic": item["topic"], "status": item["status"]},
            timestamp=ts,
        )


def _build_events_5round(run_dir: Path) -> list[dict]:
    round1_dir = run_dir / "agents" / "round1"
    round1 = {rid: d for rid in COUNCIL_ROLE_IDS if (d := _read_json(round1_dir / f"{rid}.json")) is not None}
    if not round1:
        return []

    round2_dir = run_dir / "agents" / "round2"
    round4_dir = run_dir / "agents" / "round4"
    round3 = _read_json(run_dir / "debate" / "round3_devils_advocate.json") or {"findings": []}
    consensus = _read_json(run_dir / "consensus.json") or {"items": []}

    b = _EventBuilder(run_dir)

    for role_id in COUNCIL_ROLE_IDS:
        p = round1.get(role_id)
        if p is None:
            continue
        _emit_proposal_like(b, role_id=role_id, round_num=1, round_label=ROUND_LABELS_5[1], title="Independent proposal", p=p, ts=b.next_timestamp())

    for reviewer_id, targets in REVIEW_ASSIGNMENTS.items():
        for target_id in targets:
            review = _read_json(round2_dir / f"{reviewer_id}__reviews__{target_id}.json")
            ts = b.next_timestamp()
            if review is None:
                continue
            _emit_cross_review(b, reviewer_id=reviewer_id, target_id=target_id, round_num=2, round_label=ROUND_LABELS_5[2], review=review, ts=ts)

    _emit_devils_advocate(b, round_num=3, round_label=ROUND_LABELS_5[3], findings=round3.get("findings", []), ts=b.next_timestamp())

    for role_id in COUNCIL_ROLE_IDS:
        if role_id == "devils_advocate":
            continue
        defense = _read_json(round4_dir / f"{role_id}.json")
        ts = b.next_timestamp()
        if defense is None:
            continue
        _emit_defense(b, role_id=role_id, round_num=4, round_label=ROUND_LABELS_5[4], defense=defense, ts=ts)

    _emit_consensus(b, round_num=5, round_label=ROUND_LABELS_5[5], items=consensus.get("items", []), ts=b.next_timestamp())

    return b.events


def _build_events_10round(run_dir: Path) -> list[dict]:
    round1_dir = run_dir / "agents" / "round1"
    round1 = {rid: d for rid in COUNCIL_ROLE_IDS if (d := _read_json(round1_dir / f"{rid}.json")) is not None}
    if not round1:
        return []

    round2_dir = run_dir / "agents" / "round2"
    round3_dir = run_dir / "agents" / "round3"
    round4_dir = run_dir / "agents" / "round4"
    round6_dir = run_dir / "agents" / "round6"
    round7_dir = run_dir / "agents" / "round7"
    round8_dir = run_dir / "agents" / "round8"
    round5 = _read_json(run_dir / "debate" / "round5_devils_advocate.json") or {"findings": []}
    round9 = _read_json(run_dir / "debate" / "round9_convergence.json") or {}
    consensus = _read_json(run_dir / "consensus.json") or {"items": []}

    b = _EventBuilder(run_dir)

    # R1: Hiểu bài toán & giả định (own event type - not a solution proposal)
    for role_id in COUNCIL_ROLE_IDS:
        pu = round1.get(role_id)
        if pu is None:
            continue
        ts = b.next_timestamp()
        b.emit(
            round=1,
            round_label=ROUND_LABELS_10[1],
            speaker_role=role_id,
            speaker_name=display_name(role_id),
            type="problem_understanding",
            title="Hiểu bài toán & giả định",
            text=pu.get("interpretation", ""),
            details=(
                [f"Giả định: {a}" for a in pu.get("assumptions", [])]
                + [f"Câu hỏi làm rõ: {q}" for q in pu.get("clarifying_questions", [])]
                + [f"Chưa chắc chắn: {u}" for u in pu.get("uncertainty", [])]
            ),
            timestamp=ts,
        )

    # R2: Đề xuất giải pháp độc lập (same shape as the 5-round pipeline's R1)
    round2 = {rid: d for rid in COUNCIL_ROLE_IDS if (d := _read_json(round2_dir / f"{rid}.json")) is not None}
    for role_id in COUNCIL_ROLE_IDS:
        p = round2.get(role_id)
        if p is None:
            continue
        _emit_proposal_like(b, role_id=role_id, round_num=2, round_label=ROUND_LABELS_10[2], title="Đề xuất giải pháp", p=p, ts=b.next_timestamp())

    # R3 + R4: Phản biện chéo (2 lăng kính)
    for round_num, assignments, rdir in ((3, R3_REVIEW_ASSIGNMENTS, round3_dir), (4, R4_REVIEW_ASSIGNMENTS, round4_dir)):
        for reviewer_id, targets in assignments.items():
            for target_id in targets:
                review = _read_json(rdir / f"{reviewer_id}__reviews__{target_id}.json")
                ts = b.next_timestamp()
                if review is None:
                    continue
                _emit_cross_review(b, reviewer_id=reviewer_id, target_id=target_id, round_num=round_num, round_label=ROUND_LABELS_10[round_num], review=review, ts=ts)

    # R5: Devil's Advocate
    _emit_devils_advocate(b, round_num=5, round_label=ROUND_LABELS_10[5], findings=round5.get("findings", []), ts=b.next_timestamp())

    # R6: Phương án thay thế
    for role_id in COUNCIL_ROLE_IDS:
        alt = _read_json(round6_dir / f"{role_id}.json")
        ts = b.next_timestamp()
        if alt is None:
            continue
        b.emit(
            round=6,
            round_label=ROUND_LABELS_10[6],
            speaker_role=role_id,
            speaker_name=display_name(role_id),
            type="alternative",
            title=f"Phương án thay thế: {alt['primary_topic'].replace('_', ' ')}",
            text=alt["alternative_option"],
            details=[f"Trade-off: {t}" for t in alt.get("trade_offs", [])] + [f"Khuyến nghị: {alt['recommendation']} - {alt['rationale']}"],
            meta={"recommendation": alt["recommendation"]},
            timestamp=ts,
        )

    # R7: Bảo vệ & sửa quan điểm (same shape as the 5-round pipeline's R4)
    for role_id in COUNCIL_ROLE_IDS:
        if role_id == "devils_advocate":
            continue
        defense = _read_json(round7_dir / f"{role_id}.json")
        ts = b.next_timestamp()
        if defense is None:
            continue
        _emit_defense(b, role_id=role_id, round_num=7, round_label=ROUND_LABELS_10[7], defense=defense, ts=ts)

    # R8: Edge case & Pre-mortem (tagged has_risks so it surfaces under the Risk filter too)
    for role_id in COUNCIL_ROLE_IDS:
        finding = _read_json(round8_dir / f"{role_id}.json")
        ts = b.next_timestamp()
        if finding is None:
            continue
        b.emit(
            round=8,
            round_label=ROUND_LABELS_10[8],
            speaker_role=role_id,
            speaker_name=display_name(role_id),
            type="premortem",
            title=f"Pre-mortem [{finding['category']}, khả năng {finding['likelihood']}, tác động {finding['impact']}]",
            text=finding["failure_scenario"],
            details=[f"Nguyên nhân gốc rễ: {finding['root_cause']}"],
            meta={"category": finding["category"], "likelihood": finding["likelihood"], "impact": finding["impact"]},
            has_risks=True,
            timestamp=ts,
        )

    # R9: Hội tụ (Convergence) - single synthesis event
    ts = b.next_timestamp()
    if round9:
        b.emit(
            round=9,
            round_label=ROUND_LABELS_10[9],
            speaker_role="moderator",
            speaker_name=display_name("moderator"),
            type="convergence",
            title="Hội tụ trước khi chốt đồng thuận",
            text=round9.get("synthesis_note", ""),
            details=(
                [f"Mâu thuẫn chưa giải quyết: {c}" for c in round9.get("unresolved_conflicts", [])]
                + [f"Phụ thuộc: {d}" for d in round9.get("decision_dependencies", [])]
            ),
            meta={"ready_for_consensus": round9.get("ready_for_consensus")},
            timestamp=ts,
        )

    # R10: Moderator - Đồng thuận cuối
    _emit_consensus(b, round_num=10, round_label=ROUND_LABELS_10[10], items=consensus.get("items", []), ts=b.next_timestamp())

    return b.events


def build_events(run_dir: Path) -> list[dict]:
    """Reconstructs the full (unfiltered, unpaginated) event list for a
    council-mode run. Returns [] for a run directory that has no round1 data
    (e.g. a single-agent run - those aren't "meetings", see meeting_store).
    Dispatches on meta.json's round_count: 10 -> the extended pipeline
    reader, anything else (including a missing/legacy meta.json) -> the
    original 5-round reader, so every run made before this field existed
    keeps working unchanged."""
    meta = _read_json(run_dir / "meta.json") or {}
    if meta.get("round_count") == 10:
        return _build_events_10round(run_dir)
    return _build_events_5round(run_dir)


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
