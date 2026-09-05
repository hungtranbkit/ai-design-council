"""Everything the web layer needs to read/write meeting state, all on top of
the existing artifact structure - no pipeline business logic is duplicated
here, only reading/formatting what council/pipeline + council/artifacts.py
already produce, plus a handful of new, additive artifact files:

    events.json               - flattened transcript (council/web/meeting_events.py)
    playback_state.json       - stateless "gradual reveal" schedule (see below)
    session_config.json       - the role/skill selection the session was started with
    human_decisions.json      - the user's Human Decision Center choices
    final_summary_for_chatgpt.json - regenerated whenever decisions are saved

None of this touches or is touched by `council run`/`compare`/`report` - a
run directory produced by the CLI is a valid meeting (just without
session_config.json / a gradual-reveal schedule; it displays as instantly
complete).
"""
from __future__ import annotations

import bisect
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from council import artifacts, metrics as metrics_mod, report as report_mod
from council.pipeline.orchestrator import CouncilOrchestrator
from council.pipeline.orchestrator_extended import ExtendedCouncilOrchestrator
from council.providers import get_provider
from council.providers.base import ProviderError
from council.web import meeting_events

DEFAULT_RUNS_DIR = Path("runs")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_BRIEF_PATH = REPO_ROOT / "examples" / "qr_restaurant.md"
EXTENDED_EXAMPLE_BRIEF_PATH = REPO_ROOT / "examples" / "pos_retail_vn.md"


class MeetingNotFound(Exception):
    pass


class InvalidArtifactPath(Exception):
    pass


# --------------------------------------------------------------------------
# creation
# --------------------------------------------------------------------------


def create_demo_meeting(runs_dir: Path) -> str:
    """One-click 'Run Demo Meeting' (legacy, English, 5-round): the example
    QR-restaurant brief, mock provider, all 6 default roles, gradual
    playback - unchanged behavior, kept exactly as it was before the
    10-round pipeline existed. See create_demo_meeting_extended for the new
    default (10-round, Vietnamese) demo."""
    brief_text = EXAMPLE_BRIEF_PATH.read_text(encoding="utf-8")
    return create_meeting(
        runs_dir=runs_dir,
        brief_text=brief_text,
        brief_name="demo",
        provider_name="mock",
        role_skills={},
        playback_enabled=True,
        rounds=5,
        language=None,
    )


def create_demo_meeting_extended(runs_dir: Path) -> str:
    """One-click 10-round Vietnamese demo: examples/pos_retail_vn.md (phần
    mềm quản lý bán hàng cho tiểu thương Việt Nam), mock provider - this is
    the only brief MockProvider has a full 10-round scenario for in V0."""
    brief_text = EXTENDED_EXAMPLE_BRIEF_PATH.read_text(encoding="utf-8")
    return create_meeting(
        runs_dir=runs_dir,
        brief_text=brief_text,
        brief_name="demo-pos-retail",
        provider_name="mock",
        role_skills={},
        playback_enabled=True,
        rounds=10,
        language="vi",
    )


