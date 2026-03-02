"""Reconciliation engine — reconcile transactions with GL and filings."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from taxinfra.models.filing import Filing
from taxinfra.models.transaction import Transaction


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    VARIANCE = "variance"
    MISSING_IN_GL = "missing_in_gl"
    MISSING_IN_TAX = "missing_in_tax"
    UNRECONCILED = "unreconciled"


class ReconciliationItem(BaseModel):
    """A single reconciliation item."""

    transaction_id: str = ""
    gl_reference: str = ""
    status: ReconciliationStatus
    tax_amount: Decimal = Decimal("0")
    gl_amount: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")
    description: str = ""


class ReconciliationResult(BaseModel):
    """Result of a reconciliation run."""

    total_items: int = 0
    matched: int = 0
    variances: int = 0
    missing_in_gl: int = 0
    missing_in_tax: int = 0
    total_variance: Decimal = Decimal("0")
    items: list[ReconciliationItem] = Field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.variances == 0 and self.missing_in_gl == 0 and self.missing_in_tax == 0


class ReconciliationEngine:
    """Reconcile tax data against GL entries.

    Compares:
    - Transaction-level tax amounts vs. GL tax account postings
    - Filing totals vs. aggregated transaction totals
    - Payment amounts vs. filing amounts due
    """

    def reconcile_transactions_to_gl(
        self,
        transactions: list[Transaction],
        gl_entries: list[dict],
    ) -> ReconciliationResult:
        """Reconcile transactions against GL entries.

        Args:
            transactions: Tax transactions to reconcile
            gl_entries: GL entries as dicts with keys: reference, amount, account
        """
        gl_by_ref: dict[str, dict] = {
            entry["reference"]: entry for entry in gl_entries
        }

        items: list[ReconciliationItem] = []
        matched = 0
        variances = 0
        missing_in_gl = 0
        total_variance = Decimal("0")

        for txn in transactions:
            ref = txn.invoice_number or txn.external_id or str(txn.id)
            gl_entry = gl_by_ref.pop(ref, None)

            if gl_entry is None:
                items.append(
                    ReconciliationItem(
                        transaction_id=str(txn.id),
                        status=ReconciliationStatus.MISSING_IN_GL,
                        tax_amount=txn.tax_total,
                        description=f"Transaction {ref} not found in GL",
                    )
                )
                missing_in_gl += 1
                continue

            gl_amount = Decimal(str(gl_entry["amount"]))
            variance = txn.tax_total - gl_amount

            if variance == 0:
                items.append(
                    ReconciliationItem(
                        transaction_id=str(txn.id),
                        gl_reference=ref,
                        status=ReconciliationStatus.MATCHED,
                        tax_amount=txn.tax_total,
                        gl_amount=gl_amount,
                    )
                )
                matched += 1
            else:
                items.append(
                    ReconciliationItem(
                        transaction_id=str(txn.id),
                        gl_reference=ref,
                        status=ReconciliationStatus.VARIANCE,
                        tax_amount=txn.tax_total,
                        gl_amount=gl_amount,
                        variance=variance,
                        description=f"Variance of {variance}",
                    )
                )
                variances += 1
                total_variance += abs(variance)

        # Remaining GL entries not matched to transactions
        missing_in_tax = len(gl_by_ref)
        for ref, entry in gl_by_ref.items():
            items.append(
                ReconciliationItem(
                    gl_reference=ref,
                    status=ReconciliationStatus.MISSING_IN_TAX,
                    gl_amount=Decimal(str(entry["amount"])),
                    description=f"GL entry {ref} not found in tax transactions",
                )
            )

        return ReconciliationResult(
            total_items=len(transactions) + missing_in_tax,
            matched=matched,
            variances=variances,
            missing_in_gl=missing_in_gl,
            missing_in_tax=missing_in_tax,
            total_variance=total_variance,
            items=items,
        )

    def reconcile_filing_to_transactions(
        self,
        filing: Filing,
        transactions: list[Transaction],
    ) -> ReconciliationResult:
        """Verify that a filing's totals match the underlying transactions."""
        txn_total_tax = sum(
            (t.tax_total for t in transactions), Decimal("0")
        )
        filing_total = filing.total_tax_due

        variance = filing_total - txn_total_tax
        status = ReconciliationStatus.MATCHED if variance == 0 else ReconciliationStatus.VARIANCE

        return ReconciliationResult(
            total_items=1,
            matched=1 if variance == 0 else 0,
            variances=0 if variance == 0 else 1,
            total_variance=abs(variance),
            items=[
                ReconciliationItem(
                    transaction_id=str(filing.id),
                    status=status,
                    tax_amount=filing_total,
                    gl_amount=txn_total_tax,
                    variance=variance,
                    description=(
                        "Filing matches transactions"
                        if variance == 0
                        else f"Filing variance of {variance} vs transactions"
                    ),
                )
            ],
        )
