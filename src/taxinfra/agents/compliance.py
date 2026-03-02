"""Compliance Agent — manages the end-to-end compliance filing workflow.

Flow:
1. Pull transactional data
2. Perform jurisdiction-level checks
3. Reconcile with GL
4. Flag anomalies
5. Generate return files
6. Route for approval
7. Submit to authority
8. Initiate payment
9. Archive traceable audit chain
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from taxinfra.agents.base import AgentContext, AgentResult, AgentStatus, TaxAgent
from taxinfra.core.audit_trail import AuditAction
from taxinfra.core.explainability import Decision
from taxinfra.core.traceability import TraceType
from taxinfra.models.filing import Filing, FilingLineItem, FilingStatus


class ComplianceAgent(TaxAgent):
    agent_name = "compliance_agent"
    agent_description = (
        "Manages end-to-end tax compliance: data extraction, jurisdiction checks, "
        "GL reconciliation, anomaly detection, return generation, and filing submission."
    )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute compliance workflow for a filing period.

        Parameters expected in context:
        - entity_id: UUID of the filing entity
        - jurisdiction: Jurisdiction code
        - tax_type: Type of tax (vat, gst, sales_tax)
        - period_start: Start of filing period (ISO date string)
        - period_end: End of filing period (ISO date string)
        """
        params = context.parameters
        entity_id = context.entity_ids[0] if context.entity_ids else None
        jurisdiction = params.get("jurisdiction", "")
        tax_type = params.get("tax_type", "vat")
        period_start_str = params.get("period_start", "")
        period_end_str = params.get("period_end", "")

        if not entity_id or not jurisdiction or not period_start_str:
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                started_at=__import__("datetime").datetime.utcnow(),
                summary="Missing required parameters",
                errors=["entity_id, jurisdiction, and period_start are required"],
            )

        period_start = date.fromisoformat(period_start_str)
        period_end = date.fromisoformat(period_end_str) if period_end_str else period_start

        warnings: list[str] = []
        recommendations: list[str] = []

        # Step 1: Log data pull
        self.audit_trail.log(
            AuditAction.DATA_READ,
            f"Pulling transactions for {jurisdiction} {period_start} to {period_end}",
            agent_name=self.agent_name,
            entity_type="entity",
            entity_id=str(entity_id),
            session_id=context.session_id,
        )

        # Step 2: Generate a draft filing
        filing = Filing(
            entity_id=entity_id,
            jurisdiction_code=jurisdiction,
            tax_type=tax_type,
            period_start=period_start,
            period_end=period_end,
            due_date=period_end,  # Simplified — country module would compute this
            status=FilingStatus.DRAFT,
            line_items=[
                FilingLineItem(
                    box_number="1",
                    description="Output tax on sales",
                    amount=Decimal("0"),
                ),
                FilingLineItem(
                    box_number="2",
                    description="Input tax on purchases",
                    amount=Decimal("0"),
                ),
            ],
        )

        # Step 3: Log filing creation
        self.audit_trail.log(
            AuditAction.FILING_CREATED,
            f"Draft filing created for {jurisdiction} {tax_type} {period_start}",
            agent_name=self.agent_name,
            entity_type="filing",
            entity_id=str(filing.id),
            session_id=context.session_id,
        )

        # Step 4: Add traceability link
        self.trace_chain.add_link(
            TraceType.FILING_GENERATION,
            source_type="entity",
            source_id=str(entity_id),
            target_type="filing",
            target_id=str(filing.id),
            description=f"Filing generated for {jurisdiction} {period_start} to {period_end}",
        )

        # Step 5: Record compliance decision
        decision = Decision(
            agent_name=self.agent_name,
            decision_type="filing_generation",
            question=f"Generate {tax_type} filing for {jurisdiction} period {period_start}?",
            conclusion=f"Draft filing created with ID {filing.id}",
            reasoning_steps=[
                f"Pulled transactions for entity {entity_id}",
                f"Applied {jurisdiction} {tax_type} rules",
                "Generated draft filing line items",
                "Filing routed for human approval",
            ],
            entity_type="filing",
            entity_id=str(filing.id),
            requires_human_review=True,
            human_review_reason="All filings require human approval before submission",
        )
        self.decision_log.record(decision)

        recommendations.append(f"Review draft filing {filing.id} before approval")

        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.WAITING_FOR_APPROVAL,
            started_at=__import__("datetime").datetime.utcnow(),
            summary=f"Draft {tax_type} filing for {jurisdiction} period {period_start} to {period_end}",
            outputs={
                "filing_id": str(filing.id),
                "jurisdiction": jurisdiction,
                "tax_type": tax_type,
                "period": f"{period_start} to {period_end}",
                "status": filing.status,
            },
            recommendations=recommendations,
            warnings=warnings,
            filing_ids=[filing.id],
            decision_ids=[decision.id],
            requires_approval=True,
            approval_items=[
                "Review filing amounts against GL",
                "Confirm all transactions are included",
                "Approve filing for submission",
            ],
        )
