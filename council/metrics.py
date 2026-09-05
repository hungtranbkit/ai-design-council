"""Metrics computation for a council run and a solo run, plus per-round trajectory."""
from __future__ import annotations

from typing import Any

from council.pipeline.orchestrator import CallRecord, CouncilRunResult
from council.pipeline.orchestrator_extended import ExtendedCouncilRunResult
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


def compute_extended_council_metrics(result: ExtendedCouncilRunResult) -> dict[str, Any]:
    """Metrics for the 10-round pipeline. Keeps every field name from the
    5-round pipeline's compute_council_metrics (so any code/report reading
    metrics.json generically keeps working), and adds the new fields the
    deeper pipeline calls for - all deterministic counts over real data,
    never estimated/guessed."""
    round2, round3, round4 = result.round2, result.round3, result.round4
    round5, round6, round7 = result.round5, result.round6, result.round7
    round8, round10 = result.round8, result.round10

    all_requirements: list[str] = []
    all_edge_cases: list[str] = []
    all_risks: list[str] = []
    all_disagreements: list[str] = []
    all_proposed_changes: list[str] = []
    for p in round2.values():
        all_requirements.extend(p.requirements)
        all_edge_cases.extend(p.edge_cases)
        all_risks.extend(p.risks)
    for tmap in list(round3.values()) + list(round4.values()):
        for review in tmap.values():
            all_requirements.extend(review.missing_requirements)
            all_risks.extend(review.risks)
            all_disagreements.extend(review.disagree)
            all_proposed_changes.extend(review.proposed_changes)

    requirements_count = len(_dedup(all_requirements))
    edge_cases_count = len(_dedup(all_edge_cases))
    risks_count = len(_dedup(all_risks))
    disagreements_count = len(all_disagreements)
    # "Arguments" = every explicit piece of pushback raised across the whole
    # debate: cross-review disagreements/proposed changes plus every
    # mandatory Devil's Advocate finding.
    arguments_count = len(all_disagreements) + len(all_proposed_changes) + len(round5.findings)
    alternatives_count = len(round6)  # schema already enforces >=2 trade-offs each
    assumptions_stated_count = sum(len(pu.assumptions) for pu in result.round1.values())
    assumptions_challenged_count = sum(1 for f in round5.findings if f.category == "hidden_assumption")
    mind_changes_count = sum(len(d.changed_decisions) for d in round7.values())
    unresolved_count = len(round10.by_status("unresolved"))
    accepted_count = len(round10.by_status("accepted"))
    rejected_count = len(round10.by_status("rejected"))
    premortem_categories_covered = sorted({f.category for f in round8.values()})

    # Deterministic depth/coverage proxy: total structured analytical items
    # produced across all 10 rounds, and the average per round - a real,
    # computed count (never estimated) that naturally comes out higher for a
    # deeper debate, comparable across runs.
    total_structured_items_count = (
        sum(len(pu.assumptions) + len(pu.clarifying_questions) for pu in result.round1.values())
        + sum(len(p.requirements) + len(p.decisions) + len(p.edge_cases) + len(p.risks) for p in round2.values())
        + sum(
            len(r.agree) + len(r.disagree) + len(r.missing_requirements) + len(r.risks) + len(r.proposed_changes)
            for tmap in list(round3.values()) + list(round4.values())
            for r in tmap.values()
        )
        + len(round5.findings)
        + sum(len(a.trade_offs) + 1 for a in round6.values())  # +1 for the alternative_option itself
        + sum(len(d.responses) + len(d.changed_decisions) + len(d.final_decisions) for d in round7.values())
        + len(round8)
        + len(result.round9.unresolved_conflicts) + len(result.round9.decision_dependencies)
        + len(round10.items)
    )
    avg_items_per_round = round(total_structured_items_count / 10, 2)

    trajectory = [
        {"round": 1, "label": "problem_understanding", "assumptions_stated_count": assumptions_stated_count},
        {"round": 2, "label": "independent_proposals", "requirements_count": requirements_count, "edge_cases_count": edge_cases_count, "risks_count": risks_count},
        {"round": 3, "label": "cross_review_requirement_ux_business", "disagreements_count": sum(len(r.disagree) for tmap in round3.values() for r in tmap.values())},
        {"round": 4, "label": "cross_review_architecture_security_ops", "disagreements_count": sum(len(r.disagree) for tmap in round4.values() for r in tmap.values())},
        {"round": 5, "label": "devils_advocate", "findings_count": len(round5.findings), "categories_covered": sorted(round5.covered_categories())},
        {"round": 6, "label": "alternative_designs", "alternatives_count": alternatives_count},
        {"round": 7, "label": "defense_revision", "mind_changes_count": mind_changes_count},
        {"round": 8, "label": "premortem", "findings_count": len(round8), "categories_covered": premortem_categories_covered},
        {"round": 9, "label": "convergence", "unresolved_conflicts_count": len(result.round9.unresolved_conflicts), "ready_for_consensus": result.round9.ready_for_consensus},
        {"round": 10, "label": "consensus", "accepted_count": accepted_count, "rejected_count": rejected_count, "unresolved_count": unresolved_count},
    ]

    return {
        "mode": "council",
        "round_count": 10,
        "requirements_count": requirements_count,
        "edge_cases_count": edge_cases_count,
        "risks_count": risks_count,
        "unresolved_count": unresolved_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "mind_changes_count": mind_changes_count,
        "arguments_count": arguments_count,
        "disagreements_count": disagreements_count,
        "alternatives_count": alternatives_count,
        "assumptions_stated_count": assumptions_stated_count,
        "assumptions_challenged_count": assumptions_challenged_count,
        "premortem_findings_count": len(round8),
        "premortem_categories_covered": premortem_categories_covered,
        "devils_advocate_findings_count": len(round5.findings),
        "devils_advocate_categories_covered": sorted(round5.covered_categories()),
        "total_structured_items_count": total_structured_items_count,
        "avg_items_per_round": avg_items_per_round,
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
