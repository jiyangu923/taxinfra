"""Tests for the anomaly detection module."""

from datetime import datetime
from decimal import Decimal

from taxinfra.compliance.anomaly import AnomalyDetector, AnomalyType
from taxinfra.models.transaction import (
    Transaction,
    TransactionLineItem,
    TransactionType,
)


def _make_transaction(
    net_amount: Decimal,
    tax_amount: Decimal = Decimal("0"),
    is_exempt: bool = False,
    external_id: str = "",
    source_system: str = "",
    buyer_country: str = "US",
) -> Transaction:
    return Transaction(
        transaction_type=TransactionType.SALE,
        transaction_date=datetime(2025, 1, 15),
        external_id=external_id,
        source_system=source_system,
        buyer_country=buyer_country,
        is_exempt=is_exempt,
        line_items=[
            TransactionLineItem(
                line_number=1,
                description="Test",
                quantity=Decimal("1"),
                unit_price=net_amount,
                net_amount=net_amount,
                tax_amount=tax_amount,
            )
        ],
    )


def test_detect_missing_tax():
    detector = AnomalyDetector()
    transactions = [
        _make_transaction(Decimal("1000"), tax_amount=Decimal("0")),
    ]
    anomalies = detector.detect(transactions)

    missing_tax = [a for a in anomalies if a.anomaly_type == AnomalyType.MISSING_TAX]
    assert len(missing_tax) == 1
    assert missing_tax[0].severity == "high"


def test_no_anomaly_for_exempt():
    detector = AnomalyDetector()
    transactions = [
        _make_transaction(Decimal("1000"), tax_amount=Decimal("0"), is_exempt=True),
    ]
    anomalies = detector.detect(transactions)

    missing_tax = [a for a in anomalies if a.anomaly_type == AnomalyType.MISSING_TAX]
    assert len(missing_tax) == 0


def test_detect_large_amount():
    detector = AnomalyDetector(large_amount_threshold=Decimal("50000"))
    transactions = [
        _make_transaction(Decimal("100000"), tax_amount=Decimal("7250")),
    ]
    anomalies = detector.detect(transactions)

    large = [a for a in anomalies if a.anomaly_type == AnomalyType.LARGE_AMOUNT]
    assert len(large) == 1


def test_detect_duplicates():
    detector = AnomalyDetector()
    transactions = [
        _make_transaction(
            Decimal("100"),
            tax_amount=Decimal("7.25"),
            external_id="INV-001",
            source_system="netsuite",
        ),
        _make_transaction(
            Decimal("100"),
            tax_amount=Decimal("7.25"),
            external_id="INV-001",
            source_system="netsuite",
        ),
    ]
    anomalies = detector.detect(transactions)

    dupes = [a for a in anomalies if a.anomaly_type == AnomalyType.DUPLICATE_TRANSACTION]
    assert len(dupes) == 1
    assert dupes[0].severity == "critical"


def test_detect_missing_jurisdiction():
    detector = AnomalyDetector()
    transactions = [
        _make_transaction(Decimal("100"), tax_amount=Decimal("7"), buyer_country=""),
    ]
    anomalies = detector.detect(transactions)

    missing = [a for a in anomalies if a.anomaly_type == AnomalyType.MISSING_JURISDICTION]
    assert len(missing) == 1