def create_meeting(
    *,
    runs_dir: Path,
    brief_text: str,
    brief_name: str,
    provider_name: str,
    role_skills: dict[str, list[str]] | None,
    model: str | None = None,
    language: str | None = "vi",
    rounds: int = 10,
    playback_enabled: bool = True,
) -> str:
    # MockProvider() takes no constructor args - only forward an explicit
    # model override to a real provider.
    provider_kwargs = {"model": model} if model and provider_name != "mock" else {}
    provider = get_provider(provider_name, **provider_kwargs)  # raises ProviderError if misconfigured

    if not provider.supports_rounds(brief_text, rounds):
        raise ProviderError(
            f"Provider '{provider.name}' không có kịch bản {rounds} vòng cho brief này. "
            "MockProvider ở V0 chỉ mô phỏng đủ 10 vòng cho đề bài mẫu POS tiểu thương "
            "(examples/pos_retail_vn.md) - với brief tùy ý, hãy chọn 5 vòng, hoặc dùng provider "
            "Anthropic/OpenAI thật để chạy 10 vòng với nội dung sinh trực tiếp từ mô hình."
        )

    run_dir = artifacts.make_run_dir(runs_dir, brief_name, "council", extended=(rounds == 10))
    artifacts.save_meta(
        run_dir,
        run_id=run_dir.name,
        mode="council",
        provider=provider.name,
        brief_path="(web session)",
        model=getattr(provider, "model", None),
        round_count=rounds,
        language=language,
    )
    artifacts.save_brief(run_dir, brief_text)

    if rounds == 10:
        orchestrator10 = ExtendedCouncilOrchestrator(provider=provider, language=language)
        result10 = orchestrator10.run(brief_text)
        metrics = metrics_mod.compute_extended_council_metrics(result10)
        artifacts.save_extended_council_artifacts(run_dir, result10)
        artifacts.save_calls(run_dir, result10.calls)
        report_md = report_mod.render_extended_council_report(run_id=run_dir.name, brief_text=brief_text, result=result10, metrics=metrics)
    else:
        orchestrator5 = CouncilOrchestrator(provider=provider, language=language)
        result5 = orchestrator5.run(brief_text)
        metrics = metrics_mod.compute_council_metrics(result5)
        artifacts.save_council_artifacts(run_dir, result5)
        artifacts.save_calls(run_dir, result5.calls)
        report_md = report_mod.render_council_report(run_id=run_dir.name, brief_text=brief_text, result=result5, metrics=metrics)

    artifacts.save_metrics(run_dir, metrics)
    artifacts.save_final_report(run_dir, report_md)

    artifacts.write_json(
        run_dir / "session_config.json",
        {"role_skills": role_skills or {}, "language": language, "rounds": rounds, "started_at": datetime.now(timezone.utc).isoformat()},
    )

    events = meeting_events.build_events(run_dir)
    artifacts.write_json(run_dir / "events.json", events)
    _write_playback_state(run_dir, total_events=len(events), enabled=playback_enabled, seed=run_dir.name)

    return run_dir.name


def _write_playback_state(run_dir: Path, *, total_events: int, enabled: bool, seed: str) -> None:
    rng = random.Random(seed)
    cumulative: list[float] = []
    running = 0.0
    for _ in range(total_events):
        running += 0.0 if not enabled else rng.uniform(0.5, 1.5)
        cumulative.append(round(running, 3))
    state = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_events": total_events,
        "cumulative_delays": cumulative,
        "playback_enabled": enabled,
    }
    artifacts.write_json(run_dir / "playback_state.json", state)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


def _run_dir(runs_dir: Path, run_id: str) -> Path:
    run_dir = runs_dir / run_id
    if not run_dir.exists() or not (run_dir / "meta.json").exists():
        raise MeetingNotFound(run_id)
    return run_dir


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _is_council_meeting(run_dir: Path) -> bool:
    return (run_dir / "agents" / "round1" / "product_ba.json").exists()


def _events_for(run_dir: Path) -> list[dict]:
    events = _read_json(run_dir / "events.json")
    if events is not None:
        return events
    return meeting_events.build_events(run_dir)  # legacy run without events.json cached


def _revealed_count(run_dir: Path, total_events: int) -> tuple[int, bool]:
    state = _read_json(run_dir / "playback_state.json")
    if state is None:
        return total_events, True  # legacy/CLI run: show everything, already "complete"
    if not state.get("playback_enabled", True):
        return total_events, True
    started_at = datetime.fromisoformat(state["started_at"])
    now = datetime.now(started_at.tzinfo or timezone.utc)
    elapsed = (now - started_at).total_seconds()
    cumulative = state.get("cumulative_delays", [])
    revealed = bisect.bisect_right(cumulative, elapsed)
    revealed = min(revealed, total_events)
    return revealed, revealed >= total_events


def list_comparisons(runs_dir: Path) -> list[dict]:
    comparisons_dir = runs_dir / "comparisons"
    if not comparisons_dir.exists():
        return []
    rows = []
    for d in sorted(comparisons_dir.iterdir(), reverse=True):
        data = _read_json(d / "comparison.json")
        if data is None:
            continue
        rows.append(
            {
                "compare_id": d.name,
                "council_run_id": data.get("council_run_id"),
                "solo_run_id": data.get("solo_run_id"),
                "deltas": data.get("deltas", {}),
                "council_only_insights": data.get("council_only_insights", []),
            }
        )
    return rows


