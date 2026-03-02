"""Tests for the reconciliation engine."""

from datetime import datetime
from decimal import Decimal

from taxinfra.compliance.reconciliation import ReconciliationEngine, ReconciliationStatus
from taxinfra.models.transaction import (
    Transaction,
    TransactionLineItem,
    TransactionType,
)


def _make_transaction(
    invoice_number: str,
    tax_amount: Decimal,
) -> Transaction:
    return Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        invoice_number=invoice_number,
        line_items=[
            TransactionLineItem(
                line_number=1,
                description="Test",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                net_amount=Decimal("100"),
                tax_amount=tax_amount,
            )
        ],
    )


def test_reconciliation_all_matched():
    engine = ReconciliationEngine()
    transactions = [
        _make_transaction("INV-001", Decimal("20")),
        _make_transaction("INV-002", Decimal("15")),
    ]
    gl_entries = [
        {"reference": "INV-001", "amount": "20", "account": "2200"},
        {"reference": "INV-002", "amount": "15", "account": "2200"},
    ]

    result = engine.reconcile_transactions_to_gl(transactions, gl_entries)

    assert result.is_clean
    assert result.matched == 2
    assert result.variances == 0


def test_reconciliation_variance():
    engine = ReconciliationEngine()
    transactions = [
        _make_transaction("INV-001", Decimal("20")),
    ]
    gl_entries = [
        {"reference": "INV-001", "amount": "19.50", "account": "2200"},
    ]

    result = engine.reconcile_transactions_to_gl(transactions, gl_entries)

    assert not result.is_clean
    assert result.variances == 1
    assert result.total_variance == Decimal("0.50")


def test_reconciliation_missing_in_gl():
    engine = ReconciliationEngine()
    transactions = [
        _make_transaction("INV-001", Decimal("20")),
        _make_transaction("INV-002", Decimal("15")),
    ]
    gl_entries = [
        {"reference": "INV-001", "amount": "20", "account": "2200"},
    ]

    result = engine.reconcile_transactions_to_gl(transactions, gl_entries)

    assert not result.is_clean
    assert result.missing_in_gl == 1


def test_reconciliation_missing_in_tax():
    engine = ReconciliationEngine()
    transactions = [
        _make_transaction("INV-001", Decimal("20")),
    ]
    gl_entries = [
        {"reference": "INV-001", "amount": "20", "account": "2200"},
        {"reference": "INV-999", "amount": "50", "account": "2200"},
    ]

    result = engine.reconcile_transactions_to_gl(transactions, gl_entries)

    assert not result.is_clean
    assert result.missing_in_tax == 1
