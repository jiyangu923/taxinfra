"""Tests for the UK country module."""

from datetime import date, datetime
from decimal import Decimal

from taxinfra.countries.uk import UKModule
from taxinfra.models.jurisdiction import TaxType
from taxinfra.models.transaction import (
    Transaction,
    TransactionLineItem,
    TransactionType,
)


def _make_transaction(
    net_amount: Decimal,
    seller_country: str = "GB",
    buyer_country: str = "GB",
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


def test_uk_standard_vat():
    module = UKModule()
    txn = _make_transaction(Decimal("1000"))
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].tax_rate == Decimal("20")
    assert results[0].tax_amount == Decimal("200.00")


def test_uk_export_zero_rated():
    module = UKModule()
    txn = _make_transaction(
        Decimal("1000"),
        seller_country="GB",
        buyer_country="DE",
        is_cross_border=True,
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].tax_rate == Decimal("0")
    assert results[0].tax_amount == Decimal("0")


def test_uk_reverse_charge():
    module = UKModule()
    txn = _make_transaction(
        Decimal("1000"),
        seller_country="DE",
        buyer_country="GB",
        is_b2b=True,
        is_cross_border=True,
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].is_reverse_charge is True
    assert results[0].tax_rate == Decimal("20")


def test_uk_exempt():
    module = UKModule()
    txn = _make_transaction(
        Decimal("1000"),
        is_exempt=True,
        exemption_reason="Financial services",
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].is_exempt is True
    assert results[0].tax_amount == Decimal("0")


def test_uk_registration_threshold():
    module = UKModule()
    assert module.get_registration_threshold(TaxType.VAT) == Decimal("90000")


def test_uk_filing_deadline():
    module = UKModule()
    deadline = module.get_filing_deadline(TaxType.VAT, date(2025, 3, 31))
    # 37 days after period end
    assert deadline == date(2025, 5, 7)


def test_uk_filing_schema():
    module = UKModule()
    schema = module.get_filing_schema(TaxType.VAT)
    assert "MTD" in schema.form_name
    assert len(schema.boxes) == 9  # 9-box VAT return
