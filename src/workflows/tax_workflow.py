"""Tax Workflow Orchestrator.

Coordinates the sequential execution of all tax agents to complete an
end-to-end tax workflow with minimal user interaction.  The orchestrator
owns the WorkflowState and drives each agent in the correct order,
stopping early on failure and surfacing actionable error messages.
"""

from __future__ import annotations

import logging
import uuid

from src.agents.data_collection_agent import DataCollectionAgent
from src.agents.document_processing_agent import DocumentProcessingAgent
from src.agents.filing_agent import FilingAgent
from src.agents.tax_calculation_agent import TaxCalculationAgent
from src.models.tax_models import (
    DeductionRecord,
    DocumentType,
    IncomeRecord,
    TaxDocument,
    UserProfile,
    WorkflowState,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


class TaxWorkflowOrchestrator:
    """Drives the full end-to-end tax filing workflow.

    Usage::

        orchestrator = TaxWorkflowOrchestrator()
        state = orchestrator.create_workflow(
            user_profile=UserProfile(...),
            documents=[TaxDocument(...)],
        )
        final_state = orchestrator.run(state)
    """

    def __init__(self) -> None:
        self._agents = [
            DataCollectionAgent(),
            DocumentProcessingAgent(),
            TaxCalculationAgent(),
            FilingAgent(),
        ]

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    def create_workflow(
        self,
        user_profile: UserProfile | None = None,
        documents: list[TaxDocument] | None = None,
        income: IncomeRecord | None = None,
        deductions: DeductionRecord | None = None,
        workflow_id: str | None = None,
    ) -> WorkflowState:
        """Create a new WorkflowState ready for execution."""
        return WorkflowState(
            workflow_id=workflow_id or str(uuid.uuid4()),
            user_profile=user_profile or UserProfile(),
            documents=documents or [],
            income=income or IncomeRecord(),
            deductions=deductions or DeductionRecord(),
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, state: WorkflowState) -> WorkflowState:
        """Execute all agents sequentially and return the final state.

        If any agent fails the workflow is halted and the state's status
        is set to FAILED.  All agent messages and errors are preserved in
        the state for inspection.
        """
        logger.info("Starting workflow '%s'.", state.workflow_id)

        for agent in self._agents:
            result = agent.run(state)
            if not result.success:
                state.status = WorkflowStatus.FAILED
                logger.error(
                    "Workflow '%s' failed at agent '%s': %s",
                    state.workflow_id,
                    agent.name,
                    result.message,
                )
                return state

        logger.info("Workflow '%s' completed successfully.", state.workflow_id)
        return state

    # ------------------------------------------------------------------
    # Convenience: run from raw inputs in one call
    # ------------------------------------------------------------------

    def run_from_inputs(
        self,
        user_profile: UserProfile,
        documents: list[TaxDocument],
        deductions: DeductionRecord | None = None,
    ) -> WorkflowState:
        """Create a workflow and run it immediately."""
        state = self.create_workflow(
            user_profile=user_profile,
            documents=documents,
            deductions=deductions or DeductionRecord(),
        )
        return self.run(state)
