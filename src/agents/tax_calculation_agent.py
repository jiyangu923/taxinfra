"""Tax Calculation Agent.

Applies current U.S. federal tax rules (tax year 2024) to compute:
- Adjusted Gross Income (AGI)
- Standard vs itemised deduction choice
- Taxable income
- Federal income tax (progressive brackets)
- Child Tax Credit and Earned Income Credit
- Final refund or amount owed

State-level tax is intentionally out of scope for the MVP but the
breakdown dict is structured to accommodate it later.
"""

from __future__ import annotations

from src.agents.base_agent import AgentResult, BaseAgent
from src.models.tax_models import (
    FilingStatus,
    TaxCalculationResult,
    WorkflowState,
    WorkflowStatus,
)

# ---------------------------------------------------------------------------
# 2024 tax parameters
# ---------------------------------------------------------------------------

# Standard deductions (2024)
STANDARD_DEDUCTIONS: dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 14_600,
    FilingStatus.MARRIED_FILING_JOINTLY: 29_200,
    FilingStatus.MARRIED_FILING_SEPARATELY: 14_600,
    FilingStatus.HEAD_OF_HOUSEHOLD: 21_900,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 29_200,
}

# Federal income tax brackets (2024) — list of (upper_limit, rate)
# The last tuple uses float('inf') to catch all income above the penultimate bracket.
TAX_BRACKETS: dict[FilingStatus, list[tuple[float, float]]] = {
    FilingStatus.SINGLE: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_FILING_JOINTLY: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.MARRIED_FILING_SEPARATELY: [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (365_600, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (16_550, 0.10),
        (63_100, 0.12),
        (100_500, 0.22),
        (191_950, 0.24),
        (243_700, 0.32),
        (609_350, 0.35),
        (float("inf"), 0.37),
    ],
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: [
        (23_200, 0.10),
        (94_300, 0.12),
        (201_050, 0.22),
        (383_900, 0.24),
        (487_450, 0.32),
        (731_200, 0.35),
        (float("inf"), 0.37),
    ],
}

# Child Tax Credit (2024)
CHILD_TAX_CREDIT_PER_CHILD = 2_000
CHILD_TAX_CREDIT_PHASE_OUT_THRESHOLD: dict[FilingStatus, float] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.MARRIED_FILING_JOINTLY: 400_000,
    FilingStatus.MARRIED_FILING_SEPARATELY: 200_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: 400_000,
}

# SE tax deduction: 50 % of SE tax (SE tax rate = 15.3 % on net SE income)
SE_TAX_RATE = 0.153
SE_DEDUCTION_RATE = 0.5  # above-the-line deduction


def _compute_brackets(
    taxable_income: float, filing_status: FilingStatus
) -> tuple[float, float, dict[str, float]]:
    """Return (total_tax, marginal_rate, bracket_breakdown)."""
    brackets = TAX_BRACKETS[filing_status]
    total_tax = 0.0
    previous_limit = 0.0
    marginal_rate = 0.0
    breakdown: dict[str, float] = {}

    for limit, rate in brackets:
        if taxable_income <= 0:
            break
        rate_key = f"{int(rate * 100)}%"
        taxable_in_bracket = min(taxable_income, limit - previous_limit)
        tax_in_bracket = taxable_in_bracket * rate
        total_tax += tax_in_bracket
        breakdown[rate_key] = breakdown.get(rate_key, 0) + tax_in_bracket
        marginal_rate = rate
        taxable_income -= taxable_in_bracket
        previous_limit = limit

    return total_tax, marginal_rate, breakdown


