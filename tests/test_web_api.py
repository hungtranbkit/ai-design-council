"""Web API tests: meeting creation/status/transcript/summary/artifacts,
roles & skills config, human decisions, and non-destructive artifact reads.

Uses playback_enabled=False so every event is revealed immediately - the
gradual-reveal timing itself isn't asserted here (it's exercised manually,
see the PR notes), only that it defaults on and can be turned off.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from council.agents import role_overrides
from council.web import meeting_store as store
from council.web.app import app

BRIEF_PATH = Path(__file__).resolve().parent.parent / "examples" / "qr_restaurant.md"
BRIEF_TEXT = BRIEF_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DEFAULT_RUNS_DIR", tmp_path / "runs")
    return TestClient(app)


@pytest.fixture()
def created_meeting(client):
    resp = client.post(
        "/api/meetings",
        json={
            "brief_text": BRIEF_TEXT,
            "brief_name": "test",
            "provider": "mock",
            "role_skills": {"architect": ["architecture_review"]},
            "playback_enabled": False,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


def test_roles_and_skills_config_are_data_driven(client):
    catalog = client.get("/api/roles").json()
    roles = catalog["roles"]
    ids = {r["id"] for r in roles}
    # 6 debaters (Rounds 1-4) + the Moderator/ChatGPT Observer (Round 5) = 7.
    assert ids == {"product_ba", "ux_designer", "architect", "business_critic", "qa_security", "devils_advocate", "moderator"}
    architect = next(r for r in roles if r["id"] == "architect")
    assert "architecture_review" in architect["skills"]
    assert architect["role_type"] == "debater"
    assert architect["status"] == "active"
    assert architect["runtime_provider"] == catalog["default_provider"]

    moderator = next(r for r in roles if r["id"] == "moderator")
    assert moderator["role_type"] == "moderator"
    assert "consensus_moderation" in moderator["skills"]

    skills = client.get("/api/skills").json()["skills"]
    skill_ids = {s["id"] for s in skills}
    assert {"product_discovery", "security_review", "devils_advocate_skill", "consensus_moderation"} <= skill_ids


def test_providers_status_marks_mock_ready(client):
    providers = client.get("/api/providers").json()["providers"]
    mock = next(p for p in providers if p["name"] == "mock")
    assert mock["status"] == "ready"


def test_role_skills_override_roundtrip(client, tmp_path, monkeypatch):
    monkeypatch.setattr(role_overrides, "OVERRIDES_PATH", tmp_path / "overrides.json")
    resp = client.patch("/api/roles/ux_designer/skills", json={"role_id": "ux_designer", "skill_ids": ["ux_flow", "product_discovery"]})
    assert resp.status_code == 200
    roles = client.get("/api/roles").json()["roles"]
    ux = next(r for r in roles if r["id"] == "ux_designer")
    assert set(ux["skills"]) == {"ux_flow", "product_discovery"}


def test_role_skills_override_rejects_unknown_skill(client, tmp_path, monkeypatch):
    monkeypatch.setattr(role_overrides, "OVERRIDES_PATH", tmp_path / "overrides.json")
    resp = client.patch("/api/roles/ux_designer/skills", json={"role_id": "ux_designer", "skill_ids": ["not_a_real_skill"]})
    assert resp.status_code == 400


def test_create_meeting_without_playback_is_immediately_complete(client, created_meeting):
    status = client.get(f"/api/meetings/{created_meeting}/status").json()
    assert status["is_meeting"] is True
    assert status["is_complete"] is True
    assert status["revealed_events"] == status["total_events"]
    assert status["total_events"] > 40  # ~49 in the current mock script
    assert status["current_round"] == 5


def test_meeting_appears_in_list(client, created_meeting):
    meetings = client.get("/api/meetings").json()["meetings"]
    assert any(m["run_id"] == created_meeting for m in meetings)


def test_transcript_filters(client, created_meeting):
    def events(filter_name):
        return client.get(f"/api/meetings/{created_meeting}/transcript?filter={filter_name}").json()["events"]

    all_events = events("all")
    proposals = events("proposal")
    agrees = events("agree")
    disagrees = events("disagree")
    risks = events("risk")
    mind_changes = events("mind_change")
    decisions = events("decision")
    unresolved = events("unresolved")

    assert len(proposals) == 6  # 1 independent proposal per debating role
    assert all(e["type"] == "proposal" for e in proposals)
    # "agree" matches the dominant type OR partial agreement inside an
    # otherwise-disagreeing review - CrossReview's schema forces every review
    # to disagree/miss-something/propose-a-change, so "agreement" alone is
    # never the dominant type in practice; see meeting_events.py's comment.
    assert len(agrees) > 0
    assert all(e["type"] == "agreement" or e.get("has_agreements") for e in agrees)
    assert all(e["type"] in ("disagreement", "critique", "proposed_change") for e in disagrees)
    assert len(mind_changes) >= 3  # matches the pipeline's own mind-change guarantee
    assert all(e["type"] == "mind_change" for e in mind_changes)
    assert len(decisions) == 7  # 7 ConsensusItem topics in the mock script
    assert all(e["type"] == "decision" for e in decisions)
    assert len(unresolved) == 2  # matches metrics.json unresolved_count for this brief
    assert all(e["type"] == "decision" and e["meta"]["status"] == "unresolved" for e in unresolved)
    assert len(risks) > 0
    assert all(e["type"] == "risk" or e.get("has_risks") for e in risks)
    assert len(all_events) > len(mind_changes) + len(decisions)
    assert len(all_events) > len(mind_changes)


def test_summary_payload_has_required_fields_for_external_readers(client, created_meeting):
    summary = client.get(f"/api/meetings/{created_meeting}/summary").json()
    for key in [
        "brief", "participants", "current_round", "accepted", "rejected", "unresolved",
        "major_arguments", "mind_changes", "risks", "recommendation", "last_events",
    ]:
        assert key in summary, f"missing key {key}"
    assert summary["is_complete"] is True
    assert len(summary["accepted"]) == 5
    assert len(summary["unresolved"]) == 2
    assert summary["human_decision_required"] is True


def test_artifacts_manifest_and_file_read(client, created_meeting):
    manifest = client.get(f"/api/meetings/{created_meeting}/artifacts").json()["files"]
    assert any(f["path"] == "consensus.json" for f in manifest)
    assert any(f["path"] == "final_report.md" for f in manifest)

    file_resp = client.get(f"/api/meetings/{created_meeting}/artifacts/file", params={"path": "consensus.json"})
    assert file_resp.status_code == 200
    assert "qr_signing" in file_resp.json()["content"]


def test_artifact_path_traversal_is_rejected(client, created_meeting):
    resp = client.get(f"/api/meetings/{created_meeting}/artifacts/file", params={"path": "../../etc/passwd"})
    assert resp.status_code == 400


def test_artifact_reading_is_non_destructive(client, created_meeting):
    """Reading artifacts through the API must never mutate the underlying files."""
    run_dir = store.DEFAULT_RUNS_DIR / created_meeting
    before = (run_dir / "consensus.json").read_bytes()
    metrics_before = (run_dir / "metrics.json").read_bytes()

    client.get(f"/api/meetings/{created_meeting}")
    client.get(f"/api/meetings/{created_meeting}/status")
    client.get(f"/api/meetings/{created_meeting}/transcript?filter=all")
    client.get(f"/api/meetings/{created_meeting}/summary")
    client.get(f"/api/meetings/{created_meeting}/artifacts")
    client.get(f"/api/meetings/{created_meeting}/artifacts/file", params={"path": "consensus.json"})

    assert (run_dir / "consensus.json").read_bytes() == before
    assert (run_dir / "metrics.json").read_bytes() == metrics_before


def test_human_decisions_default_scaffold_before_any_save(client, created_meeting):
    decisions = client.get(f"/api/meetings/{created_meeting}/decisions").json()
    assert decisions["updated_at"] is None
    assert decisions["decisions"]["guest_phone_number_capture"]["human_choice"] == "pending"
    assert decisions["decisions"]["qr_signing"]["human_choice"] == "approve"


def test_human_decisions_save_writes_artifacts(client, created_meeting):
    resp = client.post(
        f"/api/meetings/{created_meeting}/decisions",
        json={"decisions": [{"topic": "guest_phone_number_capture", "human_choice": "defer", "note": "ask legal"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decisions"]["guest_phone_number_capture"]["human_choice"] == "defer"
    assert body["decisions"]["guest_phone_number_capture"]["note"] == "ask legal"
    assert body["updated_at"] is not None

    run_dir = store.DEFAULT_RUNS_DIR / created_meeting
    human_decisions = json.loads((run_dir / "human_decisions.json").read_text())
    assert human_decisions["decisions"]["guest_phone_number_capture"]["human_choice"] == "defer"

    final_summary = json.loads((run_dir / "final_summary_for_chatgpt.json").read_text())
    assert "monetization_checkpoint" in final_summary["still_pending_topics"]
    assert "guest_phone_number_capture" not in final_summary["still_pending_topics"]


def test_provider_error_returns_400_not_500(client):
    resp = client.post(
        "/api/meetings",
        json={"brief_text": "x", "brief_name": "t", "provider": "anthropic", "role_skills": {}, "playback_enabled": False},
    )
    assert resp.status_code == 400


def test_unknown_meeting_returns_404(client):
    for path in ["", "/status", "/transcript", "/summary", "/artifacts", "/decisions"]:
        resp = client.get(f"/api/meetings/does-not-exist{path}")
        assert resp.status_code == 404, path


def test_single_agent_run_is_listed_but_not_a_meeting(client, monkeypatch, tmp_path):
    """council run --mode single-agent output must still show up in /api/meetings
    (as a run, not a "meeting" with rounds), proving the web layer reuses the
    CLI's artifact structure rather than requiring web-specific runs."""
    from council import artifacts, metrics as metrics_mod, report as report_mod
    from council.pipeline.single_agent import run_solo
    from council.providers.mock import MockProvider

    runs_dir = store.DEFAULT_RUNS_DIR
    run_dir = artifacts.make_run_dir(runs_dir, "cli-brief", "single-agent", run_id="cli-made-run")
    artifacts.save_meta(run_dir, run_id=run_dir.name, mode="single-agent", provider="mock", brief_path="x.md")
    artifacts.save_brief(run_dir, BRIEF_TEXT)
    result = run_solo(MockProvider(), BRIEF_TEXT)
    metrics = metrics_mod.compute_solo_metrics(result)
    artifacts.save_solo_artifacts(run_dir, result)
    artifacts.save_metrics(run_dir, metrics)

    meetings = client.get("/api/meetings").json()["meetings"]
    row = next(m for m in meetings if m["run_id"] == "cli-made-run")
    assert row["is_meeting"] is False
    assert row["status"] == "completed"


