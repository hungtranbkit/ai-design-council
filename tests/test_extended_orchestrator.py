"""Tests for the 10-round ExtendedCouncilOrchestrator (requirement #8 of the
"raise debate quality" pass): round ordering, R1-R2 independence, Vietnamese
language-instruction propagation, non-empty critique, alternatives with
>=2 trade-offs, and mind-change detection. Mirrors the conventions of
tests/test_isolation.py and tests/test_language_and_scenarios.py but targets
ExtendedCouncilOrchestrator, which is a separate file/class from the 5-round
CouncilOrchestrator and must never affect it."""
from __future__ import annotations

from pathlib import Path

from council.pipeline.orchestrator import LANGUAGE_INSTRUCTIONS
from council.pipeline.orchestrator_extended import (
    ROUND_LABELS,
    TOTAL_ROUNDS,
    ExtendedCouncilOrchestrator,
)
from council.providers.mock import MockProvider

POS_BRIEF_PATH = Path(__file__).resolve().parent.parent / "examples" / "pos_retail_vn.md"
POS_BRIEF = POS_BRIEF_PATH.read_text(encoding="utf-8")


class RecordingProvider(MockProvider):
    """Wraps MockProvider but records every (role, round, context, system_prompt)
    handed to it - same pattern as the 5-round isolation/language tests."""

    def __init__(self):
        super().__init__()
        self.seen: list[tuple[str, int, dict, str]] = []

    def complete(self, *, role, round_num, system_prompt, user_prompt, response_model, context):
        self.seen.append((role, round_num, dict(context), system_prompt))
        return super().complete(
            role=role, round_num=round_num, system_prompt=system_prompt,
            user_prompt=user_prompt, response_model=response_model, context=context,
        )


def test_total_rounds_and_labels_are_10_and_distinct():
    assert TOTAL_ROUNDS == 10
    assert set(ROUND_LABELS.keys()) == set(range(1, 11))
    assert len(set(ROUND_LABELS.values())) == 10  # no duplicate round names


def test_pos_retail_brief_exists_and_mock_provider_supports_10_rounds():
    assert POS_BRIEF_PATH.exists(), "expected the POS-retail VN brief to be saved under examples/"
    assert MockProvider().supports_rounds(POS_BRIEF, 10)


def test_full_run_calls_rounds_in_strict_order_1_through_10():
    provider = RecordingProvider()
    result = ExtendedCouncilOrchestrator(provider=provider).run(POS_BRIEF)

    rounds_seen = [r for _role, r, _ctx, _sp in provider.seen]
    # every call for round N must appear before any call for round N+1
    for n in range(1, 10):
        last_n = max(i for i, r in enumerate(rounds_seen) if r == n)
        first_n_plus_1 = min(i for i, r in enumerate(rounds_seen) if r == n + 1)
        assert last_n < first_n_plus_1, f"round {n + 1} call started before round {n} finished"
    assert result.round10 is not None


def test_round1_context_contains_only_the_brief_no_leak():
    """R1 independence: structurally identical guarantee to the 5-round
    pipeline's Round 1 - only {"brief": ...} in context, never another role's
    output, and no early consensus visible."""
    provider = RecordingProvider()
    orchestrator = ExtendedCouncilOrchestrator(provider=provider)
    orchestrator.run_round1(POS_BRIEF)

    round1_calls = [c for c in provider.seen if c[1] == 1]
    assert len(round1_calls) == 6  # all 6 council roles called
    for role, _round, context, _sp in round1_calls:
        assert set(context.keys()) == {"brief"}, f"round1 call for {role} leaked extra context: {context.keys()}"
        assert context["brief"] == POS_BRIEF


def test_round2_context_only_has_brief_and_own_round1_never_another_roles():
    """R2 independence: each role sees only its OWN Round 1 output - continuity
    of one role's own thinking is not a cross-role leak, but seeing another
    role's Round 1 (or any early consensus) would be."""
    provider = RecordingProvider()
    orchestrator = ExtendedCouncilOrchestrator(provider=provider)
    round1 = orchestrator.run_round1(POS_BRIEF)
    orchestrator.run_round2(POS_BRIEF, round1)

    round2_calls = [c for c in provider.seen if c[1] == 2]
    assert len(round2_calls) == 6
    for role, _round, context, _sp in round2_calls:
        assert set(context.keys()) == {"brief", "own_understanding"}, context.keys()
        assert context["own_understanding"] == round1[role].model_dump()
        # must not equal (or leak) any other role's round-1 understanding
        for other_role, other_pu in round1.items():
            if other_role == role:
                continue
            assert context["own_understanding"] != other_pu.model_dump()


