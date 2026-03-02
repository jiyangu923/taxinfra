"""Transaction models — the atomic unit of tax-relevant activity."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TransactionType(StrEnum):
    SALE = "sale"
    PURCHASE = "purchase"
    REFUND = "refund"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class TransactionLineItem(BaseModel):
    """A single line within a transaction."""

    id: UUID = Field(default_factory=uuid4)
    line_number: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    net_amount: Decimal
    tax_amount: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")
    tax_code: str = ""
    product_category: str = ""
    hs_code: str = ""  # Harmonized System code for cross-border
    country_of_origin: str = ""
    exemption_certificate: str | None = None

    @property
    def gross_amount(self) -> Decimal:
        return self.net_amount + self.tax_amount


class Transaction(BaseModel):
    """A tax-relevant transaction with full traceability."""

    id: UUID = Field(default_factory=uuid4)
    external_id: str = ""  # ID from source system (ERP, billing, etc.)
    source_system: str = ""  # e.g. "netsuite", "stripe", "shopify"
    transaction_type: TransactionType
    transaction_date: datetime
    posted_date: datetime | None = None
    currency: str = "USD"
    exchange_rate: Decimal = Decimal("1")

    # Parties
    seller_entity_id: UUID | None = None
    buyer_entity_id: UUID | None = None
    seller_country: str = ""
    buyer_country: str = ""
    seller_jurisdiction: str = ""
    buyer_jurisdiction: str = ""

    # Amounts
    line_items: list[TransactionLineItem] = Field(default_factory=list)

    # Classification
    is_b2b: bool = False
    is_cross_border: bool = False
    is_digital_service: bool = False
    is_exempt: bool = False
    exemption_reason: str = ""

    # Traceability
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    gl_account: str = ""
    invoice_number: str = ""
    po_number: str = ""

    @property
    def net_total(self) -> Decimal:
        return sum((line.net_amount for line in self.line_items), Decimal("0"))

    @property
    def tax_total(self) -> Decimal:
        return sum((line.tax_amount for line in self.line_items), Decimal("0"))

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.tax_total