def test_model_override_is_ignored_for_mock_but_forwarded_to_real_providers(client, monkeypatch):
    """MockProvider() takes no constructor args - passing a model override with
    provider="mock" must not blow up. A real provider should receive it."""
    from council.providers.mock import MockProvider

    captured = {}
    real_get_provider = store.get_provider

    def spy_get_provider(name, **kwargs):
        captured[name] = kwargs
        if name == "mock":
            return MockProvider()
        return real_get_provider(name, **kwargs)

    monkeypatch.setattr(store, "get_provider", spy_get_provider)

    # provider=mock + a model override: must be silently dropped, not passed to MockProvider().
    run_id = store.create_meeting(
        runs_dir=store.DEFAULT_RUNS_DIR,
        brief_text=BRIEF_TEXT,
        brief_name="t",
        provider_name="mock",
        model="some-model-mock-does-not-take",
        role_skills={},
        playback_enabled=False,
    )
    assert captured["mock"] == {}
    meta = json.loads((store.DEFAULT_RUNS_DIR / run_id / "meta.json").read_text())
    assert meta["model"] is None  # MockProvider has no .model attribute

    # provider=anthropic + a model override: must be forwarded through to the constructor.
    captured.clear()
    with pytest.raises(Exception):  # no real ANTHROPIC_API_KEY in the test env - expected to fail here
        store.create_meeting(
            runs_dir=store.DEFAULT_RUNS_DIR,
            brief_text=BRIEF_TEXT,
            brief_name="t",
            provider_name="anthropic",
            model="claude-sonnet-5",
            role_skills={},
            playback_enabled=False,
        )
    assert captured["anthropic"] == {"model": "claude-sonnet-5"}
