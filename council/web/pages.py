"""Server-rendered page routes (Jinja2). All the actual state comes from
council.web.meeting_store, so a page reload always reflects the real
artifact files on disk - there is no separate "UI state" to fall out of sync.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from council.agents.loader import load_council_roles
from council.agents.skills import load_skills, skills_by_category
from council.web import meeting_store as store
from council.web.provider_status import provider_statuses
from council.web.role_catalog import build_role_catalog

TEMPLATES_DIR = Path(__file__).parent / "templates"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

EXAMPLE_BRIEF_PATH = REPO_ROOT / "examples" / "qr_restaurant.md"


def _version() -> str:
    try:
        return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.1.0"


@router.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request):
    meetings = store.list_meetings(store.DEFAULT_RUNS_DIR)
    return templates.TemplateResponse(
        request, "dashboard.html", {"active_nav": "meetings", "meetings": meetings}
    )


@router.get("/sessions/new", response_class=HTMLResponse)
def page_new_session(request: Request):
    catalog = build_role_catalog()
    example_brief = ""
    if EXAMPLE_BRIEF_PATH.exists():
        example_brief = EXAMPLE_BRIEF_PATH.read_text(encoding="utf-8")
    # Ollama is intentionally left out of the primary picker for now (scope
    # decision: mock + Anthropic + OpenAI only this phase) - the code and API
    # entry aren't removed, just not surfaced as a pickable chip here.
    providers = [p for p in provider_statuses() if p["name"] != "ollama"]
    return templates.TemplateResponse(
        request,
        "new_session.html",
        {
            "active_nav": "meetings",
            "debater_roles": [r for r in catalog["roles"] if r["role_type"] == "debater"],
            "moderator_role": next(r for r in catalog["roles"] if r["role_type"] == "moderator"),
            "all_skills": load_skills(),
            "providers": providers,
            "example_brief": example_brief,
        },
    )


@router.get("/meetings/{run_id}", response_class=HTMLResponse)
def page_meeting_room(request: Request, run_id: str):
    try:
        meeting = store.get_meeting(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound:
        return templates.TemplateResponse(request, "not_found.html", {"active_nav": "meetings", "run_id": run_id}, status_code=404)

    roles = [{"id": r.id, "display_name": r.display_name} for r in load_council_roles()]
    return templates.TemplateResponse(
        request,
        "meeting_room.html",
        {"active_nav": "meetings", "run_id": run_id, "meeting": meeting, "seat_roles": roles},
    )


@router.get("/meetings/{run_id}/decisions", response_class=HTMLResponse)
def page_decisions(request: Request, run_id: str):
    try:
        meeting = store.get_meeting(store.DEFAULT_RUNS_DIR, run_id)
        human = store.get_human_decisions(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound:
        return templates.TemplateResponse(request, "not_found.html", {"active_nav": "meetings", "run_id": run_id}, status_code=404)

    consensus = meeting.get("consensus") or {"items": []}
    items = []
    for item in consensus.get("items", []):
        decision_state = human["decisions"].get(item["topic"], {"human_choice": "pending", "note": ""})
        items.append({**item, "human_choice": decision_state.get("human_choice", "pending"), "note": decision_state.get("note", "")})

    return templates.TemplateResponse(
        request,
        "decisions.html",
        {"active_nav": "meetings", "run_id": run_id, "meeting": meeting, "items": items},
    )


@router.get("/roles", response_class=HTMLResponse)
def page_roles(request: Request):
    catalog = build_role_catalog()
    return templates.TemplateResponse(
        request,
        "roles.html",
        {
            "active_nav": "roles",
            "roles": catalog["roles"],
            "runtime_note": catalog["runtime_note"],
            "all_skills": load_skills(),
        },
    )


@router.get("/skills", response_class=HTMLResponse)
def page_skills(request: Request):
    return templates.TemplateResponse(
        request,
        "skills.html",
        {"active_nav": "skills", "skills_by_category": skills_by_category()},
    )


@router.get("/reports", response_class=HTMLResponse)
def page_reports(request: Request):
    meetings = [m for m in store.list_meetings(store.DEFAULT_RUNS_DIR) if m["status"] == "completed"]
    comparisons = store.list_comparisons(store.DEFAULT_RUNS_DIR)
    return templates.TemplateResponse(
        request, "reports.html", {"active_nav": "reports", "meetings": meetings, "comparisons": comparisons}
    )


@router.get("/settings", response_class=HTMLResponse)
def page_settings(request: Request):
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"active_nav": "settings", "providers": provider_statuses(), "version": _version(), "runs_dir": str(store.DEFAULT_RUNS_DIR.resolve())},
    )
