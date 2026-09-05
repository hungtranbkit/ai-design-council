"""A/B harness: runs the same brief through `single-agent` and `council` modes
and produces a comparison.json / comparison.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from council import artifacts, metrics as metrics_mod, report
from council.pipeline.orchestrator import CouncilOrchestrator, CouncilRunResult
from council.pipeline.single_agent import SoloRunResult, run_solo
from council.providers.base import Provider

# Probes for "what did debate surface that a solo pass missed" - deterministic,
# keyword-based, and only meaningful given the actual MockProvider script. A
# real-provider run may not match these probes exactly; they are a V0
# demonstration aid, not a scored benchmark.
_INSIGHT_PROBES: list[tuple[str, list[str]]] = [
    ("Signed/expiring QR token (vs a static, replayable QR)", ["signed", "hmac"]),
    ("Non-smartphone guest fallback flow", ["printed menu", "call-waiter", "call waiter", "non-smartphone"]),
    ("Offline-lite handling for flaky venue wifi", ["offline", "local queue", "idempotency key"]),
    ("Cost-gated realtime transport (SSE default, Redis only past a threshold)", ["sse", "concurrency trigger", "concurrency threshold"]),
    ("Equal-share split billing as an explicit option", ["equal-share", "equal share"]),
]


def _council_text_corpus(result: CouncilRunResult) -> str:
    parts: list[str] = []
    for defense in result.round4.values():
        parts.extend(defense.final_decisions)
    for item in result.round5.items:
        if item.decision:
            parts.append(item.decision)
    return " \n ".join(parts).lower()


def _solo_text_corpus(result: SoloRunResult) -> str:
    d = result.design
    return " \n ".join(d.requirements + d.decisions + d.edge_cases + d.risks).lower()


def _compute_council_only_insights(council_result: CouncilRunResult, solo_result: SoloRunResult) -> list[str]:
    council_text = _council_text_corpus(council_result)
    solo_text = _solo_text_corpus(solo_result)
    found: list[str] = []
    for label, keywords in _INSIGHT_PROBES:
        in_council = any(k in council_text for k in keywords)
        in_solo = any(k in solo_text for k in keywords)
        if in_council and not in_solo:
            found.append(label)
    return found


@dataclass
class ComparisonResult:
    council_run_dir: Path
    solo_run_dir: Path
    council_metrics: dict[str, Any]
    solo_metrics: dict[str, Any]
    council_only_insights: list[str]


def run_comparison(
    *, provider: Provider, brief_path: Path, runs_dir: Path, run_id_prefix: str | None = None
) -> ComparisonResult:
    brief_text = brief_path.read_text(encoding="utf-8")
    brief_name = brief_path.stem

    # --- council run ---
    council_run_dir = artifacts.make_run_dir(runs_dir, brief_name, "council", run_id=(
        f"{run_id_prefix}_council" if run_id_prefix else None
    ))
    artifacts.save_meta(council_run_dir, run_id=council_run_dir.name, mode="council", provider=provider.name, brief_path=str(brief_path))
    artifacts.save_brief(council_run_dir, brief_text)
    orchestrator = CouncilOrchestrator(provider=provider)
    council_result = orchestrator.run(brief_text)
    council_metrics = metrics_mod.compute_council_metrics(council_result)
    artifacts.save_council_artifacts(council_run_dir, council_result)
    artifacts.save_metrics(council_run_dir, council_metrics)
    artifacts.save_calls(council_run_dir, council_result.calls)
    council_report_md = report.render_council_report(
        run_id=council_run_dir.name, brief_text=brief_text, result=council_result, metrics=council_metrics
    )
    artifacts.save_final_report(council_run_dir, council_report_md)

    # --- solo run ---
    solo_run_dir = artifacts.make_run_dir(runs_dir, brief_name, "single-agent", run_id=(
        f"{run_id_prefix}_single-agent" if run_id_prefix else None
    ))
    artifacts.save_meta(solo_run_dir, run_id=solo_run_dir.name, mode="single-agent", provider=provider.name, brief_path=str(brief_path))
    artifacts.save_brief(solo_run_dir, brief_text)
    solo_result = run_solo(provider, brief_text)
    solo_metrics = metrics_mod.compute_solo_metrics(solo_result)
    artifacts.save_solo_artifacts(solo_run_dir, solo_result)
    artifacts.save_metrics(solo_run_dir, solo_metrics)
    artifacts.save_calls(solo_run_dir, solo_result.calls)
    solo_report_md = report.render_solo_report(
        run_id=solo_run_dir.name, brief_text=brief_text, result=solo_result, metrics=solo_metrics
    )
    artifacts.save_final_report(solo_run_dir, solo_report_md)

    council_only_insights = _compute_council_only_insights(council_result, solo_result)

    return ComparisonResult(
        council_run_dir=council_run_dir,
        solo_run_dir=solo_run_dir,
        council_metrics=council_metrics,
        solo_metrics=solo_metrics,
        council_only_insights=council_only_insights,
    )


def render_comparison_json(comp: ComparisonResult) -> dict[str, Any]:
    return {
        "council_run_id": comp.council_run_dir.name,
        "solo_run_id": comp.solo_run_dir.name,
        "council_metrics": comp.council_metrics,
        "solo_metrics": comp.solo_metrics,
        "council_only_insights": comp.council_only_insights,
        "deltas": {
            "requirements_count": comp.council_metrics["requirements_count"] - comp.solo_metrics["requirements_count"],
            "edge_cases_count": comp.council_metrics["edge_cases_count"] - comp.solo_metrics["edge_cases_count"],
            "risks_count": comp.council_metrics["risks_count"] - comp.solo_metrics["risks_count"],
            "mind_changes_count": comp.council_metrics["mind_changes_count"] - comp.solo_metrics["mind_changes_count"],
            "duration_seconds": round(comp.council_metrics["duration_seconds"] - comp.solo_metrics["duration_seconds"], 4),
        },
    }


def render_comparison_markdown(comp: ComparisonResult) -> str:
    lines: list[str] = []
    a = lines.append
    cm, sm = comp.council_metrics, comp.solo_metrics

    a("# A/B Comparison: council vs single-agent")
    a("")
    a(f"- Council run: `{comp.council_run_dir.name}`")
    a(f"- Solo run: `{comp.solo_run_dir.name}`")
    a("")
    a("| Metric | Council | Solo | Delta |")
    a("|---|---|---|---|")
    for key, display in [
        ("requirements_count", "Requirements"),
        ("edge_cases_count", "Edge cases"),
        ("risks_count", "Risks"),
        ("mind_changes_count", "Mind changes"),
        ("unresolved_count", "Unresolved (human decision needed)"),
        ("duration_seconds", "Duration (s)"),
        ("tokens_in", "Tokens in"),
        ("tokens_out", "Tokens out"),
    ]:
        cv, sv = cm.get(key), sm.get(key)
        delta = "-" if cv is None or sv is None else round(cv - sv, 4) if isinstance(cv, float) else cv - sv
        a(f"| {display} | {cv} | {sv} | {delta} |")
    a("")
    a("## What debate surfaced that the solo pass missed")
    a("")
    if comp.council_only_insights:
        for insight in comp.council_only_insights:
            a(f"- {insight}")
    else:
        a("_No probe-detected gaps this run - inspect both final_report.md files manually._")
    a("")
    a("## Read next")
    a("")
    a(f"- `runs/{comp.council_run_dir.name}/final_report.md` - full council report")
    a(f"- `runs/{comp.solo_run_dir.name}/final_report.md` - solo baseline report")
    return "\n".join(lines) + "\n"
