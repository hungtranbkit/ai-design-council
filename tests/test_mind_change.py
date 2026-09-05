"""Verifies the pipeline produces real, meaningful mind changes - not just echo/consensus theater."""
from __future__ import annotations

from council.pipeline.orchestrator import CouncilOrchestrator
from council.providers.mock import MockProvider

BRIEF = "A minimal test brief about a QR-ordering restaurant system."


def _run():
    orchestrator = CouncilOrchestrator(provider=MockProvider())
    return orchestrator.run(BRIEF)


def test_at_least_three_mind_changes_recorded():
    result = _run()
    all_changes = [cd for defense in result.round4.values() for cd in defense.changed_decisions]
    assert len(all_changes) >= 3, f"expected >=3 mind changes, got {len(all_changes)}"


def test_mind_changes_span_more_than_one_agent():
    """A real debate changes more than one person's mind; if only one agent ever
    revises, that's a sign the 'critique' isn't actually landing on anyone else."""
    result = _run()
    roles_that_changed = {role for role, defense in result.round4.items() if defense.changed_decisions}
    assert len(roles_that_changed) >= 2, f"only {roles_that_changed} changed - debate looks one-sided"


def test_devils_advocate_report_has_no_rubber_stamp_and_covers_all_categories():
    result = _run()
    report = result.round3
    assert len(report.findings) >= 5
    assert report.missing_categories() == set(), f"missing categories: {report.missing_categories()}"


def test_not_every_agent_caves_some_defend_their_position():
    """A believable debate has some agents standing firm, not universal capitulation."""
    result = _run()
    stances = [r.stance for defense in result.round4.values() for r in defense.responses]
    assert "defend" in stances, "no agent ever defended a position - looks like blanket agreement, not debate"
    assert "revise" in stances, "no agent ever revised - looks like the critique had no real effect"


def test_consensus_is_not_a_pure_majority_vote():
    """Every consensus item must carry a rationale, and at least one item must be
    explicitly unresolved rather than forced to a false resolution."""
    result = _run()
    consensus = result.round5
    assert all(item.rationale.strip() for item in consensus.items)
    unresolved = consensus.by_status("unresolved")
    assert len(unresolved) >= 1, "expected at least one genuinely unresolved item requiring a human decision"


def test_specific_expected_topics_change():
    """Sanity-check the demo narrative: the QR-signing and realtime-transport
    topics (the two headline contested points in the example brief) should be
    among the recorded mind changes."""
    result = _run()
    topics_changed = {cd.topic for defense in result.round4.values() for cd in defense.changed_decisions}
    assert "qr_signing" in topics_changed
    assert "realtime_transport" in topics_changed
