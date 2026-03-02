"""Integration tests for the full tax workflow."""

import pytest

from src.models.tax_models import (
    DeductionRecord,
    DocumentType,
    FilingStatus,
    IncomeRecord,
    TaxDocument,
    UserProfile,
    WorkflowStatus,
)
from src.workflows.tax_workflow import TaxWorkflowOrchestrator


def _make_profile(**kwargs) -> UserProfile:
    defaults = dict(
        first_name="Alice",
        last_name="Smith",
        filing_status=FilingStatus.SINGLE,
        tax_year=2024,
        state="NY",
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _w2(wages: float, withheld: float, issuer: str = "ACME Corp") -> TaxDocument:
    return TaxDocument(
        document_type=DocumentType.W2,
        issuer=issuer,
        data={"wages": wages, "federal_tax_withheld": withheld},
    )


class TestEndToEndWorkflow:
    def setup_method(self):
        self.orchestrator = TaxWorkflowOrchestrator()

    def test_simple_w2_workflow_completes(self):
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=60_000, withheld=9_000)],
        )
        assert state.status == WorkflowStatus.COMPLETED
        assert state.filing_package is not None
        assert state.filing_package.filing_confirmation.startswith("TAXINFRA-")

    def test_missing_profile_fails_at_data_collection(self):
        profile = UserProfile()  # empty profile
        state = self.orchestrator.run_from_inputs(
            user_profile=profile,
            documents=[_w2(wages=50_000, withheld=8_000)],
        )
        assert state.status == WorkflowStatus.FAILED
        assert any("missing" in e.lower() for e in state.errors)

    def test_missing_documents_fails_at_document_processing(self):
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[],  # no docs
        )
        assert state.status == WorkflowStatus.FAILED

    def test_multiple_document_types_workflow(self):
        docs = [
            _w2(wages=80_000, withheld=12_000),
            TaxDocument(
                document_type=DocumentType.FORM_1099_INT,
                issuer="Bank",
                data={"interest_income": 500},
            ),
            TaxDocument(
                document_type=DocumentType.FORM_1099_DIV,
                issuer="Brokerage",
                data={"ordinary_dividends": 1_000, "qualified_dividends": 600},
            ),
            TaxDocument(
                document_type=DocumentType.FORM_1098,
                issuer="Mortgage Lender",
                data={"mortgage_interest": 10_000},
            ),
        ]
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=docs,
        )
        assert state.status == WorkflowStatus.COMPLETED
        assert state.income.wages == 80_000
        assert state.income.interest == 500
        assert state.income.dividends == 1_000
        assert state.deductions.mortgage_interest == 10_000

    def test_married_filing_jointly_higher_standard_deduction(self):
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(
                filing_status=FilingStatus.MARRIED_FILING_JOINTLY
            ),
            documents=[_w2(wages=100_000, withheld=15_000)],
        )
        assert state.status == WorkflowStatus.COMPLETED
        calc = state.calculation
        assert calc.standard_deduction == 29_200

    def test_workflow_ids_are_unique(self):
        s1 = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=50_000, withheld=7_000)],
        )
        s2 = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=50_000, withheld=7_000)],
        )
        assert s1.workflow_id != s2.workflow_id

    def test_refund_amount_consistent(self):
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=60_000, withheld=10_000)],
        )
        calc = state.calculation
        # refund_or_owed = withheld - net_tax
        net_tax = calc.tax_liability - calc.credits
        expected = calc.taxes_withheld - max(0, net_tax)
        assert calc.refund_or_owed == pytest.approx(expected, abs=0.01)

    def test_self_employment_deduction_reduces_agi(self):
        """SE earners should get an above-the-line deduction for 50% of SE tax."""
        docs = [
            TaxDocument(
                document_type=DocumentType.FORM_1099_NEC,
                issuer="Client LLC",
                data={"nonemployee_compensation": 50_000},
            )
        ]
        state = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=docs,
        )
        assert state.status == WorkflowStatus.COMPLETED
        # AGI should be less than gross income due to SE deduction
        assert state.calculation.adjusted_gross_income < state.calculation.gross_income

    def test_child_tax_credit_reduces_liability(self):
        state_no_ctc = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=60_000, withheld=5_000)],
            deductions=DeductionRecord(child_tax_credit_eligible_children=0),
        )
        state_ctc = self.orchestrator.run_from_inputs(
            user_profile=_make_profile(),
            documents=[_w2(wages=60_000, withheld=5_000)],
            deductions=DeductionRecord(child_tax_credit_eligible_children=2),
        )
        # Refund with CTC should be higher (or owed less)
        assert state_ctc.calculation.refund_or_owed > state_no_ctc.calculation.refund_or_owed
