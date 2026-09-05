"""Run artifact structure and non-overwriting run directory creation.

runs/<run_id>/
  meta.json
  brief.md
  agents/round1/<role>.json
  agents/round2/<reviewer>__reviews__<target>.json
  agents/round4/<role>.json
  debate/round3_devils_advocate.json
  consensus.json
  metrics.json
  final_report.md
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RUNS_DIR = Path("runs")


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "brief")[:max_len]


def make_run_dir(runs_dir: Path, brief_name: str, mode: str, run_id: str | None = None) -> Path:
    """Create a fresh run directory. Never overwrites an existing run:
    if the computed run_id already exists on disk, a numeric suffix is
    appended until a free directory name is found."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    if run_id is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_id = f"{ts}_{slugify(brief_name)}_{mode}"
    else:
        base_id = run_id

    candidate = base_id
    suffix = 2
    while (runs_dir / candidate).exists():
        candidate = f"{base_id}-{suffix}"
        suffix += 1

    run_dir = runs_dir / candidate
    (run_dir / "agents" / "round1").mkdir(parents=True)
    (run_dir / "agents" / "round2").mkdir(parents=True)
    (run_dir / "agents" / "round4").mkdir(parents=True)
    (run_dir / "debate").mkdir(parents=True)
    return run_dir


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def save_meta(run_dir: Path, *, run_id: str, mode: str, provider: str, brief_path: str) -> None:
    meta = {
        "run_id": run_dir.name,
        "mode": mode,
        "provider": provider,
        "brief_path": brief_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "meta.json", meta)


def save_brief(run_dir: Path, brief_text: str) -> None:
    write_text(run_dir / "brief.md", brief_text)


def save_council_artifacts(run_dir: Path, result) -> None:
    """result: council.pipeline.orchestrator.CouncilRunResult"""
    for role_id, proposal in result.round1.items():
        write_json(run_dir / "agents" / "round1" / f"{role_id}.json", proposal.model_dump())

    for reviewer_id, tmap in result.round2.items():
        for target_id, review in tmap.items():
            write_json(
                run_dir / "agents" / "round2" / f"{reviewer_id}__reviews__{target_id}.json",
                review.model_dump(),
            )

    write_json(run_dir / "debate" / "round3_devils_advocate.json", result.round3.model_dump())

    for role_id, defense in result.round4.items():
        write_json(run_dir / "agents" / "round4" / f"{role_id}.json", defense.model_dump())

    write_json(run_dir / "consensus.json", result.round5.model_dump())


def save_solo_artifacts(run_dir: Path, result) -> None:
    """result: council.pipeline.single_agent.SoloRunResult"""
    write_json(run_dir / "agents" / "round1" / "solo_designer.json", result.design.model_dump())


def save_metrics(run_dir: Path, metrics: dict[str, Any]) -> None:
    write_json(run_dir / "metrics.json", metrics)


def save_final_report(run_dir: Path, report_markdown: str) -> None:
    write_text(run_dir / "final_report.md", report_markdown)
