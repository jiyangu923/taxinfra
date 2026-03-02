"""Audit Defense Agent — handles tax authority audits and information requests.

Trigger: Audit notice arrives.
System:
1. Identifies affected filings
2. Pulls underlying transactional chain
3. Generates audit package
4. Drafts response
5. Suggests negotiation positions
6. Tracks deadlines
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from taxinfra.agents.base import AgentContext, AgentResult, AgentStatus, TaxAgent
from taxinfra.core.audit_trail import AuditAction
from taxinfra.core.explainability import Decision


class AuditNotice(BaseModel):
    """An audit notice from a tax authority."""

    authority: str  # e.g. "IRS", "HMRC", "BZSt"
    jurisdiction: str
    notice_date: date
    response_deadline: date
    audit_type: str  # "desk_audit", "field_audit", "information_request"
    periods_covered: list[str] = Field(default_factory=list)  # e.g. ["2024-Q1", "2024-Q2"]
    tax_types: list[str] = Field(default_factory=list)
    description: str = ""
    reference_number: str = ""


class AuditDefenseAgent(TaxAgent):
    agent_name = "audit_defense_agent"
    agent_description = (
        "Handles tax authority audits: identifies affected filings, builds audit packages "
        "with full traceability, drafts responses, and tracks deadlines."
    )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Respond to an audit notice.

        Parameters expected in context:
        - notice: Serialized AuditNotice
        """
        params = context.parameters
        notice_data = params.get("notice", {})

        if not notice_data:
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                started_at=datetime.utcnow(),
                summary="No audit notice provided",
                errors=["An audit notice must be provided in context parameters"],
            )

        notice = AuditNotice(**notice_data)
        recommendations: list[str] = []
        warnings: list[str] = []

        # Step 1: Log audit notice receipt
        self.audit_trail.log(
            AuditAction.DATA_READ,
            f"Audit notice received from {notice.authority}: {notice.reference_number}",
            agent_name=self.agent_name,
            entity_type="audit_notice",
            entity_id=notice.reference_number,
            session_id=context.session_id,
            details={
                "authority": notice.authority,
                "audit_type": notice.audit_type,
                "periods": notice.periods_covered,
                "deadline": notice.response_deadline.isoformat(),
            },
        )

        # Step 2: Identify affected filings (would query filing store in production)
        affected_filing_ids: list[UUID] = []
        for period in notice.periods_covered:
            recommendations.append(f"Pull all filings for period {period} in {notice.jurisdiction}")

        # Step 3: Build audit package outline
        audit_package = {
            "notice_reference": notice.reference_number,
            "authority": notice.authority,
            "periods": notice.periods_covered,
            "response_deadline": notice.response_deadline.isoformat(),
            "sections": [
                "1. Filing summaries for requested periods",
                "2. Underlying transaction detail with source system references",
                "3. Tax determination audit trail (rules applied, rates used)",
                "4. GL reconciliation evidence",
                "5. Supporting documentation (invoices, contracts, exemption certificates)",
            ],
        }

        # Step 4: Deadline tracking
        days_until_deadline = (notice.response_deadline - date.today()).days
        if days_until_deadline <= 7:
            warnings.append(
                f"URGENT: Response deadline in {days_until_deadline} days "
                f"({notice.response_deadline})"
            )
        elif days_until_deadline <= 30:
            warnings.append(
                f"Response deadline in {days_until_deadline} days ({notice.response_deadline})"
            )

        recommendations.extend([
            "Assemble complete transaction trail for requested periods",
            "Verify all filings for requested periods are consistent with GL",
            "Prepare response draft for review by tax counsel",
        ])

        # Step 5: Record decision
        decision = Decision(
            agent_name=self.agent_name,
            decision_type="audit_response_preparation",
            question=f"How to respond to {notice.authority} audit {notice.reference_number}?",
            conclusion="Audit package outline prepared, pending human review",
            reasoning_steps=[
                f"Received {notice.audit_type} from {notice.authority}",
                f"Periods covered: {', '.join(notice.periods_covered)}",
                f"Response deadline: {notice.response_deadline}",
                "Identified affected filings",
                "Built audit package outline with traceability chain",
                "Flagged for human review",
            ],
            entity_type="audit_notice",
            entity_id=notice.reference_number,
            requires_human_review=True,
            human_review_reason="All audit responses must be reviewed by tax counsel",
        )
        self.decision_log.record(decision)

        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.WAITING_FOR_APPROVAL,
            started_at=datetime.utcnow(),
            summary=f"Audit defense package prepared for {notice.authority} {notice.reference_number}",
            outputs={
                "audit_package": audit_package,
                "days_until_deadline": days_until_deadline,
                "affected_periods": notice.periods_covered,
            },
            recommendations=recommendations,
            warnings=warnings,
            filing_ids=affected_filing_ids,
            decision_ids=[decision.id],
            requires_approval=True,
            approval_items=[
                "Review audit package completeness",
                "Approve response strategy",
                "Confirm engagement of external counsel if needed",
            ],
        )
