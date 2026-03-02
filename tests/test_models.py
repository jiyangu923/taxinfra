"""Tests for tax data models."""

import pytest

from src.models.tax_models import (
    DeductionRecord,
    FilingStatus,
    IncomeRecord,
    TaxDocument,
    DocumentType,
    UserProfile,
    WorkflowState,
    WorkflowStatus,
)


class TestIncomeRecord:
    def test_total_gross_income(self):
        income = IncomeRecord(wages=50_000, interest=500, dividends=1_000)
        assert income.total_gross_income == 51_500

    def test_defaults_to_zero(self):
        income = IncomeRecord()
        assert income.total_gross_income == 0


class TestDeductionRecord:
    def test_salt_cap_applied(self):
        # SALT is capped at $10,000
        deductions = DeductionRecord(state_local_taxes=15_000)
        assert deductions.total_itemized() == 10_000

    def test_itemized_sum(self):
        deductions = DeductionRecord(
            mortgage_interest=8_000,
            charitable_contributions=2_000,
            state_local_taxes=5_000,
        )
        assert deductions.total_itemized() == 15_000


class TestWorkflowState:
    def test_add_message(self):
        state = WorkflowState(workflow_id="test-1")
        state.add_message("TestAgent", "Hello")
        assert len(state.agent_messages) == 1
        assert "TestAgent" in state.agent_messages[0]
        assert "Hello" in state.agent_messages[0]

    def test_add_error(self):
        state = WorkflowState(workflow_id="test-2")
        state.add_error("TestAgent", "Something went wrong")
        assert len(state.errors) == 1
        assert "ERROR" in state.errors[0]

    def test_initial_status(self):
        state = WorkflowState(workflow_id="test-3")
        assert state.status == WorkflowStatus.PENDING
