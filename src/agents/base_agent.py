"""Base agent framework for the Agentic AI Tax Infrastructure Platform."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.models.tax_models import WorkflowState

logger = logging.getLogger(__name__)


class AgentResult:
    """Encapsulates the outcome of an agent's run."""

    def __init__(self, success: bool, data: Any = None, message: str = "") -> None:
        self.success = success
        self.data = data
        self.message = message

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "AgentResult":
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, message: str, data: Any = None) -> "AgentResult":
        return cls(success=False, data=data, message=message)


class BaseAgent(ABC):
    """Abstract base for all tax workflow agents.

    Each agent operates on a shared WorkflowState, reads the data it
    needs, performs its task autonomously, and writes its output back
    to the state.  Agents should require minimal (or zero) additional
    user input beyond what is already stored in the state.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._logger = logging.getLogger(f"taxinfra.agents.{name}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, state: WorkflowState) -> AgentResult:
        """Execute the agent on the given workflow state.

        Wraps _execute with logging and error handling so subclasses
        only need to implement _execute.
        """
        self._logger.info("Starting agent '%s'", self.name)
        state.add_message(self.name, f"Agent '{self.name}' started.")
        try:
            result = self._execute(state)
        except Exception as exc:  # noqa: BLE001
            msg = f"Unhandled exception: {exc}"
            self._logger.exception(msg)
            state.add_error(self.name, msg)
            return AgentResult.fail(msg)

        if result.success:
            self._logger.info("Agent '%s' completed successfully.", self.name)
            state.add_message(self.name, result.message or "Completed successfully.")
        else:
            self._logger.warning("Agent '%s' failed: %s", self.name, result.message)
            state.add_error(self.name, result.message)

        return result

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _execute(self, state: WorkflowState) -> AgentResult:
        """Perform the agent's core task.

        Must read from *state* and write results back to *state*.
        Returns an AgentResult describing success/failure.
        """
