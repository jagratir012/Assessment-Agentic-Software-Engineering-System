"""
Base Agent class providing common functionality for all specialized agents.
Implements controlled autonomy: agents execute independently but log decisions
for human review.
"""

from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionLog:
    """Records agent execution for audit and human oversight."""
    agent_name: str
    action: str
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    status: str = "success"
    error: str | None = None
    decisions: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class BaseAgent(ABC):
    """
    Abstract base for all agents in the system.

    Each agent:
    - Has a clear responsibility (single concern)
    - Logs all decisions for human oversight
    - Supports retry with exponential backoff
    - Can report its confidence level
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.execution_logs: list[AgentExecutionLog] = []
        self._logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent's primary task.

        Args:
            inputs: Dictionary of input data needed by this agent.

        Returns:
            Dictionary of outputs produced by this agent.
        """
        pass

    def run(self, inputs: dict[str, Any], max_retries: int = 2) -> dict[str, Any]:
        """
        Run the agent with retry logic and execution logging.

        Implements error handling and recovery: retries with exponential backoff,
        logs all attempts, and raises on final failure.
        """
        last_error = None

        for attempt in range(max_retries + 1):
            start_time = time.time()
            log_entry = AgentExecutionLog(
                agent_name=self.name,
                action="execute",
                inputs={k: str(v)[:200] for k, v in inputs.items()},  # Truncate for logging
            )

            try:
                self._logger.info(
                    f"[{self.name}] Attempt {attempt + 1}/{max_retries + 1} - Starting execution"
                )
                result = self.execute(inputs)
                log_entry.outputs = {k: str(v)[:200] for k, v in result.items()}
                log_entry.duration_ms = (time.time() - start_time) * 1000
                log_entry.status = "success"
                self.execution_logs.append(log_entry)

                self._logger.info(
                    f"[{self.name}] Completed in {log_entry.duration_ms:.1f}ms"
                )
                return result

            except Exception as e:
                last_error = e
                log_entry.status = "error"
                log_entry.error = str(e)
                log_entry.duration_ms = (time.time() - start_time) * 1000
                self.execution_logs.append(log_entry)

                self._logger.warning(
                    f"[{self.name}] Attempt {attempt + 1} failed: {e}"
                )

                if attempt < max_retries:
                    backoff = 2 ** attempt * 0.5  # 0.5s, 1s, 2s...
                    self._logger.info(f"[{self.name}] Retrying in {backoff}s...")
                    time.sleep(backoff)

        # All retries exhausted
        self._logger.error(f"[{self.name}] All retries exhausted. Final error: {last_error}")
        raise RuntimeError(
            f"Agent '{self.name}' failed after {max_retries + 1} attempts: {last_error}"
        )

    def get_execution_history(self) -> list[dict]:
        """Return execution history for human review (controlled autonomy)."""
        return [
            {
                "agent": log.agent_name,
                "action": log.action,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "error": log.error,
                "decisions": log.decisions,
            }
            for log in self.execution_logs
        ]
