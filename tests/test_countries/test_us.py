"""Tests for the US country module."""

from datetime import date, datetime
from decimal import Decimal

from taxinfra.countries.us import USModule
from taxinfra.models.jurisdiction import TaxType
from taxinfra.models.transaction import (
    Transaction,
    TransactionLineItem,
    TransactionType,
)


def _make_transaction(
    net_amount: Decimal,
    buyer_jurisdiction: str = "US-CA",
    buyer_country: str = "US",
    seller_country: str = "US",
    is_exempt: bool = False,
    exemption_reason: str = "",
) -> Transaction:
    return Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        seller_country=seller_country,
        buyer_country=buyer_country,
        buyer_jurisdiction=buyer_jurisdiction,
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


def test_us_standard_sales_tax():
    module = USModule()
    txn = _make_transaction(Decimal("1000"), buyer_jurisdiction="US-CA")
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].tax_rate == Decimal("7.25")
    assert results[0].tax_amount == Decimal("72.50")
    assert results[0].jurisdiction_code == "US-CA"


def test_us_no_sales_tax_state():
    module = USModule()
    txn = _make_transaction(Decimal("1000"), buyer_jurisdiction="US-OR")
    results = module.determine_tax(txn)

    assert len(results) == 0  # Oregon has no sales tax


def test_us_exempt_transaction():
    module = USModule()
    txn = _make_transaction(
        Decimal("1000"),
        buyer_jurisdiction="US-CA",
        is_exempt=True,
        exemption_reason="Resale certificate",
    )
    results = module.determine_tax(txn)

    assert len(results) == 1
    assert results[0].is_exempt is True
    assert results[0].tax_amount == Decimal("0")


def test_us_registration_threshold():
    module = USModule()
    threshold = module.get_registration_threshold(TaxType.SALES_TAX)
    assert threshold == Decimal("100000")


def test_us_filing_deadline():
    module = USModule()
    deadline = module.get_filing_deadline(TaxType.SALES_TAX, date(2025, 1, 31))
    assert deadline == date(2025, 2, 20)


def test_us_jurisdictions():
    module = USModule()
    jurisdictions = module.get_jurisdictions()

    # Federal + states
    assert len(jurisdictions) >= 11
    codes = [j.code for j in jurisdictions]
    assert "US" in codes
    assert "US-CA" in codes
    assert "US-TX" in codes


def test_us_filing_schema():
    module = USModule()
    schema = module.get_filing_schema(TaxType.SALES_TAX)
    assert schema.form_name == "Sales and Use Tax Return"
    assert len(schema.boxes) == 4


def test_us_penalty_rules():
    module = USModule()
    rules = module.get_penalty_rules()
    assert len(rules) == 2
    late_filing = [r for r in rules if r.penalty_type == "late_filing"]
    assert len(late_filing) == 1
