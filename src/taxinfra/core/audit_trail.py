"""Audit trail — immutable log of every action taken by the system.

Every agent decision, data access, filing change, and human approval is logged
with full context. This is the backbone of the trust layer.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditAction(StrEnum):
    # Agent actions
    AGENT_INVOKED = "agent_invoked"
    AGENT_DECISION = "agent_decision"
    AGENT_COMPLETED = "agent_completed"

    # Data actions
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_IMPORT = "data_import"

    # Filing lifecycle
    FILING_CREATED = "filing_created"
    FILING_REVIEWED = "filing_reviewed"
    FILING_APPROVED = "filing_approved"
    FILING_SUBMITTED = "filing_submitted"
    FILING_AMENDED = "filing_amended"

    # Compliance
    ANOMALY_DETECTED = "anomaly_detected"
    RECONCILIATION_RUN = "reconciliation_run"
    RULE_APPLIED = "rule_applied"

    # Human-in-the-loop
    HUMAN_APPROVAL = "human_approval"
    HUMAN_REJECTION = "human_rejection"
    HUMAN_OVERRIDE = "human_override"


class AuditEntry(BaseModel):
    """A single immutable audit log entry."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: AuditAction
    agent_name: str = ""
    user: str = ""  # Human user if applicable

    # What was acted on
    entity_type: str = ""  # e.g. "transaction", "filing", "entity"
    entity_id: str = ""

    # Context
    description: str
    details: dict = Field(default_factory=dict)

    # Traceability
    session_id: str = ""
    correlation_id: str = ""  # Links related entries across agents
    parent_entry_id: UUID | None = None

    # Data integrity
    input_hash: str = ""  # Hash of input data used
    output_hash: str = ""  # Hash of output produced


class AuditTrail:
    """Append-only audit trail for the tax operations system.

    In production this would write to an immutable store (e.g. append-only
    database table, event log, or ledger). This implementation provides the
    interface and in-memory storage for development.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def log(
        self,
        action: AuditAction,
        description: str,
        *,
        agent_name: str = "",
        user: str = "",
        entity_type: str = "",
        entity_id: str = "",
        details: dict | None = None,
        session_id: str = "",
        correlation_id: str = "",
        parent_entry_id: UUID | None = None,
    ) -> AuditEntry:
        """Record an audit entry."""
        entry = AuditEntry(
            action=action,
            description=description,
            agent_name=agent_name,
            user=user,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            session_id=session_id,
            correlation_id=correlation_id,
            parent_entry_id=parent_entry_id,
        )
        self._entries.append(entry)
        logger.info(
            "AUDIT: [%s] %s — %s",
            entry.action,
            entry.description,
            json.dumps({"entity_type": entry.entity_type, "entity_id": entry.entity_id}),
        )
        return entry

    def get_entries(
        self,
        *,
        entity_type: str = "",
        entity_id: str = "",
        action: AuditAction | None = None,
        agent_name: str = "",
        correlation_id: str = "",
        since: datetime | None = None,
    ) -> list[AuditEntry]:
        """Query audit entries with filters."""
        results = self._entries
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        if action:
            results = [e for e in results if e.action == action]
        if agent_name:
            results = [e for e in results if e.agent_name == agent_name]
        if correlation_id:
            results = [e for e in results if e.correlation_id == correlation_id]
        if since:
            results = [e for e in results if e.timestamp >= since]
        return results

    def get_entity_history(self, entity_type: str, entity_id: str) -> list[AuditEntry]:
        """Get full audit history for a specific entity."""
        return self.get_entries(entity_type=entity_type, entity_id=entity_id)

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)
