"""Agent API endpoints — invoke and manage tax agents."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taxinfra.agents.base import AgentContext, AgentResult
from taxinfra.agents.planning import PlanningAgent
from taxinfra.agents.compliance import ComplianceAgent
from taxinfra.agents.audit_defense import AuditDefenseAgent
from taxinfra.agents.regulatory import RegulatoryMonitoringAgent

router = APIRouter()


class AgentInvokeRequest(BaseModel):
    """Request to invoke a tax agent."""

    agent_type: str  # planning, compliance, audit_defense, regulatory
    triggered_by: str = ""
    entity_ids: list[UUID] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    require_human_approval: bool = True


AGENT_MAP = {
    "planning": PlanningAgent,
    "compliance": ComplianceAgent,
    "audit_defense": AuditDefenseAgent,
    "regulatory": RegulatoryMonitoringAgent,
}


@router.post("/invoke")
async def invoke_agent(body: AgentInvokeRequest, request: Request) -> AgentResult:
    """Invoke a tax agent."""
    agent_class = AGENT_MAP.get(body.agent_type)
    if not agent_class:
        return AgentResult(
            agent_name=body.agent_type,
            status="failed",
            started_at=__import__("datetime").datetime.utcnow(),
            summary=f"Unknown agent type: {body.agent_type}",
            errors=[f"Valid types: {', '.join(AGENT_MAP.keys())}"],
        )

    agent = agent_class(
        audit_trail=request.app.state.audit_trail,
        decision_log=request.app.state.decision_log,
        trace_chain=request.app.state.trace_chain,
    )

    context = AgentContext(
        triggered_by=body.triggered_by,
        entity_ids=body.entity_ids,
        jurisdictions=body.jurisdictions,
        parameters=body.parameters,
        require_human_approval=body.require_human_approval,
    )

    return await agent.run(context)


@router.get("/types")
async def list_agent_types() -> dict:
    """List available agent types."""
    return {
        "agents": [
            {
                "type": key,
                "name": cls.agent_name,
                "description": cls.agent_description,
            }
            for key, cls in AGENT_MAP.items()
        ]
    }


@router.get("/decisions/pending")
async def get_pending_decisions(request: Request) -> dict:
    """Get all decisions pending human review."""
    pending = request.app.state.decision_log.get_pending_reviews()
    return {
        "count": len(pending),
        "decisions": [d.model_dump() for d in pending],
    }


@router.get("/audit-trail")
async def get_audit_trail(
    request: Request,
    entity_type: str = "",
    entity_id: str = "",
    agent_name: str = "",
) -> dict:
    """Query the audit trail."""
    entries = request.app.state.audit_trail.get_entries(
        entity_type=entity_type,
        entity_id=entity_id,
        agent_name=agent_name,
    )
    return {
        "count": len(entries),
        "entries": [e.model_dump() for e in entries],
    }
