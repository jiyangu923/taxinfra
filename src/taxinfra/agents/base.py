"""Base agent — the foundation for all specialized tax agents.

Every agent has:
- Domain skill library
- Country modules
- API connectors
- Memory
- Audit trail logging
- Explainability
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from taxinfra.core.audit_trail import AuditAction, AuditTrail
from taxinfra.core.explainability import DecisionLog
from taxinfra.core.traceability import TraceChain

logger = logging.getLogger(__name__)


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentContext(BaseModel):
    """Context passed to an agent when invoked."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str = ""
    triggered_by: str = ""  # What triggered this agent
    entity_ids: list[UUID] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    require_human_approval: bool = True


class AgentResult(BaseModel):
    """Result returned by an agent after execution."""

    agent_name: str
    status: AgentStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)

    # Outputs
    summary: str = ""
    outputs: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # What was generated
    filing_ids: list[UUID] = Field(default_factory=list)
    decision_ids: list[UUID] = Field(default_factory=list)

    # Human review
    requires_approval: bool = False
    approval_items: list[str] = Field(default_factory=list)


class TaxAgent(ABC):
    """Base class for all tax operations agents.

    Provides shared infrastructure: audit trail logging, decision recording,
    traceability, and memory. Subclasses implement domain-specific logic.
    """

    agent_name: str = "base_agent"
    agent_description: str = ""

    def __init__(
        self,
        audit_trail: AuditTrail,
        decision_log: DecisionLog,
        trace_chain: TraceChain,
    ) -> None:
        self.audit_trail = audit_trail
        self.decision_log = decision_log
        self.trace_chain = trace_chain
        self.status = AgentStatus.IDLE
        self._memory: list[dict] = []

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent with full audit trail and error handling."""
        started_at = datetime.utcnow()
        self.status = AgentStatus.RUNNING

        # Log invocation
        self.audit_trail.log(
            AuditAction.AGENT_INVOKED,
            f"Agent '{self.agent_name}' invoked",
            agent_name=self.agent_name,
            session_id=context.session_id,
            correlation_id=context.correlation_id,
            details={
                "triggered_by": context.triggered_by,
                "parameters": context.parameters,
            },
        )

        try:
            result = await self.execute(context)
            result.started_at = started_at
            result.completed_at = datetime.utcnow()
            self.status = (
                AgentStatus.WAITING_FOR_APPROVAL
                if result.requires_approval
                else AgentStatus.COMPLETED
            )

            # Log completion
            self.audit_trail.log(
                AuditAction.AGENT_COMPLETED,
                f"Agent '{self.agent_name}' completed: {result.summary}",
                agent_name=self.agent_name,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
                details={
                    "status": result.status,
                    "warnings": result.warnings,
                    "requires_approval": result.requires_approval,
                },
            )

            return result

        except Exception as e:
            self.status = AgentStatus.FAILED
            logger.exception("Agent '%s' failed", self.agent_name)

            self.audit_trail.log(
                AuditAction.AGENT_COMPLETED,
                f"Agent '{self.agent_name}' failed: {e}",
                agent_name=self.agent_name,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
                details={"error": str(e)},
            )

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                started_at=started_at,
                summary=f"Agent failed: {e}",
                errors=[str(e)],
            )

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Implement agent-specific logic. Override in subclasses."""
        ...

    def remember(self, key: str, value: object) -> None:
        """Store something in agent memory for later retrieval."""
        self._memory.append({
            "key": key,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def recall(self, key: str) -> list[dict]:
        """Recall items from memory by key."""
        return [m for m in self._memory if m["key"] == key]
