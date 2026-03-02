"""Explainability — every AI decision must show its reasoning.

No hallucination tolerance in tax. Every decision the system makes must be
traceable to specific rules, regulations, data inputs, and reasoning chains.
This module provides the structure for that.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RuleReference(BaseModel):
    """A reference to a specific tax rule or regulation."""

    rule_id: str  # Internal rule identifier
    jurisdiction: str  # e.g. "US", "DE", "GB"
    regulation_name: str  # e.g. "VAT Act 2024, Section 30"
    section: str = ""
    url: str = ""  # Link to official source
    effective_date: str = ""
    summary: str = ""


class Decision(BaseModel):
    """A single explainable decision made by the system.

    This is the atomic unit of explainability. Every tax determination,
    classification, rate selection, or recommendation generates a Decision
    that captures why and how it was reached.
    """

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_name: str
    decision_type: str  # e.g. "tax_rate_determination", "exemption_check", "classification"

    # What was decided
    question: str  # The question being answered
    conclusion: str  # The determination/answer
    confidence: float = 1.0  # 0.0 to 1.0

    # Why — the reasoning chain
    reasoning_steps: list[str] = Field(default_factory=list)
    rules_applied: list[RuleReference] = Field(default_factory=list)
    data_inputs: dict = Field(default_factory=dict)  # Key data points used

    # What entity this applies to
    entity_type: str = ""  # "transaction", "filing", etc.
    entity_id: str = ""

    # Human review
    requires_human_review: bool = False
    human_review_reason: str = ""
    reviewed_by: str = ""
    review_outcome: str = ""  # "approved", "rejected", "modified"


class DecisionLog:
    """Log of all decisions made by agents, queryable for audit defense.

    This provides the "show your work" capability that is essential for
    tax authority audits and internal governance.
    """

    def __init__(self) -> None:
        self._decisions: list[Decision] = []

    def record(self, decision: Decision) -> Decision:
        """Record a decision."""
        self._decisions.append(decision)
        return decision

    def get_decisions(
        self,
        *,
        agent_name: str = "",
        decision_type: str = "",
        entity_type: str = "",
        entity_id: str = "",
        requires_review: bool | None = None,
    ) -> list[Decision]:
        """Query decisions with filters."""
        results = self._decisions
        if agent_name:
            results = [d for d in results if d.agent_name == agent_name]
        if decision_type:
            results = [d for d in results if d.decision_type == decision_type]
        if entity_type:
            results = [d for d in results if d.entity_type == entity_type]
        if entity_id:
            results = [d for d in results if d.entity_id == entity_id]
        if requires_review is not None:
            results = [d for d in results if d.requires_human_review == requires_review]
        return results

    def get_decisions_for_entity(self, entity_type: str, entity_id: str) -> list[Decision]:
        """Get all decisions that affected a specific entity."""
        return self.get_decisions(entity_type=entity_type, entity_id=entity_id)

    def get_pending_reviews(self) -> list[Decision]:
        """Get all decisions that still need human review."""
        return [
            d
            for d in self._decisions
            if d.requires_human_review and d.review_outcome == ""
        ]

    @property
    def decisions(self) -> list[Decision]:
        return list(self._decisions)
