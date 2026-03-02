"""Filing engine — generates tax return filings from transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from taxinfra.core.audit_trail import AuditAction, AuditTrail
from taxinfra.core.traceability import TraceChain, TraceType
from taxinfra.countries.base import CountryModule
from taxinfra.models.filing import Filing, FilingLineItem, FilingStatus
from taxinfra.models.transaction import Transaction, TransactionType


class FilingEngine:
    """Generates tax filings from transaction data using country-specific rules."""

    def __init__(self, audit_trail: AuditTrail, trace_chain: TraceChain) -> None:
        self.audit_trail = audit_trail
        self.trace_chain = trace_chain

    def generate_filing(
        self,
        entity_id: UUID,
        transactions: list[Transaction],
        country_module: CountryModule,
        tax_type: str,
        period_start: date,
        period_end: date,
    ) -> Filing:
        """Generate a draft filing from transactions.

        Steps:
        1. Filter transactions for the period and jurisdiction
        2. Apply country-specific tax determination
        3. Aggregate into filing line items
        4. Create traceability links from transactions -> filing
        """
        # Filter transactions for the period
        period_transactions = [
            t
            for t in transactions
            if period_start <= t.transaction_date.date() <= period_end
        ]

        # Calculate totals
        output_tax = Decimal("0")
        input_tax = Decimal("0")
        sales_ids: list[UUID] = []
        purchase_ids: list[UUID] = []

        for txn in period_transactions:
            determinations = country_module.determine_tax(txn)
            for det in determinations:
                if txn.transaction_type in (TransactionType.SALE, TransactionType.REFUND):
                    output_tax += det.tax_amount
                    sales_ids.append(txn.id)
                elif txn.transaction_type == TransactionType.PURCHASE:
                    input_tax += det.tax_amount
                    purchase_ids.append(txn.id)

        filing = Filing(
            entity_id=entity_id,
            jurisdiction_code=country_module.country_code,
            tax_type=tax_type,
            period_start=period_start,
            period_end=period_end,
            due_date=country_module.get_filing_deadline(
                __import__("taxinfra.models.jurisdiction", fromlist=["TaxType"]).TaxType(tax_type),
                period_end,
            ),
            status=FilingStatus.DRAFT,
            line_items=[
                FilingLineItem(
                    box_number="output",
                    description="Output tax on sales",
                    amount=output_tax,
                    source_transaction_ids=sales_ids,
                ),
                FilingLineItem(
                    box_number="input",
                    description="Input tax on purchases",
                    amount=input_tax,
                    source_transaction_ids=purchase_ids,
                ),
            ],
            total_tax_due=output_tax,
            total_input_tax=input_tax,
            net_tax_payable=output_tax - input_tax,
        )

        # Audit trail
        self.audit_trail.log(
            AuditAction.FILING_CREATED,
            f"Filing generated: {country_module.country_code} {tax_type} "
            f"{period_start} to {period_end}",
            entity_type="filing",
            entity_id=str(filing.id),
            details={
                "output_tax": str(output_tax),
                "input_tax": str(input_tax),
                "net_payable": str(filing.net_tax_payable),
                "transaction_count": len(period_transactions),
            },
        )

        # Traceability: link every source transaction to this filing
        for txn in period_transactions:
            self.trace_chain.add_link(
                TraceType.AGGREGATION,
                source_type="transaction",
                source_id=str(txn.id),
                target_type="filing",
                target_id=str(filing.id),
                description=f"Transaction {txn.id} -> Filing {filing.id}",
            )

        return filing
