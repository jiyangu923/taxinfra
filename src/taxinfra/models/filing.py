"""Filing models — tax return filings and their lifecycle."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FilingStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"


class FilingLineItem(BaseModel):
    """A line item on a tax filing, linked back to source transactions."""

    id: UUID = Field(default_factory=uuid4)
    box_number: str  # The box/field on the return form
    description: str
    amount: Decimal
    source_transaction_ids: list[UUID] = Field(default_factory=list)


class Filing(BaseModel):
    """A tax return filing for a specific jurisdiction and period."""

    id: UUID = Field(default_factory=uuid4)
    entity_id: UUID
    jurisdiction_code: str
    tax_type: str  # vat, gst, sales_tax, etc.

    # Period
    period_start: date
    period_end: date
    due_date: date

    # Status
    status: FilingStatus = FilingStatus.DRAFT
    submitted_at: datetime | None = None
    accepted_at: datetime | None = None

    # Amounts
    line_items: list[FilingLineItem] = Field(default_factory=list)
    total_tax_due: Decimal = Decimal("0")
    total_input_tax: Decimal = Decimal("0")
    net_tax_payable: Decimal = Decimal("0")

    # Payment
    payment_reference: str = ""
    payment_date: date | None = None

    # Traceability
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = ""
    approved_by: str = ""

    # Audit trail
    amendment_of: UUID | None = None  # ID of original filing if this is an amendment
    notes: str = ""

    @property
    def source_transaction_ids(self) -> set[UUID]:
        """All source transaction IDs that feed into this filing."""
        ids: set[UUID] = set()
        for item in self.line_items:
            ids.update(item.source_transaction_ids)
        return ids
