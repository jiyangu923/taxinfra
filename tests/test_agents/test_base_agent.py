"""Tests for the base agent framework."""

import pytest

from taxinfra.agents.base import AgentContext, AgentResult, AgentStatus, TaxAgent
from taxinfra.core.audit_trail import AuditTrail
from taxinfra.core.explainability import DecisionLog
from taxinfra.core.traceability import TraceChain


class SimpleTestAgent(TaxAgent):
    agent_name = "test_agent"
    agent_description = "A simple test agent"

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.COMPLETED,
            started_at=__import__("datetime").datetime.utcnow(),
            summary="Test completed",
            outputs={"result": "success"},
        )


class FailingTestAgent(TaxAgent):
    agent_name = "failing_agent"
    agent_description = "An agent that always fails"

    async def execute(self, context: AgentContext) -> AgentResult:
        raise ValueError("Something went wrong")


@pytest.mark.asyncio
async def test_agent_run_success():
    trail = AuditTrail()
    decision_log = DecisionLog()
    trace_chain = TraceChain()

    agent = SimpleTestAgent(trail, decision_log, trace_chain)
    context = AgentContext(triggered_by="test")

    result = await agent.run(context)

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "Test completed"
    assert agent.status == AgentStatus.COMPLETED

    # Verify audit trail was logged
    entries = trail.get_entries(agent_name="test_agent")
    assert len(entries) == 2  # INVOKED + COMPLETED


@pytest.mark.asyncio
async def test_agent_run_failure():
    trail = AuditTrail()
    decision_log = DecisionLog()
    trace_chain = TraceChain()

    agent = FailingTestAgent(trail, decision_log, trace_chain)
    context = AgentContext(triggered_by="test")

    result = await agent.run(context)

    assert result.status == AgentStatus.FAILED
    assert "Something went wrong" in result.errors[0]
    assert agent.status == AgentStatus.FAILED

    # Failure should still be logged
    entries = trail.get_entries(agent_name="failing_agent")
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_agent_memory():
    trail = AuditTrail()
    agent = SimpleTestAgent(trail, DecisionLog(), TraceChain())

    agent.remember("last_filing", {"id": "f1", "status": "submitted"})
    agent.remember("last_filing", {"id": "f2", "status": "draft"})

    recalled = agent.recall("last_filing")
    assert len(recalled) == 2

    missing = agent.recall("nonexistent")
    assert len(missing) == 0