def list_meetings(runs_dir: Path) -> list[dict]:
    if not runs_dir.exists():
        return []
    rows = []
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir() or run_dir.name == "comparisons":
            continue
        meta = _read_json(run_dir / "meta.json")
        if meta is None:
            continue
        metrics = _read_json(run_dir / "metrics.json") or {}
        brief = (run_dir / "brief.md")
        brief_excerpt = ""
        if brief.exists():
            first_line = brief.read_text(encoding="utf-8").strip().splitlines()
            brief_excerpt = next((l.lstrip("# ").strip() for l in first_line if l.strip()), "")

        row = {
            "run_id": run_dir.name,
            "mode": meta.get("mode"),
            "provider": meta.get("provider"),
            "created_at": meta.get("created_at"),
            "brief_excerpt": brief_excerpt[:140],
            "is_meeting": _is_council_meeting(run_dir),
            "metrics": {
                "requirements_count": metrics.get("requirements_count"),
                "risks_count": metrics.get("risks_count"),
                "mind_changes_count": metrics.get("mind_changes_count"),
                "unresolved_count": metrics.get("unresolved_count"),
            },
        }
        if row["is_meeting"]:
            events = _events_for(run_dir)
            revealed, complete = _revealed_count(run_dir, len(events))
            current = events[revealed - 1] if revealed else None
            row["status"] = "completed" if complete else "in_progress"
            row["current_round"] = current["round"] if current else 0
            row["current_round_label"] = current["round_label"] if current else "Chưa bắt đầu"
            row["total_rounds"] = meta.get("round_count") or 5
            row["participants"] = sorted({e["speaker_role"] for e in events})
        else:
            row["status"] = "completed"
            row["current_round"] = None
            row["current_round_label"] = None
            row["total_rounds"] = None
            row["participants"] = []
        rows.append(row)
    return rows


def get_meeting(runs_dir: Path, run_id: str) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    return {
        "run_id": run_id,
        "meta": _read_json(run_dir / "meta.json"),
        "metrics": _read_json(run_dir / "metrics.json"),
        "consensus": _read_json(run_dir / "consensus.json"),
        "session_config": _read_json(run_dir / "session_config.json"),
        "brief": (run_dir / "brief.md").read_text(encoding="utf-8") if (run_dir / "brief.md").exists() else "",
        "is_meeting": _is_council_meeting(run_dir),
    }


def _elapsed_seconds(run_dir: Path) -> float | None:
    state = _read_json(run_dir / "playback_state.json")
    if state is None:
        return None
    started_at = datetime.fromisoformat(state["started_at"])
    now = datetime.now(started_at.tzinfo or timezone.utc)
    return round((now - started_at).total_seconds(), 1)


def get_status(runs_dir: Path, run_id: str) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    if not _is_council_meeting(run_dir):
        return {"run_id": run_id, "is_meeting": False, "status": "completed"}

    events = _events_for(run_dir)
    revealed, complete = _revealed_count(run_dir, len(events))
    visible = events[:revealed]
    current = visible[-1] if visible else None
    meta = _read_json(run_dir / "meta.json") or {}

    mind_changes = sum(1 for e in visible if e["type"] == "mind_change")
    decisions = [e for e in visible if e["type"] == "decision"]
    accepted = sum(1 for e in decisions if e["meta"].get("status") == "accepted")
    rejected = sum(1 for e in decisions if e["meta"].get("status") == "rejected")
    unresolved = sum(1 for e in decisions if e["meta"].get("status") == "unresolved")

    round_count = meta.get("round_count") or 5
    round_labels = meeting_events.ROUND_LABELS_10 if round_count == 10 else meeting_events.ROUND_LABELS_5

    return {
        "run_id": run_id,
        "is_meeting": True,
        "status": "completed" if complete else "running",
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "elapsed_seconds": _elapsed_seconds(run_dir),
        "total_events": len(events),
        "revealed_events": revealed,
        "is_complete": complete,
        "total_rounds": round_count,
        "round_labels": {str(n): label for n, label in round_labels.items()},
        "current_round": current["round"] if current else 0,
        "current_round_label": current["round_label"] if current else "Chưa bắt đầu",
        "current_speaker_role": current["speaker_role"] if current else None,
        "current_speaker_name": current["speaker_name"] if current else None,
        "mind_changes_count": mind_changes,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "unresolved_count": unresolved,
    }


