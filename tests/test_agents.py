"""Tests for individual tax agents."""

import pytest

from src.agents.data_collection_agent import DataCollectionAgent
from src.agents.document_processing_agent import DocumentProcessingAgent
from src.agents.filing_agent import FilingAgent
from src.agents.tax_calculation_agent import TaxCalculationAgent
from src.models.tax_models import (
    DeductionRecord,
    DocumentType,
    FilingStatus,
    IncomeRecord,
    TaxDocument,
    UserProfile,
    WorkflowState,
    WorkflowStatus,
)


def _base_profile(**kwargs) -> UserProfile:
    defaults = dict(
        first_name="Jane",
        last_name="Doe",
        filing_status=FilingStatus.SINGLE,
        tax_year=2024,
        state="CA",
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _base_state(**kwargs) -> WorkflowState:
    return WorkflowState(
        workflow_id="test-wf",
        user_profile=_base_profile(**kwargs),
    )


# ---------------------------------------------------------------------------
# DataCollectionAgent
# ---------------------------------------------------------------------------


class TestDataCollectionAgent:
    def setup_method(self):
        self.agent = DataCollectionAgent()

    def test_valid_profile_succeeds(self):
        state = _base_state()
        result = self.agent.run(state)
        assert result.success
        assert state.status == WorkflowStatus.DOCUMENT_PROCESSING

    def test_state_normalised_to_uppercase(self):
        state = _base_state(state="ca")
        self.agent.run(state)
        assert state.user_profile.state == "CA"

    def test_missing_first_name_fails(self):
        state = _base_state(first_name="")
        result = self.agent.run(state)
        assert not result.success
        assert "first_name" in result.message

    def test_missing_state_fails(self):
        state = _base_state(state="")
        result = self.agent.run(state)
        assert not result.success
        assert "state" in result.message

    def test_default_filing_status_applied(self):
        profile = UserProfile(
            first_name="John",
            last_name="Smith",
            tax_year=2024,
            state="TX",
        )
        # FilingStatus defaults in Pydantic to SINGLE; override to test message path
        profile.filing_status = FilingStatus.SINGLE
        state = WorkflowState(workflow_id="def-fs", user_profile=profile)
        result = self.agent.run(state)
        assert result.success


# ---------------------------------------------------------------------------
# DocumentProcessingAgent
# ---------------------------------------------------------------------------


class TestDocumentProcessingAgent:
    def setup_method(self):
        self.agent = DocumentProcessingAgent()

    def _state_with_docs(self, *docs: TaxDocument) -> WorkflowState:
        state = _base_state()
        state.status = WorkflowStatus.DOCUMENT_PROCESSING
        state.documents = list(docs)
        return state

    def test_no_documents_fails(self):
        state = _base_state()
        result = self.agent.run(state)
        assert not result.success

    def test_w2_adds_wages(self):
        doc = TaxDocument(
            document_type=DocumentType.W2,
            issuer="ACME Corp",
            data={"wages": 75_000, "federal_tax_withheld": 10_000},
        )
        state = self._state_with_docs(doc)
        result = self.agent.run(state)
        assert result.success
        assert state.income.wages == 75_000
        assert state.taxes_withheld == 10_000

    def test_multiple_documents_accumulated(self):
        w2 = TaxDocument(
            document_type=DocumentType.W2,
            issuer="Corp A",
            data={"wages": 50_000, "federal_tax_withheld": 8_000},
        )
        int_doc = TaxDocument(
            document_type=DocumentType.FORM_1099_INT,
            issuer="Big Bank",
            data={"interest_income": 500},
        )
        div_doc = TaxDocument(
            document_type=DocumentType.FORM_1099_DIV,
            issuer="Brokerage",
            data={"ordinary_dividends": 1_200, "qualified_dividends": 800},
        )
        state = self._state_with_docs(w2, int_doc, div_doc)
        result = self.agent.run(state)
        assert result.success
        assert state.income.wages == 50_000
        assert state.income.interest == 500
        assert state.income.dividends == 1_200

    def test_1099_nec_self_employment(self):
        doc = TaxDocument(
            document_type=DocumentType.FORM_1099_NEC,
            issuer="Client",
            data={"nonemployee_compensation": 20_000},
        )
        state = self._state_with_docs(doc)
        self.agent.run(state)
        assert state.income.self_employment == 20_000

    def test_1098_adds_mortgage_deduction(self):
        doc = TaxDocument(
            document_type=DocumentType.FORM_1098,
            issuer="Mortgage Co",
            data={"mortgage_interest": 9_500},
        )
        state = self._state_with_docs(doc)
        self.agent.run(state)
        assert state.deductions.mortgage_interest == 9_500

    def test_unknown_document_type_skipped(self):
        doc = TaxDocument(
            document_type=DocumentType.OTHER,
            issuer="Mystery",
            data={},
        )
        state = self._state_with_docs(doc)
        result = self.agent.run(state)
        # Should succeed (skipped, not failed) and income unchanged
        assert result.success
        assert state.income.total_gross_income == 0


# ---------------------------------------------------------------------------
# TaxCalculationAgent
# ---------------------------------------------------------------------------


class TestTaxCalculationAgent:
    def setup_method(self):
        self.agent = TaxCalculationAgent()

    def _state_with_income(self, wages: float, withheld: float = 0) -> WorkflowState:
        state = _base_state()
        state.status = WorkflowStatus.CALCULATING
        state.income = IncomeRecord(wages=wages)
        state.taxes_withheld = withheld
        return state

    def test_single_standard_deduction_used(self):
        # Wages well below itemised threshold → standard deduction should be chosen.
        state = self._state_with_income(wages=50_000)
        result = self.agent.run(state)
        assert result.success
        assert state.calculation is not None
        assert state.calculation.breakdown["used_standard_deduction"] is True

    def test_taxable_income_computed_correctly(self):
        state = self._state_with_income(wages=50_000)
        self.agent.run(state)
        calc = state.calculation
        # AGI = 50_000 (no above-the-line deductions)
        # Standard deduction for SINGLE 2024 = 14_600
        assert calc.adjusted_gross_income == pytest.approx(50_000)
        assert calc.taxable_income == pytest.approx(50_000 - 14_600)

    def test_refund_when_over_withheld(self):
        state = self._state_with_income(wages=50_000, withheld=12_000)
        self.agent.run(state)
        # Tax on ~35_400 taxable income is well under $12k → expect refund
        assert state.calculation.refund_or_owed > 0

    def test_owed_when_under_withheld(self):
        state = self._state_with_income(wages=200_000, withheld=100)
        self.agent.run(state)
        assert state.calculation.refund_or_owed < 0

    def test_child_tax_credit_applied(self):
        state = self._state_with_income(wages=50_000)
        state.deductions = DeductionRecord(child_tax_credit_eligible_children=2)
        self.agent.run(state)
        # 2 children × $2,000 = $4,000 CTC
        assert state.calculation.credits == pytest.approx(4_000)

    def test_effective_rate_between_zero_and_one(self):
        state = self._state_with_income(wages=80_000)
        self.agent.run(state)
        rate = state.calculation.effective_tax_rate
        assert 0 <= rate <= 1

    def test_zero_income_no_tax(self):
        state = self._state_with_income(wages=0)
        self.agent.run(state)
        assert state.calculation.tax_liability == 0
        assert state.calculation.taxable_income == 0

    def test_itemised_deduction_chosen_when_higher(self):
        state = self._state_with_income(wages=200_000)
        # Give large itemised deductions that exceed standard deduction
        state.deductions = DeductionRecord(
            mortgage_interest=20_000,
            charitable_contributions=5_000,
            state_local_taxes=10_000,
        )
        self.agent.run(state)
        assert state.calculation.breakdown["used_standard_deduction"] is False


# ---------------------------------------------------------------------------
# FilingAgent
# ---------------------------------------------------------------------------


class TestFilingAgent:
    def setup_method(self):
        self.agent = FilingAgent()

    def _completed_state(self) -> WorkflowState:
        """Return a state that has passed through all prior agents."""
        from src.workflows.tax_workflow import TaxWorkflowOrchestrator

        orc = TaxWorkflowOrchestrator()
        state = orc.create_workflow(
            user_profile=_base_profile(),
            documents=[
                TaxDocument(
                    document_type=DocumentType.W2,
                    issuer="ACME",
                    data={"wages": 60_000, "federal_tax_withheld": 9_000},
                )
            ],
        )
        # Run only the first three agents to reach REVIEW status
        from src.agents.data_collection_agent import DataCollectionAgent
        from src.agents.document_processing_agent import DocumentProcessingAgent
        from src.agents.tax_calculation_agent import TaxCalculationAgent

        DataCollectionAgent().run(state)
        DocumentProcessingAgent().run(state)
        TaxCalculationAgent().run(state)
        return state

    def test_filing_succeeds(self):
        state = self._completed_state()
        result = self.agent.run(state)
        assert result.success
        assert state.status == WorkflowStatus.COMPLETED
        assert state.filing_package is not None

    def test_confirmation_number_generated(self):
        state = self._completed_state()
        self.agent.run(state)
        confirmation = state.filing_package.filing_confirmation
        assert confirmation.startswith("TAXINFRA-")
        assert len(confirmation) > 10

    def test_filing_fails_without_calculation(self):
        state = _base_state()
        state.documents = [
            TaxDocument(
                document_type=DocumentType.W2,
                issuer="ACME",
                data={"wages": 50_000, "federal_tax_withheld": 5_000},
            )
        ]
        result = self.agent.run(state)
        assert not result.success

    def test_filing_fails_without_documents(self):
        from src.agents.data_collection_agent import DataCollectionAgent
        from src.agents.tax_calculation_agent import TaxCalculationAgent

        state = _base_state()
        state.income = IncomeRecord(wages=50_000)
        state.taxes_withheld = 5_000
        DataCollectionAgent().run(state)
        state.documents = []  # clear documents
        TaxCalculationAgent().run(state)
        result = self.agent.run(state)
        assert not result.success
