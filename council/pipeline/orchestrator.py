"""The 5-round council orchestrator.

Round 1  Independent proposals   - strict isolation, enforced structurally below.
Round 2  Cross review            - each agent reviews a fixed subset of others.
Round 3  Devil's Advocate        - reads everything, mandatory structured critique.
Round 4  Defense / Revision      - each of the 5 debating agents responds; mind
                                    changes are recorded as ChangedDecision entries.
Round 5  Consensus / Moderator   - synthesis, not a majority vote.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from council.agents.loader import RoleConfig, load_council_roles, load_moderator
from council.pipeline import prompts
from council.pipeline.schemas import (
    ConsensusReport,
    CrossReview,
    Defense,
    DevilsAdvocateReport,
    Proposal,
)
from council.providers.base import Provider, ProviderResponse

# Fixed round-2 review assignments: reviewer_role -> [target_role, ...].
# Deliberately a *subset* of all other agents per reviewer, not everyone-reviews-
# everyone. Must stay in sync with council/providers/mock.py's _ROUND2 table.
REVIEW_ASSIGNMENTS: dict[str, list[str]] = {
    "product_ba": ["architect", "qa_security"],
    "ux_designer": ["product_ba", "architect"],
    "architect": ["ux_designer", "business_critic"],
    "business_critic": ["architect", "product_ba"],
    "qa_security": ["product_ba", "architect"],
    "devils_advocate": ["architect", "ux_designer"],
}


@dataclass
class CallRecord:
    role: str
    round: int
    tokens_in: int | None
    tokens_out: int | None
    estimated_cost_usd: float | None
    latency_seconds: float
    provider_name: str
    timestamp: str = ""  # ISO 8601 UTC; used by the web UI to order/replay events


@dataclass
class CouncilRunResult:
    round1: dict[str, Proposal]
    round2: dict[str, dict[str, CrossReview]]
    round3: DevilsAdvocateReport
    round4: dict[str, Defense]
    round5: ConsensusReport
    calls: list[CallRecord] = field(default_factory=list)
    wall_time_seconds: float = 0.0


# Optional response-language instruction, prepended to each role's
# system_prompt when CouncilOrchestrator(..., language=<key>) is set. This is
# the lightest possible hook for a real LLM provider (Anthropic/OpenAI) to
# answer in a given language - it changes nothing about the schemas, the
# round structure, or MockProvider (which ignores system_prompt entirely and
# dispatches purely off the brief's content - see providers/mock.py). Adding
# a language only means adding an entry here.
LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "vi": (
        "Hãy trả lời bằng tiếng Việt tự nhiên, dễ đọc. Chỉ giữ nguyên thuật ngữ kỹ thuật tiếng Anh "
        "khi thực sự cần thiết (ví dụ tên công nghệ, giao thức). Toàn bộ nội dung structured output "
        "(summary, requirements, decisions, risks, rationale, v.v.) đều phải bằng tiếng Việt."
    ),
}


class CouncilOrchestrator:
    def __init__(self, provider: Provider, roles: list[RoleConfig] | None = None, language: str | None = None):
        self.provider = provider
        self.roles: dict[str, RoleConfig] = {r.id: r for r in (roles or load_council_roles())}
        self.moderator = load_moderator()
        self.language = language
        self._calls: list[CallRecord] = []

    # -- internal -----------------------------------------------------------

    def _call(self, *, role: str, round_num: int, system_prompt: str, user_prompt: str, response_model, context: dict[str, Any]):
        language_instruction = LANGUAGE_INSTRUCTIONS.get(self.language or "")
        if language_instruction:
            system_prompt = f"{language_instruction}\n\n{system_prompt}"
        resp: ProviderResponse = self.provider.complete(
            role=role,
            round_num=round_num,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            context=context,
        )
        self._calls.append(
            CallRecord(
                role=role,
                round=round_num,
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                estimated_cost_usd=resp.estimated_cost_usd,
                latency_seconds=resp.latency_seconds,
                provider_name=resp.provider_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        return resp.parsed

    # -- rounds ---------------------------------------------------------

    def run_round1(self, brief_text: str) -> dict[str, Proposal]:
        """Independent proposals. Isolation is structural: the only context each
        call receives is {"brief": brief_text} - there is no code path here that
        can hand one agent's round-1 call any other agent's data."""
        results: dict[str, Proposal] = {}
        for role_id, role in self.roles.items():
            context = {"brief": brief_text}  # <- isolation boundary, see test_isolation.py
            user_prompt = prompts.render_round1_prompt(brief_text, role.round1_instructions)
            proposal = self._call(
                role=role_id,
                round_num=1,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=Proposal,
                context=context,
            )
            results[role_id] = proposal
        return results

    def run_round2(self, brief_text: str, round1: dict[str, Proposal]) -> dict[str, dict[str, CrossReview]]:
        results: dict[str, dict[str, CrossReview]] = {}
        for reviewer_id, targets in REVIEW_ASSIGNMENTS.items():
            role = self.roles[reviewer_id]
            results[reviewer_id] = {}
            for target_id in targets:
                target_proposal = round1[target_id].model_dump()
                context = {"brief": brief_text, "target_role": target_id, "target_proposal": target_proposal}
                user_prompt = prompts.render_round2_prompt(
                    brief_text, role.round2_instructions, target_id, target_proposal
                )
                review = self._call(
                    role=reviewer_id,
                    round_num=2,
                    system_prompt=role.system_prompt,
                    user_prompt=user_prompt,
                    response_model=CrossReview,
                    context=context,
                )
                results[reviewer_id][target_id] = review
        return results

    def run_round3(
        self, brief_text: str, round1: dict[str, Proposal], round2: dict[str, dict[str, CrossReview]]
    ) -> DevilsAdvocateReport:
        role = self.roles["devils_advocate"]
        proposals_dump = {rid: p.model_dump() for rid, p in round1.items()}
        reviews_dump = {rid: {t: r.model_dump() for t, r in tmap.items()} for rid, tmap in round2.items()}
        context = {"brief": brief_text, "proposals": proposals_dump, "reviews": reviews_dump}
        user_prompt = prompts.render_round3_prompt(brief_text, role.round3_instructions, proposals_dump, reviews_dump)
        return self._call(
            role="devils_advocate",
            round_num=3,
            system_prompt=role.system_prompt,
            user_prompt=user_prompt,
            response_model=DevilsAdvocateReport,
            context=context,
        )

    def _critiques_for(
        self, role_id: str, round2: dict[str, dict[str, CrossReview]], round3: DevilsAdvocateReport
    ) -> list[dict[str, Any]]:
        critiques: list[dict[str, Any]] = []
        for reviewer_id, tmap in round2.items():
            if role_id in tmap:
                critiques.append({"source": f"{reviewer_id} (round2)", **tmap[role_id].model_dump()})
        for finding in round3.findings:
            if finding.target_role == role_id or finding.target_role is None:
                critiques.append({"source": "devils_advocate (round3)", **finding.model_dump()})
        return critiques

    def run_round4(
        self,
        brief_text: str,
        round1: dict[str, Proposal],
        round2: dict[str, dict[str, CrossReview]],
        round3: DevilsAdvocateReport,
    ) -> dict[str, Defense]:
        results: dict[str, Defense] = {}
        for role_id, role in self.roles.items():
            if role_id == "devils_advocate":
                continue  # the critic doesn't defend - only the 5 stakeholders do
            critiques = self._critiques_for(role_id, round2, round3)
            own_proposal = round1[role_id].model_dump()
            context = {"brief": brief_text, "own_proposal": own_proposal, "critiques": critiques}
            user_prompt = prompts.render_round4_prompt(brief_text, role.round4_instructions, own_proposal, critiques)
            defense = self._call(
                role=role_id,
                round_num=4,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=Defense,
                context=context,
            )
            results[role_id] = defense
        return results

    def run_round5(
        self,
        brief_text: str,
        round1: dict[str, Proposal],
        round2: dict[str, dict[str, CrossReview]],
        round3: DevilsAdvocateReport,
        round4: dict[str, Defense],
    ) -> ConsensusReport:
        proposals_dump = {rid: p.model_dump() for rid, p in round1.items()}
        reviews_dump = {rid: {t: r.model_dump() for t, r in tmap.items()} for rid, tmap in round2.items()}
        round3_dump = round3.model_dump()
        round4_dump = {rid: d.model_dump() for rid, d in round4.items()}
        context = {
            "brief": brief_text,
            "proposals": proposals_dump,
            "reviews": reviews_dump,
            "devils_advocate": round3_dump,
            "defenses": round4_dump,
        }
        user_prompt = prompts.render_round5_prompt(
            brief_text, self.moderator.round5_instructions, proposals_dump, reviews_dump, round3_dump, round4_dump
        )
        return self._call(
            role="moderator",
            round_num=5,
            system_prompt=self.moderator.system_prompt,
            user_prompt=user_prompt,
            response_model=ConsensusReport,
            context=context,
        )

    # -- entry point ------------------------------------------------------

    def run(self, brief_text: str) -> CouncilRunResult:
        start = time.perf_counter()
        self._calls = []
        round1 = self.run_round1(brief_text)
        round2 = self.run_round2(brief_text, round1)
        round3 = self.run_round3(brief_text, round1, round2)
        round4 = self.run_round4(brief_text, round1, round2, round3)
        round5 = self.run_round5(brief_text, round1, round2, round3, round4)
        wall_time = time.perf_counter() - start
        return CouncilRunResult(
            round1=round1,
            round2=round2,
            round3=round3,
            round4=round4,
            round5=round5,
            calls=list(self._calls),
            wall_time_seconds=wall_time,
        )