def get_transcript(runs_dir: Path, run_id: str, filter_name: str = "all", since: int | None = None) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    events = _events_for(run_dir)
    revealed, complete = _revealed_count(run_dir, len(events))
    visible = events[:revealed]
    if since is not None:
        visible = [e for e in visible if e["order"] > since]
    filtered = meeting_events.events_matching(visible, filter_name)
    return {"run_id": run_id, "filter": filter_name, "is_complete": complete, "events": filtered}


def get_events(
    runs_dir: Path, run_id: str, *, round_num: int | None = None, event_type: str | None = None, since: int | None = None
) -> dict:
    """Canonical structured event feed (spec section 9) - one flat record per
    event with a stable schema external clients can rely on, distinct from
    /transcript's UI-shaped cards (speaker_name, title, details bullets).
    Always respects the same playback reveal as /status and /transcript."""
    run_dir = _run_dir(runs_dir, run_id)
    events = _events_for(run_dir)
    revealed, complete = _revealed_count(run_dir, len(events))
    visible = events[:revealed]
    if round_num is not None:
        visible = [e for e in visible if e["round"] == round_num]
    if event_type is not None:
        visible = [e for e in visible if e["type"] == event_type]
    if since is not None:
        visible = [e for e in visible if e["order"] > since]

    structured = [
        {
            "event_id": f"{run_id}:{e['order']}",
            "meeting_id": run_id,
            "order": e["order"],
            "round": e["round"],
            "round_name": e["round_label"],
            "role": e["speaker_role"],
            "type": e["type"],
            "target_role": e["target_role"],
            "severity": e.get("meta", {}).get("severity"),
            "summary": e["title"],
            "content": e["text"],
            "details": e["details"],
            "timestamp": e.get("timestamp"),
        }
        for e in visible
    ]
    return {"run_id": run_id, "meeting_id": run_id, "is_complete": complete, "events": structured}


def get_metrics(runs_dir: Path, run_id: str) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    meta = _read_json(run_dir / "meta.json") or {}
    metrics = _read_json(run_dir / "metrics.json") or {}
    is_mock = meta.get("provider") == "mock"
    return {
        "run_id": run_id,
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "is_mock_provider": is_mock,
        "cost_is_proxy": is_mock,  # mock has no real API cost - tokens_in/out/cost are a deterministic char-count proxy
        **metrics,
    }


