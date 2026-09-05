"""Renders final_report.md - the human/ChatGPT-readable deliverable of a run.

Per the V0 spec this must be easy to read end-to-end and must make clear that
the human is the final decision-maker, not the council.
"""
from __future__ import annotations

from typing import Any

from council.agents.display import display_name as _name
from council.pipeline.orchestrator import CouncilRunResult
from council.pipeline.orchestrator_extended import ExtendedCouncilRunResult
from council.pipeline.single_agent import SoloRunResult


def render_council_report(
    *, run_id: str, brief_text: str, result: CouncilRunResult, metrics: dict[str, Any]
) -> str:
    lines: list[str] = []
    a = lines.append

    a(f"# AI Design Council - Final Report ({run_id})")
    a("")
    a("> **You are the final decision-maker.** This report is a structured input to your")
    a("> decision, not a decision itself. Every 'accepted' item below is the council's")
    a("> recommendation, not a mandate - accept, override, or send back for another round.")
    a("")

    # --- Executive summary ---------------------------------------------
    a("## Executive Summary")
    a("")
    a(
        f"Six AI agents (Product/BA, UX Designer, Architect, Business Critic, QA+Security, "
        f"Devil's Advocate) independently designed a solution to the brief below, then "
        f"cross-reviewed each other, underwent a mandatory Devil's Advocate critique, "
        f"defended or revised their positions, and had a neutral moderator synthesize the "
        f"result - **not** by majority vote."
    )
    a("")
    a(
        f"- **{metrics['requirements_count']}** unique requirements surfaced across all proposals\n"
        f"- **{metrics['edge_cases_count']}** edge cases identified\n"
        f"- **{metrics['risks_count']}** distinct risks raised\n"
        f"- **{metrics['mind_changes_count']}** recorded mind changes (agents revising a prior decision under critique)\n"
        f"- **{metrics['accepted_count']}** decisions accepted, **{metrics['rejected_count']}** rejected, "
        f"**{metrics['unresolved_count']}** left unresolved for you to decide\n"
        f"- Devil's Advocate raised **{metrics['devils_advocate_findings_count']}** findings across categories: "
        f"{', '.join(metrics['devils_advocate_categories_covered'])}"
    )
    a("")
    a(f"Overall: {result.round5.summary}")
    a("")

    # --- Accepted decisions ---------------------------------------------
    accepted = result.round5.by_status("accepted")
    a("## Accepted Decisions")
    a("")
    if not accepted:
        a("_None accepted this run._")
        a("")
    for item in accepted:
        a(f"### {item.topic}")
        a(f"**Decision:** {item.decision}")
        a("")
        a(f"**Why:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    # --- Rejected decisions ----------------------------------------------
    rejected = result.round5.by_status("rejected")
    a("## Rejected Decisions")
    a("")
    if not rejected:
        a("_None rejected this run._")
        a("")
    for item in rejected:
        a(f"### {item.topic}")
        a(f"**Why rejected:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    # --- Unresolved: human choice required --------------------------------
    unresolved = result.round5.by_status("unresolved")
    a("## Unresolved - Requires Your Decision")
    a("")
    if not unresolved:
        a("_Nothing unresolved this run._")
        a("")
    for item in unresolved:
        a(f"### {item.topic}")
        a(f"**Why the council could not resolve this:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Evidence / positions:**")
            for e in item.evidence:
                a(f"- {e}")
            a("")
        if item.dissent:
            a(f"**Dissent:** {item.dissent}")
        a("")

    # --- Major arguments (from cross-review + devil's advocate) -----------
    a("## Major Arguments During Debate")
    a("")
    for reviewer_id, tmap in result.round2.items():
        for target_id, review in tmap.items():
            if review.disagree:
                a(f"- **{_name(reviewer_id)} vs {_name(target_id)}:** {'; '.join(review.disagree)}")
    a("")
    a("### Devil's Advocate findings (Round 3)")
    for f in result.round3.findings:
        target = f" -> targeting {_name(f.target_role)}" if f.target_role else ""
        a(f"- **[{f.category}, {f.severity}]**{target}: {f.description}")
    a("")

    # --- Mind changes -------------------------------------------------
    a("## Mind Changes (Round 4)")
    a("")
    any_change = False
    for role_id, defense in result.round4.items():
        for cd in defense.changed_decisions:
            any_change = True
            a(f"### {_name(role_id)} changed position on: {cd.topic}")
            a(f"- **Before:** {cd.old_decision}")
            a(f"- **After:** {cd.new_decision}")
            a(f"- **Reason:** {cd.reason}")
            a(f"- **Triggered by:** {cd.triggered_by}")
            a("")
    if not any_change:
        a("_No agent changed a decision this run - treat that as a signal to scrutinize the debate quality._")
        a("")

    # --- Risks ----------------------------------------------------------
    a("## All Risks Raised")
    a("")
    seen_risks: set[str] = set()
    for p in result.round1.values():
        for r in p.risks:
            key = r.strip().lower()
            if key not in seen_risks:
                seen_risks.add(key)
                a(f"- {r}")
    a("")

    # --- Recommendation ---------------------------------------------------
    a("## Recommendation")
    a("")
    a(
        "Proceed with the accepted decisions above as the V1 design baseline. Before "
        "committing engineering time, make an explicit call on each unresolved item "
        "listed above - they are business/policy questions the council correctly "
        "identified it cannot resolve on its own authority."
    )
    a("")
    a("---")
    a(f"*Metrics: {metrics['duration_seconds']}s wall time, {metrics['call_count']} agent calls "
      f"(mode={metrics.get('mode', 'council')}). See metrics.json for full detail.*")

    return "\n".join(lines) + "\n"


def render_extended_council_report(
    *, run_id: str, brief_text: str, result: ExtendedCouncilRunResult, metrics: dict[str, Any]
) -> str:
    """10-round pipeline final report - entirely in Vietnamese (default
    response language for this pipeline). See render_council_report for the
    5-round/English sibling; kept as a separate function rather than
    parameterizing that one, since the round structure genuinely differs."""
    lines: list[str] = []
    a = lines.append

    a(f"# Báo cáo cuối cùng của Hội đồng Thiết kế AI ({run_id})")
    a("")
    a("> **Bạn là người quyết định cuối cùng.** Báo cáo này là dữ liệu đầu vào có cấu trúc cho")
    a("> quyết định của bạn, không phải bản thân quyết định. Mọi mục 'accepted' dưới đây là")
    a("> khuyến nghị của council, không phải mệnh lệnh - bạn có thể chấp nhận, ghi đè, hoặc yêu cầu tranh luận thêm.")
    a("")

    a("## Tóm tắt điều hành")
    a("")
    a(
        "Sáu AI agent (Product/BA, UX Designer, Architect, Business Critic, QA+Security, Devil's "
        "Advocate) đã trải qua **10 vòng phân tích sâu**: hiểu bài toán độc lập, đề xuất giải pháp "
        "độc lập, phản biện chéo theo 2 lăng kính (yêu cầu/UX/kinh doanh và kiến trúc/bảo mật/vận "
        "hành), Devil's Advocate bắt buộc, phương án thay thế có trade-off, bảo vệ/sửa quan điểm, "
        "pre-mortem giả định thất bại, hội tụ kiểm tra mâu thuẫn, và cuối cùng Moderator tổng hợp "
        "đồng thuận - **không** bằng biểu quyết đa số."
    )
    a("")
    a(
        f"- **{metrics['requirements_count']}** yêu cầu (requirement) riêng biệt được nêu ra\n"
        f"- **{metrics['edge_cases_count']}** edge case được xác định\n"
        f"- **{metrics['risks_count']}** rủi ro riêng biệt được nêu ra\n"
        f"- **{metrics['arguments_count']}** luận điểm phản biện (arguments) được ghi nhận, gồm **{metrics['disagreements_count']}** bất đồng cụ thể\n"
        f"- **{metrics['alternatives_count']}** phương án thay thế (Round 6), mỗi phương án kèm tối thiểu 2 trade-off\n"
        f"- **{metrics['assumptions_challenged_count']}/{metrics['assumptions_stated_count']}** giả định bị Devil's Advocate chất vấn trực tiếp (hidden assumption)\n"
        f"- **{metrics['mind_changes_count']}** lần đổi ý được ghi nhận rõ before → after → reason (Round 7)\n"
        f"- **{metrics['premortem_findings_count']}** phát hiện pre-mortem (Round 8), phủ nhóm: {', '.join(metrics['premortem_categories_covered'])}\n"
        f"- **{metrics['accepted_count']}** quyết định được chấp nhận, **{metrics['rejected_count']}** bị từ chối, "
        f"**{metrics['unresolved_count']}** còn để bạn quyết định\n"
        f"- Devil's Advocate nêu **{metrics['devils_advocate_findings_count']}** phát hiện, phủ đủ các nhóm: "
        f"{', '.join(metrics['devils_advocate_categories_covered'])}"
    )
    a("")
    a(f"Tổng kết: {result.round10.summary}")
    a("")

    accepted = result.round10.by_status("accepted")
    a("## Quyết định được chấp nhận")
    a("")
    if not accepted:
        a("_Không có quyết định nào được chấp nhận ở lần chạy này._")
        a("")
    for item in accepted:
        a(f"### {item.topic}")
        a(f"**Quyết định:** {item.decision}")
        if item.implementation_priority:
            a(f"**Mức ưu tiên triển khai:** {item.implementation_priority}")
        a("")
        a(f"**Vì sao:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Bằng chứng:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    rejected = result.round10.by_status("rejected")
    a("## Quyết định bị từ chối")
    a("")
    if not rejected:
        a("_Không có quyết định nào bị từ chối ở lần chạy này._")
        a("")
    for item in rejected:
        a(f"### {item.topic}")
        a(f"**Vì sao bị từ chối:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Bằng chứng:**")
            for e in item.evidence:
                a(f"- {e}")
        a("")

    unresolved = result.round10.by_status("unresolved")
    a("## Chưa giải quyết - Cần bạn quyết định")
    a("")
    if not unresolved:
        a("_Không có mục nào chưa giải quyết ở lần chạy này._")
        a("")
    for item in unresolved:
        a(f"### {item.topic}")
        a(f"**Vì sao council không tự giải quyết được:** {item.rationale}")
        a("")
        if item.evidence:
            a("**Bằng chứng / các lập trường:**")
            for e in item.evidence:
                a(f"- {e}")
            a("")
        if item.dissent:
            a(f"**Ý kiến bất đồng còn lại:** {item.dissent}")
        a("")

    a("## Phương án thay thế đã cân nhắc (Round 6)")
    a("")
    for role_id, alt in result.round6.items():
        a(f"### {_name(role_id)} - {alt.primary_topic}")
        a(f"**Phương án thay thế:** {alt.alternative_option}")
        a("**Trade-off:**")
        for t in alt.trade_offs:
            a(f"- {t}")
        a(f"**Khuyến nghị:** {alt.recommendation} - {alt.rationale}")
        a("")

    a("## Luận điểm phản biện chính (Round 3 + 4 + 5)")
    a("")
    for tmap in (result.round3, result.round4):
        for reviewer_id, targets in tmap.items():
            for target_id, review in targets.items():
                if review.disagree:
                    a(f"- **{_name(reviewer_id)} vs {_name(target_id)}:** {'; '.join(review.disagree)}")
    a("")
    a("### Phát hiện của Devil's Advocate (Round 5)")
    for f in result.round5.findings:
        target = f" -> nhắm vào {_name(f.target_role)}" if f.target_role else ""
        a(f"- **[{f.category}, {f.severity}]**{target}: {f.description}")
    a("")

    a("## Những lần đổi ý (Round 7)")
    a("")
    any_change = False
    for role_id, defense in result.round7.items():
        for cd in defense.changed_decisions:
            any_change = True
            a(f"### {_name(role_id)} đổi ý về: {cd.topic}")
            a(f"- **Trước:** {cd.old_decision}")
            a(f"- **Sau:** {cd.new_decision}")
            a(f"- **Lý do:** {cd.reason}")
            a(f"- **Nguyên nhân từ:** {cd.triggered_by}")
            a("")
    if not any_change:
        a("_Không có agent nào đổi ý ở lần chạy này - đây là dấu hiệu cần xem lại chất lượng tranh luận._")
        a("")

    a("## Pre-mortem: giả sử dự án thất bại sau 6 tháng (Round 8)")
    a("")
    for role_id, finding in result.round8.items():
        a(f"### Góc nhìn {_name(role_id)} [{finding.category}, khả năng {finding.likelihood}, tác động {finding.impact}]")
        a(f"**Kịch bản thất bại:** {finding.failure_scenario}")
        a(f"**Nguyên nhân gốc rễ:** {finding.root_cause}")
        a("")

    a("## Hội tụ trước khi chốt (Round 9)")
    a("")
    conv = result.round9
    if conv.unresolved_conflicts:
        a("**Mâu thuẫn chưa giải quyết:**")
        for c in conv.unresolved_conflicts:
            a(f"- {c}")
    if conv.decision_dependencies:
        a("**Phụ thuộc giữa các quyết định:**")
        for d in conv.decision_dependencies:
            a(f"- {d}")
    a(f"**Sẵn sàng chốt đồng thuận:** {'Có' if conv.ready_for_consensus else 'Chưa'}")
    a(f"**Ghi chú tổng hợp:** {conv.synthesis_note}")
    a("")

    a("## Toàn bộ rủi ro đã nêu")
    a("")
    seen_risks: set[str] = set()
    for p in result.round2.values():
        for r in p.risks:
            key = r.strip().lower()
            if key not in seen_risks:
                seen_risks.add(key)
                a(f"- {r}")
    a("")

    a("## Khuyến nghị")
    a("")
    a(
        "Triển khai các quyết định đã chấp nhận ở trên làm nền tảng thiết kế V1, theo đúng mức ưu "
        "tiên (P0 trước, P1/P2 sau). Trước khi đầu tư thời gian phát triển, hãy tự quyết định rõ ràng "
        "cho từng mục 'Chưa giải quyết' ở trên - đó là các câu hỏi kinh doanh/chính sách mà council "
        "đã xác nhận đúng là ngoài thẩm quyền tự quyết của mình."
    )
    a("")
    a("---")
    a(
        f"*Metrics: {metrics['duration_seconds']}s, {metrics['call_count']} lượt gọi agent, "
        f"{metrics['round_count']} vòng, {metrics['total_structured_items_count']} hạng mục phân "
        f"tích có cấu trúc (trung bình {metrics['avg_items_per_round']}/vòng). Xem metrics.json để biết chi tiết.*"
    )

    return "\n".join(lines) + "\n"


def render_solo_report(*, run_id: str, brief_text: str, result: SoloRunResult, metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    d = result.design

    a(f"# Solo Designer Report ({run_id})")
    a("")
    a("> Single-agent baseline, no cross-review or debate. Generated for A/B comparison")
    a("> against the council pipeline - see the comparison report to evaluate what")
    a("> multi-agent debate added. **You are the final decision-maker.**")
    a("")
    a("## Summary")
    a("")
    a(d.summary)
    a("")
    a("## Requirements")
    for r in d.requirements:
        a(f"- {r}")
    a("")
    a("## Decisions")
    for dec in d.decisions:
        a(f"- {dec}")
    a("")
    a("## Edge Cases")
    for e in d.edge_cases:
        a(f"- {e}")
    a("")
    a("## Risks")
    for r in d.risks:
        a(f"- {r}")
    a("")
    a("## Open Questions")
    for q in d.open_questions:
        a(f"- {q}")
    a("")
    a("---")
    a(f"*Metrics: {metrics['duration_seconds']}s wall time, {metrics['call_count']} agent call. See metrics.json.*")
    return "\n".join(lines) + "\n"
