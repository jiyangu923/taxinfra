"""Tests for the traceability module."""

from taxinfra.core.traceability import TraceChain, TraceType


def test_trace_chain_add_and_query():
    chain = TraceChain()

    chain.add_link(
        TraceType.ERP_IMPORT,
        source_type="erp_record",
        source_id="erp-001",
        target_type="transaction",
        target_id="txn-001",
        description="Imported from NetSuite",
    )

    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-001",
        target_type="filing",
        target_id="filing-001",
        description="Aggregated into Q1 filing",
    )

    assert len(chain.links) == 2


def test_trace_forward():
    chain = TraceChain()

    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-001",
        target_type="filing",
        target_id="filing-001",
    )
    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-002",
        target_type="filing",
        target_id="filing-001",
    )

    forward = chain.trace_forward("transaction", "txn-001")
    assert len(forward) == 1
    assert forward[0].target_id == "filing-001"


def test_trace_backward():
    chain = TraceChain()

    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-001",
        target_type="filing",
        target_id="filing-001",
    )
    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-002",
        target_type="filing",
        target_id="filing-001",
    )

    backward = chain.trace_backward("filing", "filing-001")
    assert len(backward) == 2


def test_full_chain():
    chain = TraceChain()

    # ERP -> Transaction -> Filing -> Submission
    chain.add_link(
        TraceType.ERP_IMPORT,
        source_type="erp_record",
        source_id="erp-001",
        target_type="transaction",
        target_id="txn-001",
    )
    chain.add_link(
        TraceType.AGGREGATION,
        source_type="transaction",
        source_id="txn-001",
        target_type="filing",
        target_id="filing-001",
    )
    chain.add_link(
        TraceType.FILING_SUBMISSION,
        source_type="filing",
        source_id="filing-001",
        target_type="submission",
        target_id="sub-001",
    )

    # Get full chain from the transaction
    full = chain.get_full_chain("transaction", "txn-001")
    assert len(full) == 3  # All three links connected
