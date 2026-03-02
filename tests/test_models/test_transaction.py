"""Tests for transaction models."""

from datetime import datetime
from decimal import Decimal

from taxinfra.models.transaction import Transaction, TransactionLineItem, TransactionType


def test_transaction_creation():
    txn = Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        currency="USD",
        seller_country="US",
        buyer_country="US",
        buyer_jurisdiction="US-CA",
        line_items=[
            TransactionLineItem(
                line_number=1,
                description="Software license",
                quantity=Decimal("1"),
                unit_price=Decimal("1000"),
                net_amount=Decimal("1000"),
                tax_amount=Decimal("72.50"),
                tax_rate=Decimal("7.25"),
            )
        ],
    )
    assert txn.net_total == Decimal("1000")
    assert txn.tax_total == Decimal("72.50")
    assert txn.gross_total == Decimal("1072.50")


def test_transaction_with_multiple_lines():
    txn = Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        line_items=[
            TransactionLineItem(
                line_number=1,
                description="Item A",
                quantity=Decimal("2"),
                unit_price=Decimal("50"),
                net_amount=Decimal("100"),
                tax_amount=Decimal("7.25"),
            ),
            TransactionLineItem(
                line_number=2,
                description="Item B",
                quantity=Decimal("1"),
                unit_price=Decimal("200"),
                net_amount=Decimal("200"),
                tax_amount=Decimal("14.50"),
            ),
        ],
    )
    assert txn.net_total == Decimal("300")
    assert txn.tax_total == Decimal("21.75")


def test_transaction_empty_lines():
    txn = Transaction(
        transaction_type=TransactionType.PURCHASE,
        transaction_date=datetime(2025, 1, 15),
    )
    assert txn.net_total == Decimal("0")
    assert txn.tax_total == Decimal("0")
    assert txn.gross_total == Decimal("0")


def test_line_item_gross_amount():
    item = TransactionLineItem(
        line_number=1,
        description="Test",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        net_amount=Decimal("100"),
        tax_amount=Decimal("20"),
    )
    assert item.gross_amount == Decimal("120")


def test_transaction_types():
    assert TransactionType.SALE == "sale"
    assert TransactionType.REFUND == "refund"
    assert TransactionType.CREDIT_NOTE == "credit_note"
