"""Data Collection Agent.

Gathers the minimum necessary personal and financial details from the
user profile already stored in the workflow state and validates them.
In a production system this agent would interact with a conversational
LLM to fill gaps; here it validates completeness and applies sensible
defaults so the rest of the pipeline can run autonomously.
"""

from __future__ import annotations

from src.agents.base_agent import AgentResult, BaseAgent
from src.models.tax_models import FilingStatus, UserProfile, WorkflowState, WorkflowStatus


_REQUIRED_FIELDS: list[str] = [
    "first_name",
    "last_name",
    "filing_status",
    "tax_year",
    "state",
]

_DEFAULT_FILING_STATUS = FilingStatus.SINGLE


class DataCollectionAgent(BaseAgent):
    """Validates and normalises user-profile data for the tax workflow.

    The agent:
    1. Checks required fields and applies defaults where appropriate.
    2. Normalises state code to upper-case.
    3. Infers filing status when omitted.
    4. Advances the workflow status to DOCUMENT_PROCESSING on success.
    """

    def __init__(self) -> None:
        super().__init__("DataCollectionAgent")

    def _execute(self, state: WorkflowState) -> AgentResult:
        state.status = WorkflowStatus.DATA_COLLECTION
        profile = state.user_profile

        # Apply defaults for fields that have safe fallback values.
        if not profile.filing_status:
            profile.filing_status = _DEFAULT_FILING_STATUS
            state.add_message(
                self.name,
                f"Filing status defaulted to '{_DEFAULT_FILING_STATUS.value}'.",
            )

        if profile.state:
            profile.state = profile.state.upper()

        # Validate required fields.
        missing = [
            field
            for field in _REQUIRED_FIELDS
            if not getattr(profile, field, None)
        ]
        if missing:
            return AgentResult.fail(
                f"Missing required profile fields: {', '.join(missing)}. "
                "Please provide this information to proceed."
            )

        state.add_message(
            self.name,
            f"Profile validated for {profile.first_name} {profile.last_name} "
            f"(TY {profile.tax_year}, {profile.filing_status.value}, {profile.state}).",
        )
        state.status = WorkflowStatus.DOCUMENT_PROCESSING
        return AgentResult.ok(
            data=profile,
            message="Data collection and validation complete.",
        )
