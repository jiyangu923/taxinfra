"""Base country module — the interface every country skill must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from taxinfra.models.jurisdiction import Jurisdiction, TaxType
from taxinfra.models.transaction import Transaction


class TaxDetermination(BaseModel):
    """The result of applying country-specific tax logic to a transaction."""

    jurisdiction_code: str
    tax_type: TaxType
    taxable_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    is_exempt: bool = False
    exemption_reason: str = ""
    is_reverse_charge: bool = False
    rules_applied: list[str] = Field(default_factory=list)


class FilingSchema(BaseModel):
    """Schema definition for a country's tax return form."""

    jurisdiction_code: str
    tax_type: TaxType
    form_name: str
    version: str = "1.0"
    boxes: list[FilingBox] = Field(default_factory=list)
    filing_frequency: str = "monthly"
    electronic_filing_required: bool = False


class FilingBox(BaseModel):
    """A single box/field on a tax return form."""

    box_number: str
    label: str
    description: str = ""
    data_type: str = "decimal"  # decimal, string, date, boolean
    required: bool = True
    calculation: str = ""  # How to compute this box


class PenaltyRule(BaseModel):
    """Penalty/interest rules for late filing or payment."""

    jurisdiction_code: str
    penalty_type: str  # "late_filing", "late_payment", "understatement"
    rate: Decimal  # Percentage or fixed amount
    is_percentage: bool = True
    max_amount: Decimal | None = None
    grace_period_days: int = 0
    description: str = ""


class CountryModule(ABC):
    """Base class for country-specific tax modules.

    Each country module encodes the jurisdiction's tax rules, filing schemas,
    penalty logic, and compliance requirements.
    """

    country_code: str = ""
    country_name: str = ""
    currency: str = ""
    tax_types: list[TaxType] = []

    @abstractmethod
    def get_jurisdictions(self) -> list[Jurisdiction]:
        """Return all jurisdictions within this country."""
        ...

    @abstractmethod
    def determine_tax(
        self,
        transaction: Transaction,
        as_of: date | None = None,
    ) -> list[TaxDetermination]:
        """Apply country-specific tax rules to a transaction."""
        ...

    @abstractmethod
    def get_filing_schema(self, tax_type: TaxType) -> FilingSchema:
        """Get the filing form schema for a specific tax type."""
        ...

    @abstractmethod
    def get_penalty_rules(self) -> list[PenaltyRule]:
        """Get penalty and interest rules."""
        ...

    @abstractmethod
    def get_registration_threshold(self, tax_type: TaxType) -> Decimal:
        """Get the registration threshold for a tax type."""
        ...

    def get_filing_deadline(self, tax_type: TaxType, period_end: date) -> date:
        """Get the filing deadline for a period. Override per country."""
        from datetime import timedelta
        return period_end + timedelta(days=30)

    def get_payment_deadline(self, tax_type: TaxType, period_end: date) -> date:
        """Get the payment deadline for a period. Override per country."""
        return self.get_filing_deadline(tax_type, period_end)