def test_vietnamese_language_instruction_prepended_to_every_system_prompt():
    provider = RecordingProvider()
    orchestrator = ExtendedCouncilOrchestrator(provider=provider, language="vi")
    orchestrator.run_round1(POS_BRIEF)
    assert len(provider.seen) == 6
    for _role, _round, _ctx, system_prompt in provider.seen:
        assert system_prompt.startswith(LANGUAGE_INSTRUCTIONS["vi"])


def test_no_language_set_never_injects_the_vietnamese_instruction_marker():
    provider = RecordingProvider()
    orchestrator = ExtendedCouncilOrchestrator(provider=provider)  # language=None
    orchestrator.run_round1(POS_BRIEF)
    assert all(LANGUAGE_INSTRUCTIONS["vi"] not in sp for _r, _rn, _c, sp in provider.seen)


def test_discipline_instructions_present_in_every_extended_round_system_prompt():
    """The prompt-discipline block (assumptions/evidence/MUST-SHOULD-COULD/
    no rubber-stamping/mind-change format/uncertainty) must reach every round,
    not just round 1 - it's what upgrades reasoning quality for real providers."""
    from council.pipeline.orchestrator_extended import DISCIPLINE_INSTRUCTIONS

    provider = RecordingProvider()
    ExtendedCouncilOrchestrator(provider=provider).run(POS_BRIEF)
    assert len(provider.seen) > 0
    assert all(DISCIPLINE_INSTRUCTIONS in sp for _r, _rn, _c, sp in provider.seen)


def test_round5_devils_advocate_has_concrete_non_empty_findings_all_categories():
    result = ExtendedCouncilOrchestrator(provider=MockProvider()).run(POS_BRIEF)
    assert len(result.round5.findings) >= 5
    assert result.round5.missing_categories() == set()
    for finding in result.round5.findings:
        assert finding.description.strip() != ""


def test_round6_alternatives_every_role_has_at_least_2_trade_offs():
    """Anti-shallow rule: the Alternative round must produce a real option
    B/C, not just optimize option A - schema enforces >=2 trade-offs, this
    test confirms the mock scenario actually satisfies it end to end."""
    result = ExtendedCouncilOrchestrator(provider=MockProvider()).run(POS_BRIEF)
    assert len(result.round6) == 6  # all 6 roles produced an alternative
    for role_id, alt in result.round6.items():
        assert len(alt.trade_offs) >= 2, f"{role_id}'s alternative has fewer than 2 trade-offs"
        assert alt.alternative_option.strip() != ""
        assert alt.rationale.strip() != ""


def test_round7_mind_changes_recorded_with_before_after_reason():
    result = ExtendedCouncilOrchestrator(provider=MockProvider()).run(POS_BRIEF)
    all_changes = [c for d in result.round7.values() for c in d.changed_decisions]
    assert len(all_changes) >= 3
    for change in all_changes:
        assert change.old_decision.strip() != ""
        assert change.new_decision.strip() != ""
        assert change.old_decision != change.new_decision
        assert change.reason.strip() != ""


def test_round9_convergence_report_produced_before_round10_consensus():
    result = ExtendedCouncilOrchestrator(provider=MockProvider()).run(POS_BRIEF)
    assert result.round9.round == 9
    assert result.round10.round == 10
    # dissenting/unresolved items must survive into the final consensus, not
    # be silently collapsed into a majority vote
    unresolved = result.round10.by_status("unresolved")
    assert len(unresolved) >= 1


def test_devils_advocate_does_not_defend_in_round7():
    result = ExtendedCouncilOrchestrator(provider=MockProvider()).run(POS_BRIEF)
    assert "devils_advocate" not in result.round7
