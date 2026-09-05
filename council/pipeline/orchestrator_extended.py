"""The 10-round council orchestrator - a deeper analysis pipeline than the
original 5-round one (council/pipeline/orchestrator.py, kept completely
unchanged for backward compatibility with every existing run/test).

    R1  Hiểu bài toán & giả định độc lập   - interpret the brief, state
                                              assumptions, BEFORE proposing
                                              anything. Genuinely new: the old
                                              Round 1 jumped straight to a
                                              solution.
    R2  Đề xuất giải pháp độc lập           - independent proposals (same
                                              shape as the old Round 1).
    R3  Phản biện chéo: Yêu cầu/UX/Kinh doanh - cross-review from the
                                              business/UX-facing roles.
    R4  Phản biện chéo: Kiến trúc/Bảo mật/Vận hành - cross-review from the
                                              technical roles. R3+R4 together
                                              cover exactly the same 12
                                              reviewer->target pairs the old
                                              Round 2 did, split by the
                                              reviewer's own lens.
    R5  Devil's Advocate                    - same mandatory-critique shape
                                              as the old Round 3, now
                                              informed by two review rounds
                                              instead of one.
    R6  Phương án thay thế                  - NEW: every role must produce a
                                              genuine "B option" for one of
                                              their own Round 2 decisions,
                                              with >=2 concrete trade-offs
                                              (schema-enforced).
    R7  Bảo vệ & sửa quan điểm              - same Defense/ChangedDecision
                                              shape as the old Round 4, now
                                              informed by R3+R4+R5+R6.
    R8  Edge case & Pre-mortem              - NEW: assume the project failed
                                              ~6 months in; every role names a
                                              concrete failure scenario and
                                              root cause from their own lens.
    R9  Hội tụ (Convergence)                - NEW: an honest inventory of
                                              what's still contradictory or
                                              dependent before the final
                                              round - not a decision itself.
    R10 Moderator - Đồng thuận cuối         - same ConsensusReport shape as
                                              the old Round 5, now informed by
                                              9 rounds instead of 4.

Isolation is structural exactly as in the 5-round pipeline: Round 1 and
Round 2 each hand every role ONLY the brief (plus, for Round 2, that same
role's own Round 1 output - continuity of one role's own thinking is not a
cross-role leak) - never another role's output.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from council.agents.loader import RoleConfig, load_council_roles, load_moderator
from council.pipeline.orchestrator import LANGUAGE_INSTRUCTIONS, CallRecord
from council.pipeline.schemas import (
    AlternativeProposal,
    ConsensusReport,
    ConvergenceReport,
    CrossReview,
    Defense,
    DevilsAdvocateReport,
    PreMortemFinding,
    ProblemUnderstanding,
    Proposal,
)
from council.providers.base import Provider, ProviderResponse

TOTAL_ROUNDS = 10

ROUND_LABELS: dict[int, str] = {
    1: "Hiểu bài toán & giả định",
    2: "Đề xuất giải pháp",
    3: "Phản biện: Yêu cầu / UX / Kinh doanh",
    4: "Phản biện: Kiến trúc / Bảo mật / Vận hành",
    5: "Devil's Advocate",
    6: "Phương án thay thế",
    7: "Bảo vệ & sửa quan điểm",
    8: "Edge case & Pre-mortem",
    9: "Hội tụ (Convergence)",
    10: "Đồng thuận cuối (Moderator)",
}

# R3 = reviews authored by the business/UX-facing roles; R4 = reviews authored
# by the technical roles. Together these are exactly the 12 reviewer->target
# pairs the 5-round pipeline's REVIEW_ASSIGNMENTS uses, just split by round.
R3_REVIEW_ASSIGNMENTS: dict[str, list[str]] = {
    "product_ba": ["architect", "qa_security"],
    "ux_designer": ["product_ba", "architect"],
    "business_critic": ["architect", "product_ba"],
}
R4_REVIEW_ASSIGNMENTS: dict[str, list[str]] = {
    "architect": ["ux_designer", "business_critic"],
    "qa_security": ["product_ba", "architect"],
    "devils_advocate": ["architect", "ux_designer"],
}

# Standing analysis-discipline instructions, prepended to every extended-round
# system_prompt (after any language instruction) - the lightest possible hook
# for a real LLM provider to follow the same discipline MockProvider's
# hand-authored content already demonstrates. MockProvider itself ignores
# system_prompt entirely (see providers/mock.py), so this has zero effect on
# the deterministic demo path; it only matters once a real provider is wired.
DISCIPLINE_INSTRUCTIONS = (
    "Kỷ luật phân tích bắt buộc cho vòng này:\n"
    "- Luôn nêu rõ assumption (giả định) bạn đang dựa vào.\n"
    "- Mọi nhận định phải có evidence/rationale cụ thể, không nói chung chung.\n"
    "- Khi phù hợp, nêu ít nhất 2 rủi ro hoặc trade-off.\n"
    "- Phản biện phải nhắm trực tiếp vào luận điểm của role khác, không phản biện chung chung.\n"
    "- Khi đề xuất requirement, phân loại rõ MUST / SHOULD / COULD.\n"
    "- Không được 'đồng ý' (rubber-stamp) mà không giải thích lý do cụ thể.\n"
    "- Nếu đổi ý so với vòng trước, phải ghi rõ before -> after -> reason.\n"
    "- Nếu thiếu dữ liệu để kết luận, hãy đánh dấu là uncertainty, không bịa.\n"
)


@dataclass
class ExtendedCouncilRunResult:
    round1: dict[str, ProblemUnderstanding]
    round2: dict[str, Proposal]
    round3: dict[str, dict[str, CrossReview]]
    round4: dict[str, dict[str, CrossReview]]
    round5: DevilsAdvocateReport
    round6: dict[str, AlternativeProposal]
    round7: dict[str, Defense]
    round8: dict[str, PreMortemFinding]
    round9: ConvergenceReport
    round10: ConsensusReport
    calls: list[CallRecord] = field(default_factory=list)
    wall_time_seconds: float = 0.0


class ExtendedCouncilOrchestrator:
    """10-round pipeline. Entirely separate from CouncilOrchestrator (which
    stays untouched) so the original 5-round pipeline's guarantees are never
    at risk from this file."""

    def __init__(self, provider: Provider, roles: list[RoleConfig] | None = None, language: str | None = None):
        self.provider = provider
        self.roles: dict[str, RoleConfig] = {r.id: r for r in (roles or load_council_roles())}
        self.moderator = load_moderator()
        self.language = language
        self._calls: list[CallRecord] = []

    # -- internal -----------------------------------------------------------

    def _system_prompt(self, base: str) -> str:
        parts = [DISCIPLINE_INSTRUCTIONS]
        language_instruction = LANGUAGE_INSTRUCTIONS.get(self.language or "")
        if language_instruction:
            parts.insert(0, language_instruction)
        return "\n\n".join([*parts, base])

    def _call(self, *, role: str, round_num: int, system_prompt: str, user_prompt: str, response_model, context: dict[str, Any]):
        resp: ProviderResponse = self.provider.complete(
            role=role,
            round_num=round_num,
            system_prompt=self._system_prompt(system_prompt),
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

    def run_round1(self, brief_text: str) -> dict[str, ProblemUnderstanding]:
        """Hiểu bài toán & giả định - isolation is structural: the only
        context here is {"brief": brief_text}, exactly like the 5-round
        pipeline's Round 1 (see tests/test_isolation.py's 10-round sibling)."""
        results: dict[str, ProblemUnderstanding] = {}
        for role_id, role in self.roles.items():
            context = {"brief": brief_text}
            user_prompt = (
                f"Đọc kỹ đề bài dưới đây. Trước khi đề xuất bất kỳ giải pháp nào, hãy nêu cách bạn hiểu vấn đề, "
                f"các giả định bạn đang dựa vào, và câu hỏi làm rõ nếu có.\n\n--- ĐỀ BÀI ---\n{brief_text}\n"
            )
            results[role_id] = self._call(
                role=role_id,
                round_num=1,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=ProblemUnderstanding,
                context=context,
            )
        return results

    def run_round2(self, brief_text: str, round1: dict[str, ProblemUnderstanding]) -> dict[str, Proposal]:
        """Đề xuất giải pháp độc lập - each role only sees its OWN Round 1
        output, never another role's (structural isolation, same guarantee
        as the 5-round pipeline's independent-proposal round)."""
        results: dict[str, Proposal] = {}
        for role_id, role in self.roles.items():
            own_understanding = round1[role_id].model_dump()
            context = {"brief": brief_text, "own_understanding": own_understanding}
            user_prompt = (
                f"Dựa trên cách bạn đã hiểu vấn đề ở vòng trước, hãy đề xuất giải pháp cụ thể. Phân loại rõ "
                f"requirement nào là MUST / SHOULD / COULD.\n\n--- ĐỀ BÀI ---\n{brief_text}\n\n"
                f"--- CÁCH BẠN HIỂU VẤN ĐỀ (vòng 1) ---\n{own_understanding}\n"
            )
            results[role_id] = self._call(
                role=role_id,
                round_num=2,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=Proposal,
                context=context,
            )
        return results

    def _run_cross_review_round(
        self, round_num: int, assignments: dict[str, list[str]], brief_text: str, round2: dict[str, Proposal]
    ) -> dict[str, dict[str, CrossReview]]:
        results: dict[str, dict[str, CrossReview]] = {}
        for reviewer_id, targets in assignments.items():
            role = self.roles[reviewer_id]
            results[reviewer_id] = {}
            for target_id in targets:
                target_proposal = round2[target_id].model_dump()
                context = {"brief": brief_text, "target_role": target_id, "target_proposal": target_proposal}
                user_prompt = (
                    f"Phản biện đề xuất của {target_id}. Đồng ý điểm nào, không đồng ý điểm nào (phải nêu lý do "
                    f"cụ thể, không rubber-stamp), thiếu requirement gì, rủi ro gì, và đề xuất thay đổi gì.\n\n"
                    f"--- ĐỀ XUẤT CỦA {target_id} ---\n{target_proposal}\n"
                )
                results[reviewer_id][target_id] = self._call(
                    role=reviewer_id,
                    round_num=round_num,
                    system_prompt=role.system_prompt,
                    user_prompt=user_prompt,
                    response_model=CrossReview,
                    context=context,
                )
        return results

    def run_round3(self, brief_text: str, round2: dict[str, Proposal]) -> dict[str, dict[str, CrossReview]]:
        """Phản biện chéo - lăng kính Yêu cầu / UX / Kinh doanh."""
        return self._run_cross_review_round(3, R3_REVIEW_ASSIGNMENTS, brief_text, round2)

    def run_round4(self, brief_text: str, round2: dict[str, Proposal]) -> dict[str, dict[str, CrossReview]]:
        """Phản biện chéo - lăng kính Kiến trúc / Bảo mật / Vận hành."""
        return self._run_cross_review_round(4, R4_REVIEW_ASSIGNMENTS, brief_text, round2)

    def run_round5(
        self,
        brief_text: str,
        round2: dict[str, Proposal],
        round3: dict[str, dict[str, CrossReview]],
        round4: dict[str, dict[str, CrossReview]],
    ) -> DevilsAdvocateReport:
        role = self.roles["devils_advocate"]
        proposals_dump = {rid: p.model_dump() for rid, p in round2.items()}
        reviews_dump = {
            rid: {t: r.model_dump() for t, r in tmap.items()}
            for rid, tmap in {**round3, **round4}.items()
        }
        context = {"brief": brief_text, "proposals": proposals_dump, "reviews": reviews_dump}
        user_prompt = (
            "Đọc toàn bộ đề xuất và phản biện chéo ở trên. Bắt buộc tìm ra hidden assumption, "
            "unnecessary complexity, missing business case, scalability, ux, security, và operations gap. "
            "Không được trả lời kiểu 'ổn rồi'.\n\n"
            f"--- ĐỀ XUẤT (vòng 2) ---\n{proposals_dump}\n\n--- PHẢN BIỆN CHÉO (vòng 3+4) ---\n{reviews_dump}\n"
        )
        return self._call(
            role="devils_advocate",
            round_num=5,
            system_prompt=role.system_prompt,
            user_prompt=user_prompt,
            response_model=DevilsAdvocateReport,
            context=context,
        )

    def run_round6(
        self,
        brief_text: str,
        round2: dict[str, Proposal],
        round5: DevilsAdvocateReport,
    ) -> dict[str, AlternativeProposal]:
        """Phương án thay thế - mỗi role bắt buộc đưa ra một phương án B cho
        chính quyết định của mình, kèm >=2 trade-off cụ thể (schema-enforced)."""
        results: dict[str, AlternativeProposal] = {}
        for role_id, role in self.roles.items():
            own_proposal = round2[role_id].model_dump()
            context = {"brief": brief_text, "own_proposal": own_proposal, "devils_advocate": round5.model_dump()}
            user_prompt = (
                f"Chọn một quyết định chính của bạn ở vòng 2 và đề xuất một phương án thay thế (B option) thật "
                f"sự khác, không phải chỉ tối ưu phương án cũ. Nêu ít nhất 2 trade-off cụ thể.\n\n"
                f"--- ĐỀ XUẤT CỦA BẠN (vòng 2) ---\n{own_proposal}\n"
            )
            results[role_id] = self._call(
                role=role_id,
                round_num=6,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=AlternativeProposal,
                context=context,
            )
        return results

    def _critiques_for(
        self,
        role_id: str,
        round3: dict[str, dict[str, CrossReview]],
        round4: dict[str, dict[str, CrossReview]],
        round5: DevilsAdvocateReport,
    ) -> list[dict[str, Any]]:
        critiques: list[dict[str, Any]] = []
        for reviewer_id, tmap in {**round3, **round4}.items():
            if role_id in tmap:
                critiques.append({"source": f"{reviewer_id} (round3/4)", **tmap[role_id].model_dump()})
        for finding in round5.findings:
            if finding.target_role == role_id or finding.target_role is None:
                critiques.append({"source": "devils_advocate (round5)", **finding.model_dump()})
        return critiques

    def run_round7(
        self,
        brief_text: str,
        round2: dict[str, Proposal],
        round3: dict[str, dict[str, CrossReview]],
        round4: dict[str, dict[str, CrossReview]],
        round5: DevilsAdvocateReport,
        round6: dict[str, AlternativeProposal],
    ) -> dict[str, Defense]:
        results: dict[str, Defense] = {}
        for role_id, role in self.roles.items():
            if role_id == "devils_advocate":
                continue  # the critic doesn't defend - only the 5 stakeholders + moderator's later synthesis do
            critiques = self._critiques_for(role_id, round3, round4, round5)
            own_proposal = round2[role_id].model_dump()
            own_alternative = round6[role_id].model_dump()
            context = {"brief": brief_text, "own_proposal": own_proposal, "critiques": critiques, "own_alternative": own_alternative}
            user_prompt = (
                f"Trả lời từng phản biện bạn nhận được: bảo vệ (nêu lý do cụ thể) hoặc sửa quan điểm (ghi rõ "
                f"before -> after -> reason). Cân nhắc cả phương án thay thế bạn tự đề xuất ở vòng 6.\n\n"
                f"--- ĐỀ XUẤT CỦA BẠN (vòng 2) ---\n{own_proposal}\n\n--- PHẢN BIỆN NHẬN ĐƯỢC ---\n{critiques}\n"
            )
            results[role_id] = self._call(
                role=role_id,
                round_num=7,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=Defense,
                context=context,
            )
        return results

    def run_round8(
        self, brief_text: str, round7: dict[str, Defense]
    ) -> dict[str, PreMortemFinding]:
        """Edge case & Pre-mortem - giả sử dự án thất bại sau 6 tháng."""
        results: dict[str, PreMortemFinding] = {}
        for role_id, role in self.roles.items():
            final_decisions = round7[role_id].final_decisions if role_id in round7 else []
            context = {"brief": brief_text, "final_decisions": final_decisions}
            user_prompt = (
                "Giả sử dự án này đã triển khai và thất bại rõ rệt sau 6 tháng. Từ góc nhìn chuyên môn của "
                "bạn, nguyên nhân cụ thể nhất có khả năng là gì? Hãy nêu một failure scenario cụ thể và root "
                f"cause, không nói chung chung.\n\n--- CÁC QUYẾT ĐỊNH CUỐI (vòng 7) ---\n{final_decisions}\n"
            )
            results[role_id] = self._call(
                role=role_id,
                round_num=8,
                system_prompt=role.system_prompt,
                user_prompt=user_prompt,
                response_model=PreMortemFinding,
                context=context,
            )
        return results

    def run_round9(
        self,
        brief_text: str,
        round7: dict[str, Defense],
        round8: dict[str, PreMortemFinding],
    ) -> ConvergenceReport:
        """Hội tụ - kiểm tra mâu thuẫn/dependency còn sót trước khi chốt."""
        context = {
            "brief": brief_text,
            "final_decisions": {rid: d.final_decisions for rid, d in round7.items()},
            "premortem": {rid: f.model_dump() for rid, f in round8.items()},
        }
        user_prompt = (
            "Rà soát toàn bộ quyết định cuối của từng role và các pre-mortem finding. Liệt kê mâu thuẫn chưa "
            "giải quyết, dependency giữa các quyết định, và đánh giá đã sẵn sàng để chốt đồng thuận chưa.\n\n"
            f"--- QUYẾT ĐỊNH CUỐI TỪNG ROLE (vòng 7) ---\n{context['final_decisions']}\n\n"
            f"--- PRE-MORTEM (vòng 8) ---\n{context['premortem']}\n"
        )
        return self._call(
            role="moderator",
            round_num=9,
            system_prompt=self.moderator.system_prompt,
            user_prompt=user_prompt,
            response_model=ConvergenceReport,
            context=context,
        )

    def run_round10(
        self,
        brief_text: str,
        round2: dict[str, Proposal],
        round3: dict[str, dict[str, CrossReview]],
        round4: dict[str, dict[str, CrossReview]],
        round5: DevilsAdvocateReport,
        round6: dict[str, AlternativeProposal],
        round7: dict[str, Defense],
        round8: dict[str, PreMortemFinding],
        round9: ConvergenceReport,
    ) -> ConsensusReport:
        context = {
            "brief": brief_text,
            "proposals": {rid: p.model_dump() for rid, p in round2.items()},
            "reviews": {rid: {t: r.model_dump() for t, r in tmap.items()} for rid, tmap in {**round3, **round4}.items()},
            "devils_advocate": round5.model_dump(),
            "alternatives": {rid: a.model_dump() for rid, a in round6.items()},
            "defenses": {rid: d.model_dump() for rid, d in round7.items()},
            "premortem": {rid: f.model_dump() for rid, f in round8.items()},
            "convergence": round9.model_dump(),
        }
        user_prompt = (
            "Tổng hợp toàn bộ 9 vòng tranh luận thành quyết định cuối: accepted/rejected/unresolved cho từng "
            "chủ đề, kèm rationale dựa trên evidence (không phải biểu quyết đa số), dissenting opinion nếu "
            f"còn, và mức độ ưu tiên triển khai (P0/P1/P2) cho các mục accepted.\n\n"
            f"--- HỘI TỤ (vòng 9) ---\n{round9.model_dump()}\n"
        )
        return self._call(
            role="moderator",
            round_num=10,
            system_prompt=self.moderator.system_prompt,
            user_prompt=user_prompt,
            response_model=ConsensusReport,
            context=context,
        )

    # -- entry point ------------------------------------------------------

    def run(self, brief_text: str) -> ExtendedCouncilRunResult:
        start = time.perf_counter()
        self._calls = []
        round1 = self.run_round1(brief_text)
        round2 = self.run_round2(brief_text, round1)
        round3 = self.run_round3(brief_text, round2)
        round4 = self.run_round4(brief_text, round2)
        round5 = self.run_round5(brief_text, round2, round3, round4)
        round6 = self.run_round6(brief_text, round2, round5)
        round7 = self.run_round7(brief_text, round2, round3, round4, round5, round6)
        round8 = self.run_round8(brief_text, round7)
        round9 = self.run_round9(brief_text, round7, round8)
        round10 = self.run_round10(brief_text, round2, round3, round4, round5, round6, round7, round8, round9)
        wall_time = time.perf_counter() - start
        return ExtendedCouncilRunResult(
            round1=round1, round2=round2, round3=round3, round4=round4, round5=round5,
            round6=round6, round7=round7, round8=round8, round9=round9, round10=round10,
            calls=list(self._calls), wall_time_seconds=wall_time,
        )
