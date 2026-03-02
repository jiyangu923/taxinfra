"""Germany tax module — Umsatzsteuer (VAT)."""

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


class DEModule(CountryModule):
    country_code = "DE"
    country_name = "Germany"
    currency = "EUR"
    tax_types = [TaxType.VAT]

    STANDARD_RATE = Decimal("19")
    REDUCED_RATE = Decimal("7")

    def get_jurisdictions(self) -> list[Jurisdiction]:
        return [
            Jurisdiction(
                code="DE",
                name="Germany",
                jurisdiction_type=JurisdictionType.COUNTRY,
                country="DE",
                currency="EUR",
                tax_rates=[
                    TaxRate(
                        tax_type=TaxType.VAT,
                        rate=self.STANDARD_RATE,
                        reduced_rate=self.REDUCED_RATE,
                        zero_rate_applicable=False,
                        effective_from=date(2021, 1, 1),
                        description="German USt standard rate",
                    ),
                ],
                filing_frequency="monthly",
                filing_deadline_days=10,
                payment_deadline_days=10,
                registration_threshold=Decimal("0"),  # No threshold for B2B
                registration_threshold_currency="EUR",
                e_invoicing_required=True,
                e_invoicing_standard="xrechnung",
                reverse_charge_applicable=True,
                real_time_reporting=False,
            )
        ]

    def determine_tax(
        self,
        transaction: Transaction,
        as_of: date | None = None,
    ) -> list[TaxDetermination]:
        """Apply German VAT (Umsatzsteuer) rules.

        Key German VAT rules (simplified):
        - Standard rate: 19%
        - Reduced rate: 7% (food, books, public transport, hotels)
        - Intra-EU B2B: reverse charge
        - Exports outside EU: zero-rated (steuerfreie Ausfuhrlieferung)
        - Kleinunternehmerregelung: small business exemption up to €22,000
        - E-invoicing: XRechnung for B2G, increasingly for B2B
        """
        rules_applied: list[str] = []

        # EU export: zero-rated
        if transaction.is_cross_border and transaction.seller_country == "DE":
            if transaction.is_b2b:
                rules_applied.append("Innergemeinschaftliche Lieferung / Export — steuerfrei")
            else:
                rules_applied.append("Ausfuhrlieferung — steuerfrei (§ 4 Nr. 1a UStG)")
            return [
                TaxDetermination(
                    jurisdiction_code="DE",
                    tax_type=TaxType.VAT,
                    taxable_amount=transaction.net_total,
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    rules_applied=rules_applied,
                )
            ]

        # Reverse charge on imports
        if (
            transaction.is_cross_border
            and transaction.is_b2b
            and transaction.buyer_country == "DE"
        ):
            rules_applied.append("Reverse-Charge-Verfahren (§ 13b UStG)")
            return [
                TaxDetermination(
                    jurisdiction_code="DE",
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
            rules_applied.append(f"Steuerbefreiung: {transaction.exemption_reason}")
            return [
                TaxDetermination(
                    jurisdiction_code="DE",
                    tax_type=TaxType.VAT,
                    taxable_amount=transaction.net_total,
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    is_exempt=True,
                    exemption_reason=transaction.exemption_reason,
                    rules_applied=rules_applied,
                )
            ]

        # Standard domestic rate
        rules_applied.append(f"Regelsteuersatz: {self.STANDARD_RATE}% (§ 12 Abs. 1 UStG)")
        tax_amount = (transaction.net_total * self.STANDARD_RATE / 100).quantize(Decimal("0.01"))

        return [
            TaxDetermination(
                jurisdiction_code="DE",
                tax_type=TaxType.VAT,
                taxable_amount=transaction.net_total,
                tax_rate=self.STANDARD_RATE,
                tax_amount=tax_amount,
                rules_applied=rules_applied,
            )
        ]

    def get_filing_schema(self, tax_type: TaxType) -> FilingSchema:
        """German Umsatzsteuer-Voranmeldung (UStVA)."""
        return FilingSchema(
            jurisdiction_code="DE",
            tax_type=TaxType.VAT,
            form_name="Umsatzsteuer-Voranmeldung (UStVA)",
            version="2024",
            boxes=[
                FilingBox(box_number="81", label="Steuerpflichtige Umsätze 19%", description="Taxable supplies at 19%"),
                FilingBox(box_number="86", label="Steuerpflichtige Umsätze 7%", description="Taxable supplies at 7%"),
                FilingBox(box_number="41", label="Innergemeinschaftliche Lieferungen", description="Intra-EU supplies"),
                FilingBox(box_number="21", label="Nicht steuerbare Umsätze", description="Non-taxable supplies (exports)"),
                FilingBox(box_number="46", label="Reverse-Charge-Leistungen", description="Reverse charge services received"),
                FilingBox(box_number="66", label="Vorsteuerbeträge", description="Input VAT deductible"),
                FilingBox(box_number="83", label="Verbleibende Umsatzsteuer-Vorauszahlung", description="Net VAT payable", calculation="output_vat - box_66"),
            ],
            filing_frequency="monthly",
            electronic_filing_required=True,
        )

    def get_penalty_rules(self) -> list[PenaltyRule]:
        return [
            PenaltyRule(
                jurisdiction_code="DE",
                penalty_type="late_filing",
                rate=Decimal("0.25"),
                description="Verspätungszuschlag: 0.25% of tax per month, min €25",
                grace_period_days=14,
            ),
            PenaltyRule(
                jurisdiction_code="DE",
                penalty_type="late_payment",
                rate=Decimal("1"),
                description="Säumniszuschlag: 1% per month of outstanding tax",
                grace_period_days=3,
            ),
        ]

    def get_registration_threshold(self, tax_type: TaxType) -> Decimal:
        """Germany: No VAT registration threshold for regular businesses.

        Kleinunternehmerregelung threshold is €22,000 but that's an opt-out, not registration.
        """
        return Decimal("0")

    def get_filing_deadline(self, tax_type: TaxType, period_end: date) -> date:
        """Germany: 10th of the month following the period."""
        next_month = period_end.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=10)
