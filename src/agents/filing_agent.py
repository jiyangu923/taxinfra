"""Filing Agent.

Assembles the final FilingPackage from the validated workflow state and
produces a filing confirmation.  In a production system this agent
would submit to an e-file gateway or IRS MeF system; here it validates
the package and generates a deterministic confirmation number so the
rest of the pipeline can be tested end-to-end without external calls.
"""

from __future__ import annotations

import hashlib


from src.agents.base_agent import AgentResult, BaseAgent
from src.models.tax_models import FilingPackage, WorkflowState, WorkflowStatus, _utcnow_iso


class FilingAgent(BaseAgent):
    """Assembles and 'submits' the completed tax return."""

    def __init__(self) -> None:
        super().__init__("FilingAgent")

    # ------------------------------------------------------------------

    def _generate_confirmation(self, package: FilingPackage) -> str:
        """Generate a deterministic confirmation number from the package."""
        raw = (
            f"{package.workflow_id}"
            f"{package.user_profile.first_name}"
            f"{package.user_profile.last_name}"
            f"{package.user_profile.tax_year}"
            f"{package.calculation.refund_or_owed:.2f}"
            f"{package.prepared_at}"
        )
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
        return f"TAXINFRA-{digest}"

    def _validate_package(self, state: WorkflowState) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors: list[str] = []
        if not state.user_profile.first_name or not state.user_profile.last_name:
            errors.append("User name is missing from the profile.")
        if state.calculation is None:
            errors.append("Tax calculation has not been completed.")
        if not state.documents:
            errors.append("No source documents are attached.")
        return errors

    # ------------------------------------------------------------------

    def _execute(self, state: WorkflowState) -> AgentResult:
        state.status = WorkflowStatus.FILING

        validation_errors = self._validate_package(state)
        if validation_errors:
            return AgentResult.fail(
                "Filing package validation failed: " + "; ".join(validation_errors)
            )

        assert state.calculation is not None  # guaranteed by validation above

        package = FilingPackage(
            workflow_id=state.workflow_id,
            user_profile=state.user_profile,
            income=state.income,
            deductions=state.deductions,
            calculation=state.calculation,
            documents=state.documents,
            prepared_at=_utcnow_iso(),
        )
        package.filing_confirmation = self._generate_confirmation(package)

        state.filing_package = package
        state.status = WorkflowStatus.COMPLETED

        refund_or_owed = state.calculation.refund_or_owed
        direction = "refund" if refund_or_owed >= 0 else "amount owed"
        return AgentResult.ok(
            data=package,
            message=(
                f"Tax return filed successfully. "
                f"Confirmation: {package.filing_confirmation}. "
                f"Expected {direction}: ${abs(refund_or_owed):,.2f}."
            ),
        )
