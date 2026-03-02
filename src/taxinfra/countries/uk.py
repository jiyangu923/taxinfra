"""United Kingdom tax module — VAT."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from taxinfra.countries.base import (
    CountryModule,
    FilingBox,
    FilingSchema,
    PenaltyRule,
    TaxDetermination,
)
from taxinfra.models.jurisdiction import (
    Jurisdiction,
    JurisdictionType,
    TaxRate,
    TaxType,
)
from taxinfra.models.transaction import Transaction


class UKModule(CountryModule):
    country_code = "GB"
    country_name = "United Kingdom"
    currency = "GBP"
    tax_types = [TaxType.VAT]

    STANDARD_RATE = Decimal("20")
    REDUCED_RATE = Decimal("5")
    ZERO_RATE = Decimal("0")

    def get_jurisdictions(self) -> list[Jurisdiction]:
        return [
            Jurisdiction(
                code="GB",
                name="United Kingdom",
                jurisdiction_type=JurisdictionType.COUNTRY,
                country="GB",
                currency="GBP",
                tax_rates=[
                    TaxRate(
                        tax_type=TaxType.VAT,
                        rate=self.STANDARD_RATE,
                        reduced_rate=self.REDUCED_RATE,
                        zero_rate_applicable=True,
                        effective_from=date(2011, 1, 4),
                        description="UK VAT standard rate",
                    ),
                ],
                filing_frequency="quarterly",
                filing_deadline_days=37,
                payment_deadline_days=37,
                registration_threshold=Decimal("90000"),
                registration_threshold_currency="GBP",
                e_invoicing_required=False,
                reverse_charge_applicable=True,
                real_time_reporting=True,  # Making Tax Digital
            )
        ]

    def determine_tax(
        self,
        transaction: Transaction,
        as_of: date | None = None,
    ) -> list[TaxDetermination]:
        """Apply UK VAT rules.

        Key UK VAT rules (simplified):
        - Standard rate: 20%
        - Reduced rate: 5% (children's car seats, energy, etc.)
        - Zero rate: 0% (food, books, children's clothing, exports)
        - Exempt: Financial services, insurance, education, health
        - Reverse charge: B2B services from abroad
        - Making Tax Digital: Quarterly digital reporting
        """
        rules_applied: list[str] = []

        # Export: zero-rated
        if transaction.is_cross_border and transaction.seller_country == "GB":
            rules_applied.append("Export of goods/services — zero-rated")
            return [
                TaxDetermination(
                    jurisdiction_code="GB",
                    tax_type=TaxType.VAT,
                    taxable_amount=transaction.net_total,
                    tax_rate=self.ZERO_RATE,
                    tax_amount=Decimal("0"),
                    rules_applied=rules_applied,
                )
            ]

        # Reverse charge for B2B imports
        if (
            transaction.is_cross_border
            and transaction.is_b2b
            and transaction.buyer_country == "GB"
        ):
            rules_applied.append("Reverse charge applies — B2B import")
            return [
                TaxDetermination(
                    jurisdiction_code="GB",
                    tax_type=TaxType.VAT,
                    taxable_amount=transaction.net_total,
                    tax_rate=self.STANDARD_RATE,
                    tax_amount=(transaction.net_total * self.STANDARD_RATE / 100).quantize(
                        Decimal("0.01")
                    ),
                    is_reverse_charge=True,
                    rules_applied=rules_applied,
                )
            ]

        # Exempt
        if transaction.is_exempt:
            rules_applied.append(f"Exempt: {transaction.exemption_reason}")
            return [
                TaxDetermination(
                    jurisdiction_code="GB",
                    tax_type=TaxType.VAT,
                    taxable_amount=transaction.net_total,
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    is_exempt=True,
                    exemption_reason=transaction.exemption_reason,
                    rules_applied=rules_applied,
                )
            ]

        # Standard rate domestic
        rules_applied.append(f"UK VAT standard rate: {self.STANDARD_RATE}%")
        tax_amount = (transaction.net_total * self.STANDARD_RATE / 100).quantize(Decimal("0.01"))

        return [
            TaxDetermination(
                jurisdiction_code="GB",
                tax_type=TaxType.VAT,
                taxable_amount=transaction.net_total,
                tax_rate=self.STANDARD_RATE,
                tax_amount=tax_amount,
                rules_applied=rules_applied,
            )
        ]

    def get_filing_schema(self, tax_type: TaxType) -> FilingSchema:
        """UK VAT Return (MTD-compatible 9-box return)."""
        return FilingSchema(
            jurisdiction_code="GB",
            tax_type=TaxType.VAT,
            form_name="VAT Return (MTD)",
            version="2024.1",
            boxes=[
                FilingBox(box_number="1", label="VAT due on sales", description="VAT due on sales and other outputs"),
                FilingBox(box_number="2", label="VAT due on acquisitions", description="VAT due on acquisitions from other EC Member States"),
                FilingBox(box_number="3", label="Total VAT due", calculation="box_1 + box_2"),
                FilingBox(box_number="4", label="VAT reclaimed on purchases", description="VAT reclaimed on purchases and other inputs"),
                FilingBox(box_number="5", label="Net VAT", description="Net VAT to pay or reclaim", calculation="box_3 - box_4"),
                FilingBox(box_number="6", label="Total sales ex VAT", description="Total value of sales excluding VAT"),
                FilingBox(box_number="7", label="Total purchases ex VAT", description="Total value of purchases excluding VAT"),
                FilingBox(box_number="8", label="Total supplies ex VAT to EC", description="Total value of supplies to EC Member States"),
                FilingBox(box_number="9", label="Total acquisitions from EC", description="Total value of acquisitions from EC Member States"),
            ],
            filing_frequency="quarterly",
            electronic_filing_required=True,
        )

    def get_penalty_rules(self) -> list[PenaltyRule]:
        return [
            PenaltyRule(
                jurisdiction_code="GB",
                penalty_type="late_filing",
                rate=Decimal("200"),
                is_percentage=False,
                description="Points-based system (MTD): £200 penalty after threshold reached",
                grace_period_days=0,
            ),
            PenaltyRule(
                jurisdiction_code="GB",
                penalty_type="late_payment",
                rate=Decimal("2"),
                description="2% on tax outstanding after 15 days, additional 2% after 30 days",
                grace_period_days=15,
            ),
        ]

    def get_registration_threshold(self, tax_type: TaxType) -> Decimal:
        """UK VAT registration threshold: £90,000 (as of 2024)."""
        return Decimal("90000")

    def get_filing_deadline(self, tax_type: TaxType, period_end: date) -> date:
        """UK VAT: 1 month and 7 days after period end."""
        return period_end + timedelta(days=37)
