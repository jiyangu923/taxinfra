"""Tax data models for the Agentic AI Tax Infrastructure Platform."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with a Z suffix."""
    return datetime.now(timezone.utc).isoformat() + "Z"


class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


class DocumentType(str, Enum):
    W2 = "W-2"
    FORM_1099_NEC = "1099-NEC"
    FORM_1099_INT = "1099-INT"
    FORM_1099_DIV = "1099-DIV"
    FORM_1099_B = "1099-B"
    FORM_1099_R = "1099-R"
    FORM_1098 = "1098"
    SCHEDULE_K1 = "Schedule K-1"
    OTHER = "Other"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    DATA_COLLECTION = "data_collection"
    DOCUMENT_PROCESSING = "document_processing"
    CALCULATING = "calculating"
    REVIEW = "review"
    FILING = "filing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaxDocument(BaseModel):
    """Represents a tax document provided by the user."""

    document_type: DocumentType
    issuer: str = ""
    tax_year: int = Field(default_factory=lambda: datetime.now().year - 1)
    data: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""


class UserProfile(BaseModel):
    """Core user profile collected during data collection."""

    first_name: str = ""
    last_name: str = ""
    ssn_last4: str = ""
    date_of_birth: str = ""
    filing_status: FilingStatus = FilingStatus.SINGLE
    tax_year: int = Field(default_factory=lambda: datetime.now().year - 1)
    address: str = ""
    dependents: int = 0
    state: str = ""


class IncomeRecord(BaseModel):
    """Aggregated income from all sources."""

    wages: float = 0.0
    self_employment: float = 0.0
    interest: float = 0.0
    dividends: float = 0.0
    capital_gains: float = 0.0
    retirement: float = 0.0
    other: float = 0.0

    @property
    def total_gross_income(self) -> float:
        return (
            self.wages
            + self.self_employment
            + self.interest
            + self.dividends
            + self.capital_gains
            + self.retirement
            + self.other
        )


class DeductionRecord(BaseModel):
    """Deductions and credits applicable to the user."""

    mortgage_interest: float = 0.0
    charitable_contributions: float = 0.0
    state_local_taxes: float = 0.0
    medical_expenses: float = 0.0
    student_loan_interest: float = 0.0
    child_tax_credit_eligible_children: int = 0
    earned_income_credit_eligible: bool = False

    def total_itemized(self) -> float:
        return (
            self.mortgage_interest
            + self.charitable_contributions
            + min(self.state_local_taxes, 10_000)  # SALT cap
            + self.medical_expenses
            + self.student_loan_interest
        )


class TaxCalculationResult(BaseModel):
    """Output of the tax calculation agent."""

    tax_year: int
    filing_status: FilingStatus
    gross_income: float
    adjusted_gross_income: float
    standard_deduction: float
    itemized_deduction: float
    taxable_income: float
    tax_liability: float
    credits: float
    taxes_withheld: float
    refund_or_owed: float
    effective_tax_rate: float
    marginal_tax_rate: float
    breakdown: dict[str, Any] = Field(default_factory=dict)


class FilingPackage(BaseModel):
    """Final package assembled by the filing agent."""

    workflow_id: str
    user_profile: UserProfile
    income: IncomeRecord
    deductions: DeductionRecord
    calculation: TaxCalculationResult
    documents: list[TaxDocument] = Field(default_factory=list)
    prepared_at: str = Field(
        default_factory=lambda: _utcnow_iso()
    )
    filing_confirmation: str = ""


class WorkflowState(BaseModel):
    """Tracks the full state of a tax workflow session."""

    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    user_profile: UserProfile = Field(default_factory=UserProfile)
    documents: list[TaxDocument] = Field(default_factory=list)
    income: IncomeRecord = Field(default_factory=IncomeRecord)
    deductions: DeductionRecord = Field(default_factory=DeductionRecord)
    calculation: TaxCalculationResult | None = None
    filing_package: FilingPackage | None = None
    taxes_withheld: float = 0.0
    agent_messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: _utcnow_iso()
    )
    updated_at: str = Field(
        default_factory=lambda: _utcnow_iso()
    )

    def add_message(self, agent: str, message: str) -> None:
        timestamp = _utcnow_iso()
        self.agent_messages.append(f"[{timestamp}] [{agent}] {message}")
        self.updated_at = timestamp

    def add_error(self, agent: str, error: str) -> None:
        timestamp = _utcnow_iso()
        self.errors.append(f"[{timestamp}] [{agent}] ERROR: {error}")
        self.updated_at = timestamp
