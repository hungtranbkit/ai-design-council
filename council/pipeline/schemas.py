"""Structured schemas exchanged between agents across the 5 debate rounds.

Every round's output is a pydantic model. This gives us:
  - real schema validation (round outputs that don't match are rejected)
  - a stable contract that a real LLM provider must also satisfy
  - easy serialization to the run's artifact files (model_dump_json)
"""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal[
    "hidden_assumption",
    "unnecessary_complexity",
    "missing_business_case",
    "scalability",
    "ux",
    "security",
    "operations",
]

Status = Literal["accepted", "rejected", "unresolved"]

# Phrases that would signal a Devil's Advocate round degenerating into rubber-stamping.
# Round 3 output is rejected if any finding description reduces to one of these.
FORBIDDEN_RUBBER_STAMP_PHRASES = (
    "looks good",
    "lgtm",
    "no issues",
    "no concerns",
    "nothing to add",
    "all good",
)


class Proposal(BaseModel):
    """Round 1 (Independent) and the base shape carried into later rounds."""

    role: str
    round: int = 1
    summary: str
    requirements: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("requirements", "decisions")
    @classmethod
    def _non_empty_core_lists(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("proposal must contain at least one item (empty list not allowed)")
        return v


class CrossReview(BaseModel):
    """Round 2 (Cross Review): one reviewer's structured critique of one target's proposal."""

    reviewer_role: str
    target_role: str
    round: int = 2
    agree: list[str] = Field(default_factory=list)
    disagree: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reviews_must_take_a_position(self) -> "CrossReview":
        # A cross review that only agrees, with nothing disagreed, missing, or
        # proposed, is not a real critique - it is agreement theater.
        if not (self.disagree or self.missing_requirements or self.proposed_changes):
            raise ValueError(
                "cross review must contain at least one of disagree/missing_requirements/"
                "proposed_changes - pure agreement is not a valid structured review"
            )
        return self


class DevilsAdvocateFinding(BaseModel):
    category: Category
    description: str
    target_role: str | None = None
    severity: Literal["low", "medium", "high"] = "medium"

    @field_validator("description")
    @classmethod
    def _reject_rubber_stamp(cls, v: str) -> str:
        low = v.strip().lower()
        for phrase in FORBIDDEN_RUBBER_STAMP_PHRASES:
            if phrase in low:
                raise ValueError(
                    f"Devil's Advocate finding may not be a rubber stamp ('{phrase}' found). "
                    "Round 3 must surface a real, specific issue."
                )
        return v


class DevilsAdvocateReport(BaseModel):
    """Round 3 (Devil's Advocate): mandatory critique across all required categories."""

    round: int = 3
    findings: list[DevilsAdvocateFinding] = Field(default_factory=list)

    REQUIRED_CATEGORIES: ClassVar[set[str]] = {
        "hidden_assumption",
        "unnecessary_complexity",
        "missing_business_case",
        "scalability",
        "ux",
        "security",
        "operations",
    }

    @field_validator("findings")
    @classmethod
    def _min_findings(cls, v: list[DevilsAdvocateFinding]) -> list[DevilsAdvocateFinding]:
        if len(v) < 5:
            raise ValueError("Devil's Advocate must raise at least 5 distinct findings")
        return v

    def covered_categories(self) -> set[str]:
        return {f.category for f in self.findings}

    def missing_categories(self) -> set[str]:
        return self.REQUIRED_CATEGORIES - self.covered_categories()


class ChangedDecision(BaseModel):
    """One recorded mind change: an agent revising a prior decision under critique."""

    topic: str
    old_decision: str
    new_decision: str
    reason: str
    triggered_by: str  # which role/round surfaced the critique that caused this


class DefenseResponse(BaseModel):
    critique_source: str  # e.g. "qa_security (round2)" or "devils_advocate (round3)"
    critique_summary: str
    stance: Literal["defend", "revise", "partially_accept"]
    rationale: str


class Defense(BaseModel):
    """Round 4 (Defense/Revision): an agent's response to the critiques it received."""

    role: str
    round: int = 4
    responses: list[DefenseResponse] = Field(default_factory=list)
    changed_decisions: list[ChangedDecision] = Field(default_factory=list)
    final_decisions: list[str] = Field(default_factory=list)

    @field_validator("final_decisions")
    @classmethod
    def _must_have_final_decisions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("defense must restate final decisions, even if unchanged")
        return v


class ConsensusItem(BaseModel):
    topic: str
    status: Status
    decision: str | None = None
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    dissent: str | None = None

    @field_validator("rationale")
    @classmethod
    def _rationale_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("consensus item must explain WHY, not just state a verdict")
        return v


class ConsensusReport(BaseModel):
    """Round 5 (Consensus/Moderator): final synthesis, not a majority vote."""

    round: int = 5
    items: list[ConsensusItem] = Field(default_factory=list)
    summary: str = ""

    def by_status(self, status: Status) -> list[ConsensusItem]:
        return [i for i in self.items if i.status == status]


class SoloDesign(BaseModel):
    """Single-agent (no debate) baseline used by the A/B harness."""

    role: str = "solo_designer"
    summary: str
    requirements: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
