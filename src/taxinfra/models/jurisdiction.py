"""Jurisdiction models — tax jurisdictions, rates, and rules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class JurisdictionType(StrEnum):
    COUNTRY = "country"
    STATE = "state"
    PROVINCE = "province"
    CITY = "city"
    COUNTY = "county"
    SPECIAL_DISTRICT = "special_district"
    ECONOMIC_ZONE = "economic_zone"


class TaxType(StrEnum):
    VAT = "vat"
    GST = "gst"
    SALES_TAX = "sales_tax"
    USE_TAX = "use_tax"
    EXCISE = "excise"
    CUSTOMS = "customs"
    WITHHOLDING = "withholding"
    DIGITAL_SERVICES = "digital_services"
    EQUALIZATION_LEVY = "equalization_levy"


class TaxRate(BaseModel):
    """A tax rate applicable in a jurisdiction for a given period and category."""

    tax_type: TaxType
    rate: Decimal
    reduced_rate: Decimal | None = None
    zero_rate_applicable: bool = False
    effective_from: date
    effective_to: date | None = None
    product_category: str = ""  # empty = default rate
    description: str = ""

    def is_active(self, as_of: date | None = None) -> bool:
        check_date = as_of or date.today()
        if check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        return True


class Jurisdiction(BaseModel):
    """A tax jurisdiction with its rules, rates, and filing requirements."""

    code: str  # e.g. "US", "US-CA", "DE", "GB"
    name: str
    jurisdiction_type: JurisdictionType
    parent_jurisdiction: str = ""  # code of parent jurisdiction
    country: str  # ISO 3166-1 alpha-2
    currency: str = "USD"

    # Tax rates
    tax_rates: list[TaxRate] = Field(default_factory=list)

    # Filing requirements
    filing_frequency: str = "monthly"  # monthly, quarterly, annually
    filing_deadline_days: int = 30  # days after period end
    payment_deadline_days: int = 30

    # Thresholds
    registration_threshold: Decimal = Decimal("0")
    registration_threshold_currency: str = "USD"

    # E-invoicing
    e_invoicing_required: bool = False
    e_invoicing_standard: str = ""  # e.g. "peppol", "factur-x", "sdi"

    # Features
    reverse_charge_applicable: bool = False
    has_tax_groups: bool = False
    real_time_reporting: bool = False

    def get_active_rate(
        self, tax_type: TaxType, as_of: date | None = None, product_category: str = ""
    ) -> TaxRate | None:
        """Get the currently active rate for a given tax type and category."""
        for rate in self.tax_rates:
            if rate.tax_type != tax_type:
                continue
            if product_category and rate.product_category != product_category:
                continue
            if rate.is_active(as_of):
                return rate
        # Fallback to default rate (no category)
        for rate in self.tax_rates:
            if rate.tax_type == tax_type and rate.product_category == "" and rate.is_active(as_of):
                return rate
        return None