class TaxCalculationAgent(BaseAgent):
    """Computes the user's federal tax liability and refund/owed amount."""

    def __init__(self) -> None:
        super().__init__("TaxCalculationAgent")

    def _execute(self, state: WorkflowState) -> AgentResult:
        state.status = WorkflowStatus.CALCULATING
        profile = state.user_profile
        income = state.income
        deductions = state.deductions
        fs = profile.filing_status

        # ----------------------------------------------------------------
        # 1. Gross income
        # ----------------------------------------------------------------
        gross = income.total_gross_income

        # ----------------------------------------------------------------
        # 2. Above-the-line deductions → AGI
        # ----------------------------------------------------------------
        se_tax = income.self_employment * SE_TAX_RATE
        se_deduction = se_tax * SE_DEDUCTION_RATE
        student_loan_deduction = min(deductions.student_loan_interest, 2_500)
        agi = max(0.0, gross - se_deduction - student_loan_deduction)

        # ----------------------------------------------------------------
        # 3. Standard vs itemised deduction
        # ----------------------------------------------------------------
        standard = STANDARD_DEDUCTIONS[fs]
        itemised = deductions.total_itemized()
        use_standard = standard >= itemised
        chosen_deduction = standard if use_standard else itemised

        # ----------------------------------------------------------------
        # 4. Taxable income
        # ----------------------------------------------------------------
        taxable_income = max(0.0, agi - chosen_deduction)

        # ----------------------------------------------------------------
        # 5. Tax liability (progressive brackets)
        # ----------------------------------------------------------------
        tax_liability, marginal_rate, bracket_breakdown = _compute_brackets(
            taxable_income, fs
        )

        # ----------------------------------------------------------------
        # 6. Credits
        # ----------------------------------------------------------------
        credits = 0.0

        # Child Tax Credit
        ctc_threshold = CHILD_TAX_CREDIT_PHASE_OUT_THRESHOLD[fs]
        ctc_full = deductions.child_tax_credit_eligible_children * CHILD_TAX_CREDIT_PER_CHILD
        if agi > ctc_threshold:
            reduction = ((agi - ctc_threshold) / 1_000) * 50
            ctc_full = max(0.0, ctc_full - reduction)
        credits += ctc_full

        # Simplified Earned Income Credit proxy (full EIC table not included).
        if deductions.earned_income_credit_eligible and agi < 59_187:
            credits += min(7_430, agi * 0.45)

        # ----------------------------------------------------------------
        # 7. Taxes withheld (accumulated by document processing agent)
        # ----------------------------------------------------------------
        taxes_withheld = state.taxes_withheld

        # ----------------------------------------------------------------
        # 8. Refund or amount owed
        # ----------------------------------------------------------------
        net_tax = max(0.0, tax_liability - credits)
        refund_or_owed = taxes_withheld - net_tax  # positive = refund

        effective_rate = (net_tax / gross) if gross > 0 else 0.0

        result = TaxCalculationResult(
            tax_year=profile.tax_year,
            filing_status=fs,
            gross_income=gross,
            adjusted_gross_income=agi,
            standard_deduction=standard,
            itemized_deduction=itemised,
            taxable_income=taxable_income,
            tax_liability=tax_liability,
            credits=credits,
            taxes_withheld=taxes_withheld,
            refund_or_owed=refund_or_owed,
            effective_tax_rate=round(effective_rate, 4),
            marginal_tax_rate=marginal_rate,
            breakdown={
                "used_standard_deduction": use_standard,
                "above_the_line_deductions": {
                    "se_deduction": round(se_deduction, 2),
                    "student_loan_interest": round(student_loan_deduction, 2),
                },
                "tax_brackets": bracket_breakdown,
                "credits": {
                    "child_tax_credit": round(ctc_full, 2),
                    "earned_income_credit": round(
                        credits - ctc_full if deductions.earned_income_credit_eligible else 0,
                        2,
                    ),
                },
            },
        )

        state.calculation = result
        state.status = WorkflowStatus.REVIEW

        summary = (
            f"AGI=${agi:,.2f}, taxable income=${taxable_income:,.2f}, "
            f"tax liability=${tax_liability:,.2f}, credits=${credits:,.2f}, "
            f"{'REFUND' if refund_or_owed >= 0 else 'OWED'} ${abs(refund_or_owed):,.2f}."
        )
        return AgentResult.ok(data=result, message=summary)
