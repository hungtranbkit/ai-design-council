"""Read-mostly JSON API. Everything under /api/meetings/* is safe for an
external reader (e.g. ChatGPT fetching /summary) - it never lets the caller
make a decision on the user's behalf; POST /decisions only records what a
human typed into the Human Decision Center.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from council.agents import role_overrides
from council.agents.skills import load_skills
from council.providers.base import ProviderError
from council.web import meeting_store as store
from council.web.provider_status import provider_statuses
from council.web.role_catalog import build_role_catalog
from council.web.schemas import DecisionsRequest, NewMeetingRequest, RoleSkillsUpdate

router = APIRouter(prefix="/api")


@router.get("/roles")
def api_roles():
    return build_role_catalog()


@router.get("/skills")
def api_skills():
    return {"skills": [s.__dict__ for s in load_skills()]}


@router.patch("/roles/{role_id}/skills")
def api_update_role_skills(role_id: str, body: RoleSkillsUpdate):
    valid_ids = {s.id for s in load_skills()}
    unknown = [s for s in body.skill_ids if s not in valid_ids]
    if unknown:
        raise HTTPException(400, f"unknown skill id(s): {unknown}")
    role_overrides.set_role_skills(role_id, body.skill_ids)
    return {"role_id": role_id, "skills": body.skill_ids}


@router.get("/providers")
def api_providers():
    return {"providers": provider_statuses()}


@router.get("/meetings")
def api_list_meetings():
    return {"meetings": store.list_meetings(store.DEFAULT_RUNS_DIR)}


@router.post("/meetings", status_code=201)
def api_create_meeting(body: NewMeetingRequest):
    try:
        run_id = store.create_meeting(
            runs_dir=store.DEFAULT_RUNS_DIR,
            brief_text=body.brief_text,
            brief_name=body.brief_name,
            provider_name=body.provider,
            model=body.model,
            role_skills=body.role_skills,
            playback_enabled=body.playback_enabled,
        )
    except ProviderError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"run_id": run_id}


@router.get("/meetings/{run_id}")
def api_get_meeting(run_id: str):
    try:
        return store.get_meeting(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/status")
def api_meeting_status(run_id: str):
    try:
        return store.get_status(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/transcript")
def api_meeting_transcript(run_id: str, filter: str = Query("all"), since: int | None = Query(None)):
    try:
        return store.get_transcript(store.DEFAULT_RUNS_DIR, run_id, filter_name=filter, since=since)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/summary")
def api_meeting_summary(run_id: str):
    try:
        return store.get_summary(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/participants")
def api_meeting_participants(run_id: str):
    try:
        return store.get_participants(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/events")
def api_meeting_events(
    run_id: str,
    round: int | None = Query(None),
    type: str | None = Query(None),
    since: int | None = Query(None),
):
    try:
        return store.get_events(store.DEFAULT_RUNS_DIR, run_id, round_num=round, event_type=type, since=since)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/metrics")
def api_meeting_metrics(run_id: str):
    try:
        return store.get_metrics(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/artifacts")
def api_meeting_artifacts(run_id: str):
    try:
        return {"run_id": run_id, "files": store.list_artifacts(store.DEFAULT_RUNS_DIR, run_id)}
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.get("/meetings/{run_id}/artifacts/file")
def api_meeting_artifact_file(run_id: str, path: str = Query(...)):
    try:
        content = store.read_artifact(store.DEFAULT_RUNS_DIR, run_id, path)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc
    except store.InvalidArtifactPath as exc:
        raise HTTPException(400, f"invalid artifact path: {exc}") from exc
    return {"run_id": run_id, "path": path, "content": content}


@router.get("/meetings/{run_id}/decisions")
def api_get_decisions(run_id: str):
    try:
        return store.get_human_decisions(store.DEFAULT_RUNS_DIR, run_id)
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc


@router.post("/meetings/{run_id}/decisions")
def api_save_decisions(run_id: str, body: DecisionsRequest):
    try:
        return store.save_human_decisions(store.DEFAULT_RUNS_DIR, run_id, [d.model_dump() for d in body.decisions])
    except store.MeetingNotFound as exc:
        raise HTTPException(404, f"no meeting '{run_id}'") from exc
