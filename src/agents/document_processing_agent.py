"""Document Processing Agent.

Extracts structured financial data from tax documents stored in the
workflow state (W-2, 1099-INT, 1099-DIV, 1099-NEC, 1099-B, 1099-R,
1098, Schedule K-1, etc.) and aggregates the values into the
IncomeRecord and DeductionRecord on the state.

In a production system the agent would call an LLM or OCR service to
parse raw document text; here it reads the structured `data` dict
already attached to each TaxDocument, enabling deterministic testing
without external dependencies.
"""

from __future__ import annotations

from src.agents.base_agent import AgentResult, BaseAgent
from src.models.tax_models import (
    DocumentType,
    TaxDocument,
    WorkflowState,
    WorkflowStatus,
)


class DocumentProcessingAgent(BaseAgent):
    """Aggregates income and deduction data from all attached documents."""

    def __init__(self) -> None:
        super().__init__("DocumentProcessingAgent")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_w2(self, doc: TaxDocument, state: WorkflowState) -> None:
        wages = float(doc.data.get("wages", 0))
        withheld = float(doc.data.get("federal_tax_withheld", 0))
        state.income.wages += wages
        # Accumulate withheld taxes; stored in calculation placeholder via state.
        state.add_message(
            self.name,
            f"W-2 from '{doc.issuer}': wages={wages:,.2f}, "
            f"federal_withheld={withheld:,.2f}.",
        )
        state.taxes_withheld += withheld

    def _process_1099_nec(self, doc: TaxDocument, state: WorkflowState) -> None:
        amount = float(doc.data.get("nonemployee_compensation", 0))
        state.income.self_employment += amount
        state.add_message(
            self.name,
            f"1099-NEC from '{doc.issuer}': self-employment income={amount:,.2f}.",
        )

    def _process_1099_int(self, doc: TaxDocument, state: WorkflowState) -> None:
        amount = float(doc.data.get("interest_income", 0))
        state.income.interest += amount
        state.add_message(
            self.name, f"1099-INT from '{doc.issuer}': interest={amount:,.2f}."
        )

    def _process_1099_div(self, doc: TaxDocument, state: WorkflowState) -> None:
        ordinary = float(doc.data.get("ordinary_dividends", 0))
        qualified = float(doc.data.get("qualified_dividends", 0))
        state.income.dividends += ordinary
        state.add_message(
            self.name,
            f"1099-DIV from '{doc.issuer}': ordinary={ordinary:,.2f}, "
            f"qualified={qualified:,.2f}.",
        )

    def _process_1099_b(self, doc: TaxDocument, state: WorkflowState) -> None:
        gains = float(doc.data.get("net_gain_loss", 0))
        state.income.capital_gains += gains
        state.add_message(
            self.name,
            f"1099-B from '{doc.issuer}': net capital gain/loss={gains:,.2f}.",
        )

    def _process_1099_r(self, doc: TaxDocument, state: WorkflowState) -> None:
        distribution = float(doc.data.get("gross_distribution", 0))
        state.income.retirement += distribution
        state.add_message(
            self.name,
            f"1099-R from '{doc.issuer}': retirement distribution={distribution:,.2f}.",
        )

    def _process_1098(self, doc: TaxDocument, state: WorkflowState) -> None:
        interest = float(doc.data.get("mortgage_interest", 0))
        state.deductions.mortgage_interest += interest
        state.add_message(
            self.name,
            f"1098 from '{doc.issuer}': mortgage interest={interest:,.2f}.",
        )

    def _process_k1(self, doc: TaxDocument, state: WorkflowState) -> None:
        ordinary_income = float(doc.data.get("ordinary_income", 0))
        state.income.other += ordinary_income
        state.add_message(
            self.name,
            f"Schedule K-1 from '{doc.issuer}': ordinary income={ordinary_income:,.2f}.",
        )

    _HANDLERS = {
        DocumentType.W2: _process_w2,
        DocumentType.FORM_1099_NEC: _process_1099_nec,
        DocumentType.FORM_1099_INT: _process_1099_int,
        DocumentType.FORM_1099_DIV: _process_1099_div,
        DocumentType.FORM_1099_B: _process_1099_b,
        DocumentType.FORM_1099_R: _process_1099_r,
        DocumentType.FORM_1098: _process_1098,
        DocumentType.SCHEDULE_K1: _process_k1,
    }

    # ------------------------------------------------------------------

    def _execute(self, state: WorkflowState) -> AgentResult:
        state.status = WorkflowStatus.DOCUMENT_PROCESSING

        if not state.documents:
            return AgentResult.fail(
                "No tax documents found. Please attach at least one document "
                "(e.g. W-2, 1099) before proceeding."
            )

        processed = 0
        skipped = 0
        for doc in state.documents:
            handler = self._HANDLERS.get(doc.document_type)
            if handler:
                handler(self, doc, state)
                processed += 1
            else:
                state.add_message(
                    self.name,
                    f"No handler for document type '{doc.document_type}'; skipping.",
                )
                skipped += 1

        state.status = WorkflowStatus.CALCULATING
        return AgentResult.ok(
            message=(
                f"Processed {processed} document(s), skipped {skipped}. "
                f"Gross income: ${state.income.total_gross_income:,.2f}."
            )
        )
