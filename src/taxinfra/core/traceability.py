"""Traceability — link every filing back to its source transactions.

The key differentiator: traceability from filing -> source transaction -> API -> ledger.
No current vendor truly owns this chain. This module provides the graph of links
that connects every output to its inputs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TraceType(StrEnum):
    """Type of link in the traceability chain."""

    # Source data
    ERP_IMPORT = "erp_import"  # ERP -> Transaction
    BILLING_IMPORT = "billing_import"  # Billing system -> Transaction
    PAYMENT_IMPORT = "payment_import"  # Payment provider -> Transaction

    # Processing
    CLASSIFICATION = "classification"  # Transaction -> Tax determination
    RATE_LOOKUP = "rate_lookup"  # Tax determination -> Rate applied
    EXEMPTION_CHECK = "exemption_check"  # Transaction -> Exemption decision

    # Filing
    AGGREGATION = "aggregation"  # Transactions -> Filing line item
    FILING_GENERATION = "filing_generation"  # Filing line items -> Filing
    FILING_SUBMISSION = "filing_submission"  # Filing -> Authority submission

    # Reconciliation
    GL_RECONCILIATION = "gl_reconciliation"  # Transaction -> GL entry
    PAYMENT_RECONCILIATION = "payment_reconciliation"  # Filing -> Payment


class TraceLink(BaseModel):
    """A single link in the traceability chain."""

    id: UUID = Field(default_factory=uuid4)
    trace_type: TraceType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Source
    source_type: str  # e.g. "transaction", "erp_record", "gl_entry"
    source_id: str

    # Target
    target_type: str  # e.g. "filing_line_item", "tax_determination"
    target_id: str

    # Context
    description: str = ""
    metadata: dict = Field(default_factory=dict)


class TraceChain:
    """Builds and queries the traceability graph.

    Given any entity (a filing, a transaction, a payment), this can produce
    the complete chain of how it was derived, what data fed into it, and
    where the output went.
    """

    def __init__(self) -> None:
        self._links: list[TraceLink] = []

    def add_link(
        self,
        trace_type: TraceType,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        description: str = "",
        metadata: dict | None = None,
    ) -> TraceLink:
        """Add a link to the traceability chain."""
        link = TraceLink(
            trace_type=trace_type,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            description=description,
            metadata=metadata or {},
        )
        self._links.append(link)
        return link

    def trace_forward(self, source_type: str, source_id: str) -> list[TraceLink]:
        """Find all links originating from a given source (where did this data go?)."""
        return [
            link
            for link in self._links
            if link.source_type == source_type and link.source_id == source_id
        ]

    def trace_backward(self, target_type: str, target_id: str) -> list[TraceLink]:
        """Find all links pointing to a given target (where did this data come from?)."""
        return [
            link
            for link in self._links
            if link.target_type == target_type and link.target_id == target_id
        ]

    def get_full_chain(self, entity_type: str, entity_id: str) -> list[TraceLink]:
        """Get the complete chain for an entity, both forward and backward."""
        visited: set[str] = set()
        chain: list[TraceLink] = []
        self._walk_chain(entity_type, entity_id, visited, chain)
        return chain

    def _walk_chain(
        self,
        entity_type: str,
        entity_id: str,
        visited: set[str],
        chain: list[TraceLink],
    ) -> None:
        key = f"{entity_type}:{entity_id}"
        if key in visited:
            return
        visited.add(key)

        # Walk backward (sources)
        for link in self.trace_backward(entity_type, entity_id):
            if str(link.id) not in {str(l.id) for l in chain}:
                chain.append(link)
                self._walk_chain(link.source_type, link.source_id, visited, chain)

        # Walk forward (targets)
        for link in self.trace_forward(entity_type, entity_id):
            if str(link.id) not in {str(l.id) for l in chain}:
                chain.append(link)
                self._walk_chain(link.target_type, link.target_id, visited, chain)

    @property
    def links(self) -> list[TraceLink]:
        return list(self._links)
