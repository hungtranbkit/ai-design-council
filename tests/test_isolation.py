"""Round 1 must be strictly isolated: no agent may see any other agent's output."""
from __future__ import annotations

from council.pipeline.orchestrator import CouncilOrchestrator
from council.providers.mock import MockProvider

BRIEF = "A minimal test brief."


class RecordingProvider(MockProvider):
    """Wraps MockProvider but records every context dict handed to it."""

    def __init__(self):
        super().__init__()
        self.seen_contexts: list[tuple[str, int, dict]] = []

    def complete(self, *, role, round_num, system_prompt, user_prompt, response_model, context):
        self.seen_contexts.append((role, round_num, dict(context)))
        return super().complete(
            role=role,
            round_num=round_num,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            context=context,
        )


def test_round1_context_contains_only_the_brief():
    provider = RecordingProvider()
    orchestrator = CouncilOrchestrator(provider=provider)
    orchestrator.run_round1(BRIEF)

    round1_calls = [c for c in provider.seen_contexts if c[1] == 1]
    assert len(round1_calls) == 6  # all 6 council roles called
    for role, _round, context in round1_calls:
        assert set(context.keys()) == {"brief"}, f"round1 call for {role} leaked extra context: {context.keys()}"
        assert context["brief"] == BRIEF


def test_round1_proposals_do_not_reference_each_other_role_ids():
    """Belt-and-suspenders: no round-1 proposal's own text mentions another role id,
    which would be a smell that isolation was violated upstream of the schema."""
    provider = MockProvider()
    orchestrator = CouncilOrchestrator(provider=provider)
    round1 = orchestrator.run_round1(BRIEF)

    other_role_ids = set(round1.keys())
    for role_id, proposal in round1.items():
        others = other_role_ids - {role_id}
        blob = " ".join(proposal.requirements + proposal.decisions + proposal.risks).lower()
        for other in others:
            assert other not in blob, f"{role_id}'s round1 proposal mentions role id '{other}'"


def test_full_run_calls_round1_before_any_round2():
    """The orchestrator must not begin round2 calls until every round1 call is done."""
    provider = RecordingProvider()
    orchestrator = CouncilOrchestrator(provider=provider)
    orchestrator.run(BRIEF)

    rounds_in_order = [r for _role, r, _ctx in provider.seen_contexts]
    first_round2_index = rounds_in_order.index(2)
    # every round-1 call must appear before the first round-2 call
    last_round1_index = max(i for i, r in enumerate(rounds_in_order) if r == 1)
    assert last_round1_index < first_round2_index
