"""Tests for the audit trail."""

from taxinfra.core.audit_trail import AuditAction, AuditTrail


def test_audit_trail_log_and_query():
    trail = AuditTrail()

    entry = trail.log(
        AuditAction.AGENT_INVOKED,
        "Planning agent invoked",
        agent_name="planning_agent",
        entity_type="entity",
        entity_id="123",
        session_id="session-1",
    )

    assert entry.action == AuditAction.AGENT_INVOKED
    assert entry.agent_name == "planning_agent"
    assert len(trail.entries) == 1


def test_audit_trail_filter_by_entity():
    trail = AuditTrail()

    trail.log(AuditAction.FILING_CREATED, "Filing A", entity_type="filing", entity_id="f1")
    trail.log(AuditAction.FILING_CREATED, "Filing B", entity_type="filing", entity_id="f2")
    trail.log(AuditAction.DATA_READ, "Read data", entity_type="transaction", entity_id="t1")

    filings = trail.get_entries(entity_type="filing")
    assert len(filings) == 2

    specific = trail.get_entries(entity_type="filing", entity_id="f1")
    assert len(specific) == 1
    assert specific[0].description == "Filing A"


def test_audit_trail_filter_by_agent():
    trail = AuditTrail()

    trail.log(AuditAction.AGENT_INVOKED, "Agent A", agent_name="planning_agent")
    trail.log(AuditAction.AGENT_INVOKED, "Agent B", agent_name="compliance_agent")

    results = trail.get_entries(agent_name="planning_agent")
    assert len(results) == 1
    assert results[0].description == "Agent A"


def test_audit_trail_entity_history():
    trail = AuditTrail()

    trail.log(AuditAction.FILING_CREATED, "Created", entity_type="filing", entity_id="f1")
    trail.log(AuditAction.FILING_REVIEWED, "Reviewed", entity_type="filing", entity_id="f1")
    trail.log(AuditAction.FILING_APPROVED, "Approved", entity_type="filing", entity_id="f1")

    history = trail.get_entity_history("filing", "f1")
    assert len(history) == 3
    assert history[0].action == AuditAction.FILING_CREATED
    assert history[2].action == AuditAction.FILING_APPROVED
