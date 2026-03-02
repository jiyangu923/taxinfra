"""FastAPI application for the Agentic AI Tax Infrastructure Platform.

Endpoints
---------
POST /workflows/          — Start a new tax workflow
GET  /workflows/{id}      — Get the current state of a workflow
POST /workflows/{id}/run  — Execute (or re-execute) a workflow
GET  /workflows/{id}/result — Get the filing result once completed
GET  /health              — Health check
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.models.tax_models import (
    DeductionRecord,
    DocumentType,
    TaxDocument,
    UserProfile,
    WorkflowState,
    WorkflowStatus,
)
from src.workflows.tax_workflow import TaxWorkflowOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TaxInfra — Agentic AI Tax Platform",
    description=(
        "End-to-end agentic tax workflow platform. "
        "Provide a user profile and tax documents; agents handle the rest."
    ),
    version="1.0.0",
)

# In-memory workflow store (replace with a database in production).
_workflows: dict[str, WorkflowState] = {}
_orchestrator = TaxWorkflowOrchestrator()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateWorkflowRequest(BaseModel):
    user_profile: UserProfile
    documents: list[TaxDocument] = []
    deductions: DeductionRecord = DeductionRecord()


class WorkflowSummaryResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    messages: list[str]
    errors: list[str]


class FilingResultResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    confirmation: str
    refund_or_owed: float
    summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workflows/", response_model=WorkflowSummaryResponse, status_code=201)
def create_workflow(request: CreateWorkflowRequest) -> WorkflowSummaryResponse:
    """Create a new workflow and immediately run all agents."""
    state = _orchestrator.run_from_inputs(
        user_profile=request.user_profile,
        documents=request.documents,
        deductions=request.deductions,
    )
    _workflows[state.workflow_id] = state
    return WorkflowSummaryResponse(
        workflow_id=state.workflow_id,
        status=state.status,
        messages=state.agent_messages,
        errors=state.errors,
    )


@app.get("/workflows/{workflow_id}", response_model=WorkflowSummaryResponse)
def get_workflow(workflow_id: str) -> WorkflowSummaryResponse:
    """Return the current state of a workflow."""
    state = _workflows.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return WorkflowSummaryResponse(
        workflow_id=state.workflow_id,
        status=state.status,
        messages=state.agent_messages,
        errors=state.errors,
    )


@app.get("/workflows/{workflow_id}/result", response_model=FilingResultResponse)
def get_result(workflow_id: str) -> FilingResultResponse:
    """Return the filing result for a completed workflow."""
    state = _workflows.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if state.status != WorkflowStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow is not completed yet (status: {state.status.value}).",
        )
    assert state.filing_package is not None
    calc = state.filing_package.calculation
    return FilingResultResponse(
        workflow_id=workflow_id,
        status=state.status,
        confirmation=state.filing_package.filing_confirmation,
        refund_or_owed=calc.refund_or_owed,
        summary={
            "gross_income": calc.gross_income,
            "adjusted_gross_income": calc.adjusted_gross_income,
            "taxable_income": calc.taxable_income,
            "tax_liability": calc.tax_liability,
            "credits": calc.credits,
            "taxes_withheld": calc.taxes_withheld,
            "effective_tax_rate": calc.effective_tax_rate,
            "marginal_tax_rate": calc.marginal_tax_rate,
            "breakdown": calc.breakdown,
        },
    )
