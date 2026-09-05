"""Renders final_report.md - the human/ChatGPT-readable deliverable of a run.

Per the V0 spec this must be easy to read end-to-end and must make clear that
the human is the final decision-maker, not the council.
"""
from __future__ import annotations

from typing import Any

from council.agents.display import display_name as _name
from council.pipeline.orchestrator import CouncilRunResult
from council.pipeline.single_agent import SoloRunResult


def render_council_report(
    *, run_id: str, brief_text: str, result: CouncilRunResult, metrics: dict[str, Any]
) -> str:
    lines: list[str] = []
    a = lines.append

    a(f"# AI Design Council - Final Report ({run_id})")
    a("")
    a("> **You are the final decision-maker.** This report is a structured input to your")
    a("> decision, not a decision itself. Every 'accepted' item below is the council's")
    a("> recommendation, not a mandate - accept, override, or send back for another round.")
    a("")

    # --- Executive summary ---------------------------------------------
    a("## Executive Summary")
    a("")
    a(
        f"Six AI agents (Product/BA, UX Designer, Architect, Business Critic, QA+Security, "
        f"Devil's Advocate) independently designed a solution to the brief below, then "
        f"cross-reviewed each other, underwent a mandatory Devil's Advocate critique, "
        f"defended or revised their positions, and had a neutral moderator synthesize the "
        f"result - **not** by majority vote."
    )
    a("")
    a(
        f"- **{metrics['requirements_count']}** unique requirements surfaced across all proposals\n"
        f"- **{metrics['edge_cases_count']}** edge cases identified\n"
        f"- **{metrics['risks_count']}** distinct risks raised\n"
        f"- **{metrics['mind_changes_count']}** recorded mind changes (agents revising a prior decision under critique)\n"
        f"- **{metrics['accepted_count']}** decisions accepted, **{metrics['rejected_count']}** rejected, "
        f"**{metrics['unresolved_count']}** left unresolved for you to decide\n"
        f"- Devil's Advocate raised **{metrics['devils_advocate_findings_count']}** findings across categories: "
        f"{', '.join(metrics['devils_advocate_categories_covered'])}"
    )
    a("")
    a(f"Overall: {result.round5.summary}")
    a("")

    # --- Accepted decisions ---------------------------------------------
    accepted = result.round5.by_status("accepted")
    a("## Accepted Decisions")
    a("")
    if not accepted:
        a("_None accepted this run._")
        a("")
    for item in accepted:
        a(f"### {item.topic}")
        a(f"**Decision:** {item.decision}")
        a("")
        a(f"**Why:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    # --- Rejected decisions ----------------------------------------------
    rejected = result.round5.by_status("rejected")
    a("## Rejected Decisions")
    a("")
    if not rejected:
        a("_None rejected this run._")
        a("")
    for item in rejected:
        a(f"### {item.topic}")
        a(f"**Why rejected:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    # --- Unresolved: human choice required --------------------------------
    unresolved = result.round5.by_status("unresolved")
    a("## Unresolved - Requires Your Decision")
    a("")
    if not unresolved:
        a("_Nothing unresolved this run._")
        a("")
    for item in unresolved:
        a(f"### {item.topic}")
        a(f"**Why the council could not resolve this:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence / positions:**")
            for e in item.evidence:
                a(f"- {e}")
            a("")
        if item.dissent:
            a(f"**Dissent:** {item.dissent}")
        a("")

    # --- Major arguments (from cross-review + devil's advocate) -----------
    a("## Major Arguments During Debate")
    a("")
    for reviewer_id, tmap in result.round2.items():
        for target_id, review in tmap.items():
            if review.disagree:
                a(f"- **{_name(reviewer_id)} vs {_name(target_id)}:** {'; '.join(review.disagree)}")
    a("")
    a("### Devil's Advocate findings (Round 3)")
    for f in result.round3.findings:
        target = f" -> targeting {_name(f.target_role)}" if f.target_role else ""
        a(f"- **[{f.category}, {f.severity}]**{target}: {f.description}")
    a("")

    # --- Mind changes -------------------------------------------------
    a("## Mind Changes (Round 4)")
    a("")
    any_change = False
    for role_id, defense in result.round4.items():
        for cd in defense.changed_decisions:
            any_change = True
            a(f"### {_name(role_id)} changed position on: {cd.topic}")
            a(f"- **Before:** {cd.old_decision}")
            a(f"- **After:** {cd.new_decision}")
            a(f"- **Reason:** {cd.reason}")
            a(f"- **Triggered by:** {cd.triggered_by}")
            a("")
    if not any_change:
        a("_No agent changed a decision this run - treat that as a signal to scrutinize the debate quality._")
        a("")

    # --- Risks ----------------------------------------------------------
    a("## All Risks Raised")
    a("")
    seen_risks: set[str] = set()
    for p in result.round1.values():
        for r in p.risks:
            key = r.strip().lower()
            if key not in seen_risks:
                seen_risks.add(key)
                a(f"- {r}")
    a("")

    # --- Recommendation ---------------------------------------------------
    a("## Recommendation")
    a("")
    a(
        "Proceed with the accepted decisions above as the V1 design baseline. Before "
        "committing engineering time, make an explicit call on each unresolved item "
        "listed above - they are business/policy questions the council correctly "
        "identified it cannot resolve on its own authority."
    )
    a("")
    a("---")
    a(f"*Metrics: {metrics['duration_seconds']}s wall time, {metrics['call_count']} agent calls "
      f"(mode={metrics.get('mode', 'council')}). See metrics.json for full detail.*")

    return "\n".join(lines) + "\n"


def render_solo_report(*, run_id: str, brief_text: str, result: SoloRunResult, metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    d = result.design

    a(f"# Solo Designer Report ({run_id})")
    a("")
    a("> Single-agent baseline, no cross-review or debate. Generated for A/B comparison")
    a("> against the council pipeline - see the comparison report to evaluate what")
    a("> multi-agent debate added. **You are the final decision-maker.**")
    a("")
    a("## Summary")
    a("")
    a(d.summary)
    a("")
    a("## Requirements")
    for r in d.requirements:
        a(f"- {r}")
    a("")
    a("## Decisions")
    for dec in d.decisions:
        a(f"- {dec}")
    a("")
    a("## Edge Cases")
    for e in d.edge_cases:
        a(f"- {e}")
    a("")
    a("## Risks")
    for r in d.risks:
        a(f"- {r}")
    a("")
    a("## Open Questions")
    for q in d.open_questions:
        a(f"- {q}")
    a("")
    a("---")
    a(f"*Metrics: {metrics['duration_seconds']}s wall time, {metrics['call_count']} agent call. See metrics.json.*")
    return "\n".join(lines) + "\n"
