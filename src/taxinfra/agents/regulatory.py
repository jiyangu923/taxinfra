"""Regulatory Monitoring Agent — tracks regulation changes and assesses impact.

Continuously monitors for:
- New tax legislation
- Rate changes
- Filing requirement changes
- E-invoicing mandates
- Threshold changes
- Treaty updates

Produces impact assessments and configuration recommendations.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from taxinfra.agents.base import AgentContext, AgentResult, AgentStatus, TaxAgent
from taxinfra.core.explainability import Decision, RuleReference


class RegulatoryChangeType(StrEnum):
    RATE_CHANGE = "rate_change"
    NEW_TAX = "new_tax"
    THRESHOLD_CHANGE = "threshold_change"
    FILING_CHANGE = "filing_change"
    E_INVOICING_MANDATE = "e_invoicing_mandate"
    EXEMPTION_CHANGE = "exemption_change"
    TREATY_UPDATE = "treaty_update"
    LEGISLATION = "legislation"


class RegulatoryChange(BaseModel):
    """A detected regulatory change."""

    jurisdiction: str
    change_type: RegulatoryChangeType
    title: str
    description: str
    effective_date: str
    source_url: str = ""
    impact_level: str = "medium"  # low, medium, high, critical


class RegulatoryMonitoringAgent(TaxAgent):
    agent_name = "regulatory_monitoring_agent"
    agent_description = (
        "Monitors regulatory changes across jurisdictions and assesses impact on "
        "entity tax positions, filing requirements, and system configuration."
    )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Check for and assess regulatory changes.

        Parameters expected in context:
        - changes: List of detected regulatory changes (serialized)
        - jurisdictions: Jurisdictions to monitor
        """
        params = context.parameters
        changes_data = params.get("changes", [])
        jurisdictions = context.jurisdictions

        changes = [RegulatoryChange(**c) for c in changes_data]
        recommendations: list[str] = []
        warnings: list[str] = []
        decision_ids = []

        if not changes and not jurisdictions:
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.COMPLETED,
                started_at=datetime.utcnow(),
                summary="No regulatory changes to assess",
            )

        for change in changes:
            # Assess impact
            if change.impact_level in ("high", "critical"):
                warnings.append(
                    f"[{change.impact_level.upper()}] {change.jurisdiction}: {change.title} "
                    f"(effective {change.effective_date})"
                )

            # Generate recommendations based on change type
            if change.change_type == RegulatoryChangeType.RATE_CHANGE:
                recommendations.append(
                    f"Update tax rate configuration for {change.jurisdiction}: {change.title}"
                )
            elif change.change_type == RegulatoryChangeType.E_INVOICING_MANDATE:
                recommendations.append(
                    f"Implement e-invoicing compliance for {change.jurisdiction}: {change.title}"
                )
            elif change.change_type == RegulatoryChangeType.THRESHOLD_CHANGE:
                recommendations.append(
                    f"Review registration threshold for {change.jurisdiction}: {change.title}"
                )
            else:
                recommendations.append(
                    f"Review impact of {change.change_type} in {change.jurisdiction}: {change.title}"
                )

            # Record decision
            decision = Decision(
                agent_name=self.agent_name,
                decision_type="regulatory_impact_assessment",
                question=f"What is the impact of: {change.title}?",
                conclusion=f"Impact level: {change.impact_level}. Action required.",
                reasoning_steps=[
                    f"Change type: {change.change_type}",
                    f"Jurisdiction: {change.jurisdiction}",
                    f"Effective date: {change.effective_date}",
                    f"Assessed impact level: {change.impact_level}",
                ],
                rules_applied=[
                    RuleReference(
                        rule_id=f"reg_change_{change.jurisdiction}",
                        jurisdiction=change.jurisdiction,
                        regulation_name=change.title,
                        summary=change.description,
                        url=change.source_url,
                        effective_date=change.effective_date,
                    )
                ],
                requires_human_review=change.impact_level in ("high", "critical"),
                human_review_reason=(
                    f"High-impact regulatory change in {change.jurisdiction}"
                    if change.impact_level in ("high", "critical")
                    else ""
                ),
            )
            self.decision_log.record(decision)
            decision_ids.append(decision.id)

        has_critical = any(c.impact_level == "critical" for c in changes)

        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.WAITING_FOR_APPROVAL if has_critical else AgentStatus.COMPLETED,
            started_at=datetime.utcnow(),
            summary=f"Assessed {len(changes)} regulatory change(s) across {len(set(c.jurisdiction for c in changes))} jurisdiction(s)",
            outputs={
                "changes_assessed": len(changes),
                "high_impact_count": sum(
                    1 for c in changes if c.impact_level in ("high", "critical")
                ),
            },
            recommendations=recommendations,
            warnings=warnings,
            decision_ids=decision_ids,
            requires_approval=has_critical,
            approval_items=(
                ["Review and approve response to critical regulatory changes"]
                if has_critical
                else []
            ),
        )
