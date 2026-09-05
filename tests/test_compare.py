"""A/B harness tests: council must demonstrably out-perform the solo baseline
on the mock-provider demo brief, and comparison artifacts must be well-formed."""
from __future__ import annotations

from pathlib import Path

from council import compare as compare_mod
from council.providers.mock import MockProvider

BRIEF_PATH = Path(__file__).resolve().parent.parent / "examples" / "qr_restaurant.md"


def test_compare_runs_both_modes_and_writes_two_run_dirs(tmp_path: Path):
    comp = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path)
    assert comp.council_run_dir.exists()
    assert comp.solo_run_dir.exists()
    assert (comp.council_run_dir / "final_report.md").exists()
    assert (comp.solo_run_dir / "final_report.md").exists()
    assert (comp.council_run_dir / "consensus.json").exists()
    assert (comp.council_run_dir / "metrics.json").exists()
    assert (comp.solo_run_dir / "metrics.json").exists()


def test_council_finds_more_than_solo(tmp_path: Path):
    comp = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path)
    assert comp.council_metrics["requirements_count"] > comp.solo_metrics["requirements_count"]
    assert comp.council_metrics["risks_count"] > comp.solo_metrics["risks_count"]
    assert comp.council_metrics["mind_changes_count"] > comp.solo_metrics["mind_changes_count"] == 0


def test_council_only_insights_are_detected(tmp_path: Path):
    comp = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path)
    assert len(comp.council_only_insights) >= 2, comp.council_only_insights


def test_comparison_json_and_markdown_render(tmp_path: Path):
    comp = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path)
    data = compare_mod.render_comparison_json(comp)
    assert data["council_run_id"] == comp.council_run_dir.name
    assert data["solo_run_id"] == comp.solo_run_dir.name
    assert data["deltas"]["requirements_count"] > 0

    md = compare_mod.render_comparison_markdown(comp)
    assert "council vs single-agent" in md.lower()
    assert comp.council_run_dir.name in md


def test_two_comparisons_do_not_collide_on_disk(tmp_path: Path):
    comp1 = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path, run_id_prefix="demo")
    comp2 = compare_mod.run_comparison(provider=MockProvider(), brief_path=BRIEF_PATH, runs_dir=tmp_path, run_id_prefix="demo")
    assert comp1.council_run_dir != comp2.council_run_dir
    assert comp1.solo_run_dir != comp2.solo_run_dir