def get_participants(runs_dir: Path, run_id: str) -> dict:
    """Per-role computed state for the Meeting Room's participant list - all
    derived server-side from revealed events, per spec section 9 ("backend
    expose structured meeting events", not text the frontend has to parse)."""
    from council.web.role_catalog import build_role_catalog

    run_dir = _run_dir(runs_dir, run_id)
    if not _is_council_meeting(run_dir):
        return {"run_id": run_id, "is_meeting": False, "participants": []}

    events = _events_for(run_dir)
    revealed, complete = _revealed_count(run_dir, len(events))
    visible = events[:revealed]
    current = visible[-1] if visible else None
    current_role = current["speaker_role"] if current else None

    next_role = None
    if not complete:
        for e in events[revealed:]:
            if e["speaker_role"] != current_role:
                next_role = e["speaker_role"]
                break

    spoken_roles = {e["speaker_role"] for e in visible}
    mind_change_roles = {e["speaker_role"] for e in visible if e["type"] == "mind_change"}
    disagreement_roles: set[str] = set()
    critical_roles: set[str] = set()
    last_action: dict[str, dict] = {}
    for e in visible:
        if e["type"] in ("disagreement", "critique"):
            disagreement_roles.add(e["speaker_role"])
            if e.get("target_role"):
                disagreement_roles.add(e["target_role"])
        if e.get("meta", {}).get("severity") == "high":
            critical_roles.add(e["speaker_role"])
            if e.get("target_role"):
                critical_roles.add(e["target_role"])
        last_action[e["speaker_role"]] = {"title": e["title"], "round": e["round"], "type": e["type"]}

    catalog = build_role_catalog()
    participants = []
    for role in catalog["roles"]:
        if role["role_type"] == "observer":
            continue  # not a meeting participant - see /api/meetings/{id}/summary instead
        role_id = role["id"]
        if role_id == current_role and not complete:
            state = "speaking"
        elif role_id == next_role:
            state = "thinking"
        elif role_id in spoken_roles:
            state = "done"
        else:
            state = "waiting"
        participants.append(
            {
                "id": role_id,
                "display_name": role["display_name"],
                "role_type": role["role_type"],
                "state": state,
                "provider": role["runtime_provider"],
                "model": role["runtime_model"],
                "skills": role["skills"],
                "has_mind_change": role_id in mind_change_roles,
                "has_active_disagreement": role_id in disagreement_roles,
                "has_critical_risk": role_id in critical_roles,
                "last_action": last_action.get(role_id),
            }
        )
    return {"run_id": run_id, "is_meeting": True, "is_complete": complete, "participants": participants}


def get_summary(runs_dir: Path, run_id: str) -> dict:
    """ChatGPT/human-oriented summary payload - see spec for the required shape."""
    run_dir = _run_dir(runs_dir, run_id)
    meeting = get_meeting(runs_dir, run_id)
    if not meeting["is_meeting"]:
        return {"run_id": run_id, "is_meeting": False}

    events = _events_for(run_dir)
    revealed, complete = _revealed_count(run_dir, len(events))
    visible = events[:revealed]
    current = visible[-1] if visible else None
    session_config = meeting.get("session_config") or {}

    def _decision_text(details: list[str]) -> str | None:
        for d in details:
            if d.startswith("Decision: "):
                return d[len("Decision: "):]
        return None

    decisions = [e for e in visible if e["type"] == "decision"]
    accepted = [
        {"topic": e["meta"]["topic"], "decision": _decision_text(e["details"]), "rationale": e["text"], "details": e["details"]}
        for e in decisions
        if e["meta"].get("status") == "accepted"
    ]
    rejected = [{"topic": e["meta"]["topic"], "rationale": e["text"], "details": e["details"]} for e in decisions if e["meta"].get("status") == "rejected"]
    unresolved = [{"topic": e["meta"]["topic"], "rationale": e["text"], "details": e["details"]} for e in decisions if e["meta"].get("status") == "unresolved"]

    major_arguments = [
        f"{e['speaker_name']} vs {e.get('target_name') or '(general)'}: {e['text']}"
        for e in visible
        if e["type"] in ("disagreement", "critique")
    ][:8]
    mind_changes = [
        {"role": e["speaker_name"], "topic": e["meta"].get("topic"), "reason": e["text"], "details": e["details"]}
        for e in visible
        if e["type"] == "mind_change"
    ]
    risks = []
    for e in visible:
        if e["type"] == "risk":
            risks.append(e["text"])
        risks.extend(d[len("Risk: "):] for d in e.get("details", []) if d.startswith("Risk: "))
    risks = list(dict.fromkeys(risks))  # dedupe, preserve order

    role_names = {e["speaker_role"]: e["speaker_name"] for e in events}
    role_skills = session_config.get("role_skills") or {}
    participants_with_skills = [
        {"role": r, "name": name, "skills": role_skills.get(r, [])} for r, name in sorted(role_names.items())
    ]

    total_rounds = (meeting.get("meta") or {}).get("round_count") or 5
    if not complete:
        recommendation = (
            f"Cuộc họp đang diễn ra (vòng {current['round'] if current else 0}/{total_rounds}). "
            "Chưa đạt đồng thuận cuối - đừng coi bất kỳ mục nào dưới đây là quyết định cuối cùng."
        )
    else:
        consensus = meeting.get("consensus") or {}
        recommendation = consensus.get("summary", "") + " Cần bạn (người dùng) tự quyết định các mục chưa giải quyết."

    return {
        "run_id": run_id,
        "brief": meeting["brief"],
        "participants": participants_with_skills,
        "current_round": current["round"] if current else 0,
        "total_rounds": total_rounds,
        "current_round_label": current["round_label"] if current else "Chưa bắt đầu",
        "is_complete": complete,
        "accepted": accepted,
        "rejected": rejected,
        "unresolved": unresolved,
        "major_arguments": major_arguments,
        "mind_changes": mind_changes,
        "risks": risks,
        "recommendation": recommendation.strip(),
        "last_events": visible[-5:],
        "human_decision_required": True,
        "note": "Payload này chỉ phản ánh những gì đã diễn ra trong cuộc họp tính đến hiện tại. Người dùng là người quyết định cuối cùng - không trình bày các mục chưa giải quyết như đã được quyết định.",
    }


