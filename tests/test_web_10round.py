"""Web-layer tests for the 10-round pipeline: status/summary/transcript
reflect 10 rounds and Vietnamese round labels, the observer-facing summary
carries total_rounds + mind changes + unresolved items, and the Meeting Room
page renders with the dynamic round-steps container (populated client-side
by app.js's renderRoundSteps(), driven by status.total_rounds/round_labels).

Uses the same created_meeting_10round fixture pattern as test_web_api.py
(the POS-retail VN brief is the only one MockProvider has a full 10-round
scenario for)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from council.web import meeting_store as store
from council.web.app import app

BRIEF_PATH = Path(__file__).resolve().parent.parent / "examples" / "pos_retail_vn.md"
BRIEF_TEXT = BRIEF_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DEFAULT_RUNS_DIR", tmp_path / "runs")
    return TestClient(app)


@pytest.fixture()
def meeting10(client):
    resp = client.post(
        "/api/meetings",
        json={
            "brief_text": BRIEF_TEXT,
            "brief_name": "pos10",
            "provider": "mock",
            "role_skills": {},
            "playback_enabled": False,
            # rounds omitted deliberately: 10 is the new default (requirement #7)
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


def test_status_reports_10_total_rounds_with_vietnamese_labels(client, meeting10):
    status = client.get(f"/api/meetings/{meeting10}/status").json()
    assert status["total_rounds"] == 10
    assert status["is_complete"] is True
    labels = status["round_labels"]
    assert len(labels) == 10
    assert labels["10"] == "Đồng thuận cuối (Moderator)"
    assert labels["5"] == "Devil's Advocate"
    assert status["current_round"] == 10


def test_dashboard_list_shows_10_as_total_rounds_for_this_meeting(client, meeting10):
    resp = client.get("/")
    assert resp.status_code == 200
    assert f"/{10}" in resp.text or "10</strong>" in resp.text


def test_summary_reports_total_rounds_10_and_vietnamese_recommendation(client, meeting10):
    summary = client.get(f"/api/meetings/{meeting10}/summary").json()
    assert summary["total_rounds"] == 10
    assert "đồng thuận" in summary["recommendation"].lower() or "quyết định" in summary["recommendation"].lower()


def test_summary_surfaces_mind_changes_and_unresolved_items(client, meeting10):
    summary = client.get(f"/api/meetings/{meeting10}/summary").json()
    assert len(summary["mind_changes"]) >= 3
    for mc in summary["mind_changes"]:
        assert mc["reason"].strip() != ""
    assert len(summary["unresolved"]) >= 1


def test_transcript_contains_all_10_round_event_types(client, meeting10):
    transcript = client.get(f"/api/meetings/{meeting10}/transcript").json()
    types = {e["type"] for e in transcript["events"]}
    expected_subset = {
        "problem_understanding", "proposal", "critique", "disagreement",
        "alternative", "defense", "mind_change", "premortem", "convergence", "decision",
    }
    assert expected_subset.issubset(types), f"missing types: {expected_subset - types}"
    rounds_present = {e["round"] for e in transcript["events"]}
    assert rounds_present == set(range(1, 11))


def test_meeting_room_page_has_dynamic_round_steps_container(client, meeting10):
    room = client.get(f"/meetings/{meeting10}")
    assert room.status_code == 200
    assert 'id="round-steps"' in room.text
    # must NOT hardcode 5 round-step divs anymore - they're built client-side
    # from status.total_rounds/round_labels (see app.js renderRoundSteps)
    assert room.text.count('class="round-step"') == 0


def test_metrics_json_has_10round_specific_fields(client, meeting10):
    meeting = client.get(f"/api/meetings/{meeting10}").json()
    metrics = meeting["metrics"]
    assert metrics["round_count"] == 10
    for key in [
        "arguments_count", "disagreements_count", "alternatives_count",
        "assumptions_challenged_count", "mind_changes_count", "unresolved_count",
        "total_structured_items_count",
    ]:
        assert key in metrics, f"missing metric {key}"
        assert metrics[key] is not None
