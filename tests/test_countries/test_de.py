"""Tests for the Germany country module."""

from datetime import date, datetime
from decimal import Decimal

from taxinfra.countries.de import DEModule
from taxinfra.models.jurisdiction import TaxType
from taxinfra.models.transaction import (
    Transaction,
    TransactionLineItem,
    TransactionType,
)


def _make_transaction(
    net_amount: Decimal,
    seller_country: str = "DE",
    buyer_country: str = "DE",
    is_b2b: bool = False,
    is_cross_border: bool = False,
    is_exempt: bool = False,
    exemption_reason: str = "",
) -> Transaction:
    return Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        seller_country=seller_country,
        buyer_country=buyer_country,
        is_b2b=is_b2b,
        is_cross_border=is_cross_border,
        is_exempt=is_exempt,
        exemption_reason=exemption_reason,
        line_items=[
            TransactionLineItem(
                line_number=1,
                description="Test item",
                quantity=Decimal("1"),
                unit_price=net_amount,
                net_amount=net_amount,
            )
        ],
    )


def test_de_standard_vat():
    module = DEModule()
    txn = _make_transaction(Decimal("1000"))
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].tax_rate == Decimal("19")
    assert results[0].tax_amount == Decimal("190.00")


def test_de_export():
    module = DEModule()
    txn = _make_transaction(
        Decimal("1000"),
        seller_country="DE",
        buyer_country="US",
        is_cross_border=True,
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].tax_amount == Decimal("0")


def test_de_reverse_charge():
    module = DEModule()
    txn = _make_transaction(
        Decimal("1000"),
        seller_country="FR",
        buyer_country="DE",
        is_b2b=True,
        is_cross_border=True,
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].is_reverse_charge is True
    assert results[0].tax_rate == Decimal("19")


def test_de_registration_threshold():
    module = DEModule()
    assert module.get_registration_threshold(TaxType.VAT) == Decimal("0")


def test_de_filing_deadline():
    module = DEModule()
    deadline = module.get_filing_deadline(TaxType.VAT, date(2025, 1, 31))
    assert deadline == date(2025, 2, 10)


def test_de_filing_schema():
    module = DEModule()
    schema = module.get_filing_schema(TaxType.VAT)
    assert "UStVA" in schema.form_name
    assert len(schema.boxes) == 7
