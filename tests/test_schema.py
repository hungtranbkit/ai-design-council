"""Schema validation tests for the structured round contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from council.pipeline.schemas import (
    CrossReview,
    Defense,
    DevilsAdvocateFinding,
    DevilsAdvocateReport,
    Proposal,
)


def test_proposal_rejects_empty_requirements():
    with pytest.raises(ValidationError):
        Proposal(role="architect", summary="x", requirements=[], decisions=["d"])


def test_proposal_rejects_empty_decisions():
    with pytest.raises(ValidationError):
        Proposal(role="architect", summary="x", requirements=["r"], decisions=[])


def test_proposal_accepts_minimal_valid_data():
    p = Proposal(role="architect", summary="x", requirements=["r"], decisions=["d"])
    assert p.round == 1


def test_cross_review_rejects_pure_agreement():
    with pytest.raises(ValidationError):
        CrossReview(
            reviewer_role="qa_security",
            target_role="architect",
            agree=["everything is fine"],
            disagree=[],
            missing_requirements=[],
            risks=[],
            proposed_changes=[],
        )


def test_cross_review_accepts_when_it_takes_a_position():
    review = CrossReview(
        reviewer_role="qa_security",
        target_role="architect",
        agree=[],
        disagree=["missing auth on the realtime channel"],
        missing_requirements=[],
        risks=[],
        proposed_changes=[],
    )
    assert review.disagree


def test_devils_advocate_finding_rejects_rubber_stamp_phrases():
    for phrase in ["Looks good to me", "LGTM", "No issues found", "no concerns here"]:
        with pytest.raises(ValidationError):
            DevilsAdvocateFinding(category="security", description=phrase)


def test_devils_advocate_report_requires_minimum_findings():
    findings = [
        DevilsAdvocateFinding(category="security", description="concrete security gap in X")
        for _ in range(4)
    ]
    with pytest.raises(ValidationError):
        DevilsAdvocateReport(findings=findings)


def test_devils_advocate_report_accepts_five_or_more_findings():
    categories = ["hidden_assumption", "unnecessary_complexity", "missing_business_case", "scalability", "security"]
    findings = [DevilsAdvocateFinding(category=c, description=f"concrete issue about {c}") for c in categories]
    report = DevilsAdvocateReport(findings=findings)
    assert len(report.findings) == 5
    assert report.missing_categories() == {"ux", "operations"}


def test_defense_requires_final_decisions():
    with pytest.raises(ValidationError):
        Defense(role="architect", final_decisions=[])


def test_defense_accepts_minimal_valid_data():
    defense = Defense(role="architect", final_decisions=["keep the service split as-is"])
    assert defense.changed_decisions == []
