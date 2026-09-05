"""Metrics computation for a council run and a solo run, plus per-round trajectory."""
from __future__ import annotations

from typing import Any

from council.pipeline.orchestrator import CallRecord, CouncilRunResult
from council.pipeline.single_agent import SoloRunResult


def _dedup(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        norm = item.strip().lower()
        if norm not in [s.strip().lower() for s in seen]:
            seen.append(item)
    return seen


def _calls_summary(calls: list[CallRecord]) -> dict[str, Any]:
    tokens_in = sum(c.tokens_in or 0 for c in calls)
    tokens_out = sum(c.tokens_out or 0 for c in calls)
    costs = [c.estimated_cost_usd for c in calls if c.estimated_cost_usd is not None]
    total_cost = round(sum(costs), 6) if costs else None
    total_latency = round(sum(c.latency_seconds for c in calls), 4)
    return {
        "call_count": len(calls),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost_usd": total_cost,
        "provider_latency_seconds": total_latency,
    }


def compute_council_metrics(result: CouncilRunResult) -> dict[str, Any]:
    round1 = result.round1
    round2 = result.round2
    round4 = result.round4
    round5 = result.round5

    all_requirements: list[str] = []
    all_edge_cases: list[str] = []
    all_risks: list[str] = []
    for p in round1.values():
        all_requirements.extend(p.requirements)
        all_edge_cases.extend(p.edge_cases)
        all_risks.extend(p.risks)
    for tmap in round2.values():
        for review in tmap.values():
            all_requirements.extend(review.missing_requirements)
            all_risks.extend(review.risks)

    requirements_count = len(_dedup(all_requirements))
    edge_cases_count = len(_dedup(all_edge_cases))
    risks_count = len(_dedup(all_risks))
    unresolved_count = len(round5.by_status("unresolved"))
    accepted_count = len(round5.by_status("accepted"))
    rejected_count = len(round5.by_status("rejected"))
    mind_changes_count = sum(len(d.changed_decisions) for d in round4.values())

    trajectory = [
        {"round": 1, "label": "independent_proposals", "requirements_count": requirements_count, "edge_cases_count": edge_cases_count, "risks_count": risks_count, "mind_changes_count": 0, "unresolved_count": None},
        {"round": 2, "label": "cross_review", "requirements_count": requirements_count, "edge_cases_count": edge_cases_count, "risks_count": risks_count, "mind_changes_count": 0, "unresolved_count": None},
        {"round": 3, "label": "devils_advocate", "findings_count": len(result.round3.findings), "categories_covered": sorted(result.round3.covered_categories())},
        {"round": 4, "label": "defense_revision", "mind_changes_count": mind_changes_count},
        {"round": 5, "label": "consensus", "accepted_count": accepted_count, "rejected_count": rejected_count, "unresolved_count": unresolved_count},
    ]

    return {
        "mode": "council",
        "requirements_count": requirements_count,
        "edge_cases_count": edge_cases_count,
        "risks_count": risks_count,
        "unresolved_count": unresolved_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "mind_changes_count": mind_changes_count,
        "devils_advocate_findings_count": len(result.round3.findings),
        "devils_advocate_categories_covered": sorted(result.round3.covered_categories()),
        "duration_seconds": round(result.wall_time_seconds, 4),
        **_calls_summary(result.calls),
        "trajectory": trajectory,
    }


def compute_solo_metrics(result: SoloRunResult) -> dict[str, Any]:
    d = result.design
    return {
        "mode": "single-agent",
        "requirements_count": len(_dedup(d.requirements)),
        "edge_cases_count": len(_dedup(d.edge_cases)),
        "risks_count": len(_dedup(d.risks)),
        "unresolved_count": len(d.open_questions),
        "accepted_count": None,
        "rejected_count": None,
        "mind_changes_count": 0,
        "devils_advocate_findings_count": None,
        "devils_advocate_categories_covered": [],
        "duration_seconds": round(result.wall_time_seconds, 4),
        **_calls_summary(result.calls),
        "trajectory": [
            {"round": 1, "label": "solo_design", "requirements_count": len(_dedup(d.requirements)), "edge_cases_count": len(_dedup(d.edge_cases)), "risks_count": len(_dedup(d.risks))}
        ],
    }
