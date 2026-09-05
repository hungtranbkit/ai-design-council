"""General orchestration correctness: round coverage, ordering, metrics shape."""
from __future__ import annotations

from council.agents.loader import COUNCIL_ROLE_IDS
from council.metrics import compute_council_metrics, compute_solo_metrics
from council.pipeline.orchestrator import REVIEW_ASSIGNMENTS, CouncilOrchestrator
from council.pipeline.schemas import ConsensusReport, CrossReview, Defense, DevilsAdvocateReport, Proposal
from council.pipeline.single_agent import run_solo
from council.providers.mock import MockProvider

BRIEF = "A minimal test brief about a QR-ordering restaurant system."


def test_review_assignments_cover_every_role_as_reviewer():
    assert set(REVIEW_ASSIGNMENTS.keys()) == set(COUNCIL_ROLE_IDS)
    for reviewer, targets in REVIEW_ASSIGNMENTS.items():
        assert targets, f"{reviewer} has no review targets"
        assert reviewer not in targets, f"{reviewer} cannot review itself"
        for t in targets:
            assert t in COUNCIL_ROLE_IDS


def test_full_run_produces_all_expected_round_types():
    result = CouncilOrchestrator(provider=MockProvider()).run(BRIEF)

    assert set(result.round1.keys()) == set(COUNCIL_ROLE_IDS)
    assert all(isinstance(p, Proposal) for p in result.round1.values())

    for reviewer, targets in REVIEW_ASSIGNMENTS.items():
        assert set(result.round2[reviewer].keys()) == set(targets)
        for review in result.round2[reviewer].values():
            assert isinstance(review, CrossReview)

    assert isinstance(result.round3, DevilsAdvocateReport)

    # every debating role except devils_advocate gets a defense
    expected_defenders = set(COUNCIL_ROLE_IDS) - {"devils_advocate"}
    assert set(result.round4.keys()) == expected_defenders
    assert all(isinstance(d, Defense) for d in result.round4.values())

    assert isinstance(result.round5, ConsensusReport)


def test_call_log_records_every_provider_call():
    result = CouncilOrchestrator(provider=MockProvider()).run(BRIEF)
    n_round1 = 6
    n_round2 = sum(len(v) for v in REVIEW_ASSIGNMENTS.values())
    n_round3 = 1
    n_round4 = 5
    n_round5 = 1
    assert len(result.calls) == n_round1 + n_round2 + n_round3 + n_round4 + n_round5
    assert all(c.provider_name == "mock" for c in result.calls)
    assert all(c.latency_seconds >= 0 for c in result.calls)


def test_council_metrics_shape():
    result = CouncilOrchestrator(provider=MockProvider()).run(BRIEF)
    m = compute_council_metrics(result)
    for key in [
        "requirements_count", "edge_cases_count", "risks_count", "unresolved_count",
        "mind_changes_count", "duration_seconds", "tokens_in", "tokens_out", "trajectory",
    ]:
        assert key in m
    assert m["requirements_count"] > 0
    assert m["duration_seconds"] >= 0
    assert len(m["trajectory"]) == 5


def test_solo_metrics_shape():
    result = run_solo(MockProvider(), BRIEF)
    m = compute_solo_metrics(result)
    assert m["mode"] == "single-agent"
    assert m["mind_changes_count"] == 0
    assert m["requirements_count"] > 0
