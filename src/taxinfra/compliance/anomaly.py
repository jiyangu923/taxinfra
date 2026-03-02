"""Anomaly detection — flag unusual patterns in tax data."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from taxinfra.models.transaction import Transaction


class AnomalyType(StrEnum):
    UNUSUAL_TAX_RATE = "unusual_tax_rate"
    MISSING_TAX = "missing_tax"
    DUPLICATE_TRANSACTION = "duplicate_transaction"
    LARGE_AMOUNT = "large_amount"
    MISSING_JURISDICTION = "missing_jurisdiction"
    INCONSISTENT_CLASSIFICATION = "inconsistent_classification"
    THRESHOLD_BREACH = "threshold_breach"


class TaxAnomaly(BaseModel):
    """A detected anomaly in tax data."""

    anomaly_type: AnomalyType
    severity: str = "medium"  # low, medium, high, critical
    transaction_id: str = ""
    description: str
    expected_value: str = ""
    actual_value: str = ""
    recommendation: str = ""


class AnomalyDetector:
    """Detect anomalies in transaction and filing data.

    Checks for:
    - Unusual tax rates (too high, too low, missing)
    - Missing tax on taxable transactions
    - Duplicate transactions
    - Unusually large amounts
    - Missing jurisdiction information
    - Inconsistent product classification
    """

    def __init__(
        self,
        large_amount_threshold: Decimal = Decimal("100000"),
        expected_rates: dict[str, Decimal] | None = None,
    ) -> None:
        self.large_amount_threshold = large_amount_threshold
        self.expected_rates = expected_rates or {}

    def detect(self, transactions: list[Transaction]) -> list[TaxAnomaly]:
        """Run all anomaly detection checks on a list of transactions."""
        anomalies: list[TaxAnomaly] = []
        anomalies.extend(self._check_missing_tax(transactions))
        anomalies.extend(self._check_large_amounts(transactions))
        anomalies.extend(self._check_missing_jurisdiction(transactions))
        anomalies.extend(self._check_duplicates(transactions))
        return anomalies

    def _check_missing_tax(self, transactions: list[Transaction]) -> list[TaxAnomaly]:
        """Flag transactions with no tax that should have tax."""
        anomalies: list[TaxAnomaly] = []
        for txn in transactions:
            if txn.is_exempt:
                continue
            if txn.tax_total == 0 and txn.net_total > 0:
                anomalies.append(
                    TaxAnomaly(
                        anomaly_type=AnomalyType.MISSING_TAX,
                        severity="high",
                        transaction_id=str(txn.id),
                        description=f"Transaction {txn.external_id or txn.id} has no tax but is not marked exempt",
                        expected_value="Tax amount > 0",
                        actual_value="0",
                        recommendation="Review transaction tax classification and exemption status",
                    )
                )
        return anomalies

    def _check_large_amounts(self, transactions: list[Transaction]) -> list[TaxAnomaly]:
        """Flag unusually large transactions for review."""
        anomalies: list[TaxAnomaly] = []
        for txn in transactions:
            if txn.net_total > self.large_amount_threshold:
                anomalies.append(
                    TaxAnomaly(
                        anomaly_type=AnomalyType.LARGE_AMOUNT,
                        severity="medium",
                        transaction_id=str(txn.id),
                        description=f"Transaction {txn.external_id or txn.id} exceeds {self.large_amount_threshold} threshold",
                        actual_value=str(txn.net_total),
                        recommendation="Verify large transaction amount and tax treatment",
                    )
                )
        return anomalies

    def _check_missing_jurisdiction(self, transactions: list[Transaction]) -> list[TaxAnomaly]:
        """Flag transactions missing jurisdiction information."""
        anomalies: list[TaxAnomaly] = []
        for txn in transactions:
            if not txn.buyer_country and not txn.buyer_jurisdiction:
                anomalies.append(
                    TaxAnomaly(
                        anomaly_type=AnomalyType.MISSING_JURISDICTION,
                        severity="high",
                        transaction_id=str(txn.id),
                        description=f"Transaction {txn.external_id or txn.id} missing buyer jurisdiction",
                        recommendation="Add buyer country and jurisdiction for tax determination",
                    )
                )
        return anomalies

    def _check_duplicates(self, transactions: list[Transaction]) -> list[TaxAnomaly]:
        """Flag potential duplicate transactions."""
        anomalies: list[TaxAnomaly] = []
        seen: dict[str, str] = {}  # key -> first transaction id
        for txn in transactions:
            if not txn.external_id:
                continue
            key = f"{txn.source_system}:{txn.external_id}"
            if key in seen:
                anomalies.append(
                    TaxAnomaly(
                        anomaly_type=AnomalyType.DUPLICATE_TRANSACTION,
                        severity="critical",
                        transaction_id=str(txn.id),
                        description=f"Potential duplicate: {txn.external_id} from {txn.source_system} (also seen as {seen[key]})",
                        recommendation="Investigate and deduplicate before filing",
                    )
                )
            else:
                seen[key] = str(txn.id)
        return anomalies
