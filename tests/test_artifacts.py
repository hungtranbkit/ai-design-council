"""Artifact structure and non-overwrite guarantees."""
from __future__ import annotations

from pathlib import Path

from council import artifacts


def test_make_run_dir_creates_expected_structure(tmp_path: Path):
    run_dir = artifacts.make_run_dir(tmp_path, "qr_restaurant", "council", run_id="fixed-id")
    assert run_dir == tmp_path / "fixed-id"
    assert (run_dir / "agents" / "round1").is_dir()
    assert (run_dir / "agents" / "round2").is_dir()
    assert (run_dir / "agents" / "round4").is_dir()
    assert (run_dir / "debate").is_dir()


def test_make_run_dir_never_overwrites_an_existing_run(tmp_path: Path):
    run_dir_1 = artifacts.make_run_dir(tmp_path, "qr_restaurant", "council", run_id="same-id")
    marker = run_dir_1 / "agents" / "round1" / "sentinel.json"
    artifacts.write_json(marker, {"do_not_delete": True})

    run_dir_2 = artifacts.make_run_dir(tmp_path, "qr_restaurant", "council", run_id="same-id")

    assert run_dir_2 != run_dir_1
    assert run_dir_2.name == "same-id-2"
    # original run's file must still exist untouched
    assert marker.exists()
    import json

    assert json.loads(marker.read_text()) == {"do_not_delete": True}


def test_make_run_dir_third_collision_increments_further(tmp_path: Path):
    artifacts.make_run_dir(tmp_path, "brief", "council", run_id="dup")
    artifacts.make_run_dir(tmp_path, "brief", "council", run_id="dup")
    third = artifacts.make_run_dir(tmp_path, "brief", "council", run_id="dup")
    assert third.name == "dup-3"


def test_auto_generated_run_id_includes_timestamp_and_mode(tmp_path: Path):
    run_dir = artifacts.make_run_dir(tmp_path, "My Brief!!", "single-agent")
    assert "single-agent" in run_dir.name
    assert "my-brief" in run_dir.name