# --------------------------------------------------------------------------
# artifacts (read-only file access, path-traversal guarded)
# --------------------------------------------------------------------------


def list_artifacts(runs_dir: Path, run_id: str) -> list[dict]:
    run_dir = _run_dir(runs_dir, run_id)
    manifest = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            manifest.append(
                {
                    "path": str(path.relative_to(run_dir)),
                    "size_bytes": path.stat().st_size,
                    "kind": path.suffix.lstrip("."),
                }
            )
    return manifest


def read_artifact(runs_dir: Path, run_id: str, relpath: str) -> str:
    run_dir = _run_dir(runs_dir, run_id)
    candidate = (run_dir / relpath).resolve()
    if run_dir.resolve() not in candidate.parents and candidate != run_dir.resolve():
        raise InvalidArtifactPath(relpath)
    if not candidate.is_file():
        raise InvalidArtifactPath(relpath)
    return candidate.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# human decisions
# --------------------------------------------------------------------------


def get_human_decisions(runs_dir: Path, run_id: str) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    stored = _read_json(run_dir / "human_decisions.json")
    if stored is not None:
        return stored

    consensus = _read_json(run_dir / "consensus.json") or {"items": []}
    scaffold = {"run_id": run_id, "updated_at": None, "decisions": {}}
    for item in consensus.get("items", []):
        default_choice = "pending" if item["status"] == "unresolved" else ("approve" if item["status"] == "accepted" else "acknowledge")
        scaffold["decisions"][item["topic"]] = {
            "status_from_council": item["status"],
            "human_choice": default_choice,
            "note": "",
        }
    return scaffold


def save_human_decisions(runs_dir: Path, run_id: str, decisions: list[dict]) -> dict:
    run_dir = _run_dir(runs_dir, run_id)
    current = get_human_decisions(runs_dir, run_id)
    for d in decisions:
        topic = d["topic"]
        entry = current["decisions"].setdefault(topic, {"status_from_council": None, "human_choice": "pending", "note": ""})
        entry["human_choice"] = d.get("human_choice", entry["human_choice"])
        entry["note"] = d.get("note", entry.get("note", ""))
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    artifacts.write_json(run_dir / "human_decisions.json", current)

    _write_final_summary_for_chatgpt(runs_dir, run_id, current)
    return current


def _write_final_summary_for_chatgpt(runs_dir: Path, run_id: str, human_decisions: dict) -> None:
    run_dir = _run_dir(runs_dir, run_id)
    summary = get_summary(runs_dir, run_id)
    pending = [t for t, d in human_decisions["decisions"].items() if d["human_choice"] == "pending"]
    payload = {
        **summary,
        "human_decisions": human_decisions["decisions"],
        "human_decisions_updated_at": human_decisions["updated_at"],
        "still_pending_topics": pending,
        "recommendation": (
            f"{len(pending)} topic(s) still awaiting a human decision: {', '.join(pending)}."
            if pending
            else "All topics have a recorded human decision. " + summary.get("recommendation", "")
        ).strip(),
    }
    artifacts.write_json(run_dir / "final_summary_for_chatgpt.json", payload)
