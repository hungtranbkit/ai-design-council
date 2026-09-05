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
Priority = Literal["MUST", "SHOULD", "COULD"]
PreMortemCategory = Literal["abuse_case", "operational", "technical", "business"]
Impact = Literal["low", "medium", "high"]

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
    # Additive, optional (backward compatible with every existing Proposal
    # artifact on disk, 5-round or 10-round): MUST/SHOULD/COULD tagging per
    # requirement text, and explicit "I don't know, don't guess" flags.
    priority_tags: dict[str, Priority] = Field(default_factory=dict)
    uncertainty: list[str] = Field(default_factory=list)

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
    # Additive, optional: R10's implementation-priority call for accepted items.
    implementation_priority: Literal["P0", "P1", "P2"] | None = None

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


class ProblemUnderstanding(BaseModel):
    """Round 1 of the 10-round pipeline: understand the problem and state
    independent assumptions BEFORE proposing any solution - a genuinely new
    round, not a renumbering of the old Round 1 (which already jumped
    straight to proposing). Isolation applies here exactly as it does to the
    old Round 1: no agent sees any other agent's output."""

    role: str
    round: int = 1
    interpretation: str  # this role's own reading of what the brief is actually asking for
    assumptions: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)  # explicit "unknown, not guessing" flags

    @field_validator("assumptions")
    @classmethod
    def _assumptions_required(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Round 1 requires at least one explicit assumption - do not skip straight to a solution")
        return v


class AlternativeProposal(BaseModel):
    """Round 6: every role must produce at least a B option (and ideally a C)
    for one of their own key decisions, with >=2 concrete trade-offs -
    directly enforced by schema validation, not just prompt instruction."""

    role: str
    round: int = 6
    primary_topic: str  # which Round 2 decision this alternative is against
    alternative_option: str
    trade_offs: list[str] = Field(default_factory=list)
    recommendation: Literal["prefer_primary", "prefer_alternative", "depends"] = "depends"
    rationale: str

    @field_validator("trade_offs")
    @classmethod
    def _min_two_trade_offs(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("an alternative must name at least 2 concrete trade-offs, not just 'it's simpler'")
        return v


class PreMortemFinding(BaseModel):
    """Round 8: assume the project failed ~6 months in - work backwards to a
    concrete root cause, from this role's own domain lens."""

    role: str
    round: int = 8
    failure_scenario: str
    root_cause: str
    category: PreMortemCategory
    likelihood: Impact = "medium"
    impact: Impact = "medium"

    @field_validator("failure_scenario", "root_cause")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("pre-mortem finding must state a concrete scenario and root cause, not leave it blank")
        return v


class ConvergenceReport(BaseModel):
    """Round 9: a dependency/conflict check before the final consensus round -
    not a decision itself, just an honest inventory of what's still unresolved
    or contradictory across the transcript so far."""

    round: int = 9
    unresolved_conflicts: list[str] = Field(default_factory=list)
    decision_dependencies: list[str] = Field(default_factory=list)  # e.g. "quyết định X phụ thuộc vào quyết định Y"
    remaining_contradictions: list[str] = Field(default_factory=list)
    ready_for_consensus: bool = True
    synthesis_note: str = ""


class SoloDesign(BaseModel):
    """Single-agent (no debate) baseline used by the A/B harness."""

    role: str = "solo_designer"
    summary: str
    requirements: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
