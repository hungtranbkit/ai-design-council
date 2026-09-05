"""Smoke tests for the server-rendered HTML pages - catches Jinja/template
errors that only surface at request time, not at import time."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from council.web import meeting_store as store
from council.web.app import app

BRIEF_PATH = Path(__file__).resolve().parent.parent / "examples" / "qr_restaurant.md"
BRIEF_TEXT = BRIEF_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DEFAULT_RUNS_DIR", tmp_path / "runs")
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/sessions/new", "/roles", "/reports", "/settings"])
def test_static_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "<html" in resp.text.lower()


def test_meeting_room_and_decisions_pages_render_for_a_real_meeting(client):
    created = client.post(
        "/api/meetings",
        json={"brief_text": BRIEF_TEXT, "brief_name": "t", "provider": "mock", "role_skills": {}, "playback_enabled": False},
    ).json()
    run_id = created["run_id"]

    room = client.get(f"/meetings/{run_id}")
    assert room.status_code == 200
    assert "Meeting Room" in room.text
    assert "seat-1" in room.text  # 6 seats rendered

    decisions = client.get(f"/meetings/{run_id}/decisions")
    assert decisions.status_code == 200
    assert "Human Decision Center" in decisions.text
    assert "qr_signing" in decisions.text.replace("_", "_")  # topic rendered somewhere


def test_unknown_meeting_room_returns_404_page(client):
    resp = client.get("/meetings/does-not-exist")
    assert resp.status_code == 404


def test_role_catalog_page_shows_all_8_roles_with_runtime_and_status(client):
    resp = client.get("/roles")
    assert resp.status_code == 200
    text = resp.text
    for expected in [
        "Product / Business Analyst", "UX Designer", "Architect", "Business Critic",
        "QA + Security", "Devil&#39;s Advocate", "Moderator", "ChatGPT Observer",
    ]:
        assert expected in text
    assert "Runtime:" in text
    assert "Debater · Rounds 1-4" in text
    assert "Moderator · Round 5" in text
    assert "Observer · Read-only" in text
    assert "Runtime: deterministic" in text  # the Observer doesn't call an LLM in V0


def test_new_session_page_shows_moderator_and_model_field_and_no_ollama_chip(client):
    resp = client.get("/sessions/new")
    assert resp.status_code == 200
    text = resp.text
    assert "Moderator" in text
    assert 'id="model_override"' in text
    assert 'data-provider="mock"' in text
    assert 'data-provider="anthropic"' in text
    assert 'data-provider="ollama"' not in text  # scope decision: hidden from the primary picker this phase
