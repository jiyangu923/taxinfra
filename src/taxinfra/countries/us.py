"""United States tax module — sales & use tax."""

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


class USModule(CountryModule):
    country_code = "US"
    country_name = "United States"
    currency = "USD"
    tax_types = [TaxType.SALES_TAX, TaxType.USE_TAX, TaxType.EXCISE]

    # Selected state rates (simplified — production would have full rate tables)
    STATE_RATES: dict[str, Decimal] = {
        "US-CA": Decimal("7.25"),
        "US-NY": Decimal("4.0"),
        "US-TX": Decimal("6.25"),
        "US-FL": Decimal("6.0"),
        "US-WA": Decimal("6.5"),
        "US-IL": Decimal("6.25"),
        "US-PA": Decimal("6.0"),
        "US-OH": Decimal("5.75"),
        "US-GA": Decimal("4.0"),
        "US-NC": Decimal("4.75"),
    }

    # States with no sales tax
    NO_SALES_TAX = {"US-OR", "US-MT", "US-NH", "US-DE", "US-AK"}

    def get_jurisdictions(self) -> list[Jurisdiction]:
        jurisdictions = [
            Jurisdiction(
                code="US",
                name="United States (Federal)",
                jurisdiction_type=JurisdictionType.COUNTRY,
                country="US",
                currency="USD",
            )
        ]
        for state_code, rate in self.STATE_RATES.items():
            state_name = state_code.split("-")[1]
            jurisdictions.append(
                Jurisdiction(
                    code=state_code,
                    name=f"{state_name} State",
                    jurisdiction_type=JurisdictionType.STATE,
                    parent_jurisdiction="US",
                    country="US",
                    currency="USD",
                    tax_rates=[
                        TaxRate(
                            tax_type=TaxType.SALES_TAX,
                            rate=rate,
                            effective_from=date(2020, 1, 1),
                        )
                    ],
                    filing_frequency="monthly",
                )
            )
        return jurisdictions

    def determine_tax(
        self,
        transaction: Transaction,
        as_of: date | None = None,
    ) -> list[TaxDetermination]:
        """Apply US sales tax rules.

        Key US rules (simplified):
        - Sales tax is destination-based in most states
        - B2B exemptions vary by state
        - SaaS taxability varies by state
        - Nexus thresholds apply (post-Wayfair: typically $100K or 200 transactions)
        """
        determinations: list[TaxDetermination] = []
        destination = transaction.buyer_jurisdiction or transaction.buyer_country

        if not destination or destination in self.NO_SALES_TAX:
            return determinations

        rate = self.STATE_RATES.get(destination, Decimal("0"))
        if rate == 0:
            return determinations

        rules_applied = [f"Destination-based sourcing: {destination}"]

        # Check exemptions
        if transaction.is_exempt:
            return [
                TaxDetermination(
                    jurisdiction_code=destination,
                    tax_type=TaxType.SALES_TAX,
                    taxable_amount=transaction.net_total,
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    is_exempt=True,
                    exemption_reason=transaction.exemption_reason or "Exemption certificate on file",
                    rules_applied=rules_applied + ["Exemption applied"],
                )
            ]

        tax_amount = (transaction.net_total * rate / 100).quantize(Decimal("0.01"))
        rules_applied.append(f"State rate: {rate}%")

        determinations.append(
            TaxDetermination(
                jurisdiction_code=destination,
                tax_type=TaxType.SALES_TAX,
                taxable_amount=transaction.net_total,
                tax_rate=rate,
                tax_amount=tax_amount,
                rules_applied=rules_applied,
            )
        )

        return determinations

    def get_filing_schema(self, tax_type: TaxType) -> FilingSchema:
        return FilingSchema(
            jurisdiction_code="US",
            tax_type=tax_type,
            form_name="Sales and Use Tax Return",
            boxes=[
                FilingBox(box_number="1", label="Gross Sales", description="Total gross sales"),
                FilingBox(box_number="2", label="Exempt Sales", description="Non-taxable sales"),
                FilingBox(
                    box_number="3",
                    label="Taxable Sales",
                    description="Net taxable sales",
                    calculation="box_1 - box_2",
                ),
                FilingBox(
                    box_number="4",
                    label="Tax Due",
                    description="Sales tax due",
                    calculation="box_3 * rate",
                ),
            ],
            filing_frequency="monthly",
            electronic_filing_required=True,
        )

    def get_penalty_rules(self) -> list[PenaltyRule]:
        return [
            PenaltyRule(
                jurisdiction_code="US",
                penalty_type="late_filing",
                rate=Decimal("5"),
                description="5% per month, up to 25%",
                max_amount=Decimal("25"),
                grace_period_days=0,
            ),
            PenaltyRule(
                jurisdiction_code="US",
                penalty_type="late_payment",
                rate=Decimal("0.5"),
                description="0.5% per month, up to 25%",
                max_amount=Decimal("25"),
                grace_period_days=0,
            ),
        ]

    def get_registration_threshold(self, tax_type: TaxType) -> Decimal:
        """Post-Wayfair economic nexus threshold (simplified to $100K)."""
        return Decimal("100000")

    def get_filing_deadline(self, tax_type: TaxType, period_end: date) -> date:
        """Most states: 20th of the month following the period."""
        next_month = period_end.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=20)
