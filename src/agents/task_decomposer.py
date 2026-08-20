"""
Task Decomposer Agent.

Responsibilities:
- Break analyzed requirements into structured, actionable tasks
- Define dependencies between tasks (DAG)
- Determine execution sequence with parallelizable layers
- Assign tasks to appropriate specialist agents

Uses Claude LLM for dynamic task decomposition for ANY requirement.
"""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import (
    AnalyzedRequirement,
    Task,
    TaskGraph,
    TaskStatus,
)
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior engineering manager decomposing a software requirement into an executable task plan.

You must output a JSON object with this structure:
{
  "tasks": [
    {
      "id": "task-001",
      "name": "Short task name",
      "description": "Detailed description of what this task produces",
      "agent": "architect | code_generator | test_generator | validator",
      "dependencies": []
    },
    {
      "id": "task-002",
      "name": "...",
      "description": "...",
      "agent": "...",
      "dependencies": ["task-001"]
    }
  ]
}

Rules:
- Generate 8-12 tasks covering the full SDLC
- First task(s) should have NO dependencies (root of the DAG)
- Tasks should form a DAG (directed acyclic graph), NOT a simple linear chain
- Some tasks should be parallelizable (same dependencies = same layer)
- Available agents: "architect" (design), "code_generator" (implementation), "test_generator" (tests), "validator" (validation/risk)
- The LAST task should always be validation by the "validator" agent
- Dependencies reference task IDs that must complete before this task starts
- Task flow should follow: Architecture → Data Models + API Design → Implementation → Tests → Validation
- Ensure cross-step coordination: outputs from architecture feed into code generation, etc.
"""


class TaskDecomposerAgent(BaseAgent):
    """Decomposes requirements into a dependency-aware task graph using LLM."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="task_decomposer",
            description="Breaks requirements into structured tasks with dependencies",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Decompose an analyzed requirement into a task graph.

        Inputs:
            - analyzed_requirement: AnalyzedRequirement instance

        Returns:
            - task_graph: TaskGraph with ordered, dependency-aware tasks
        """
        analyzed_req: AnalyzedRequirement = inputs["analyzed_requirement"]

        self._logger.info(f"Decomposing requirement: {analyzed_req.intent[:80]}...")

        user_prompt = (
            f"Requirement: {analyzed_req.intent}\n\n"
            f"Functional Requirements:\n"
            + "\n".join(f"- {fr}" for fr in analyzed_req.functional_requirements)
            + f"\n\nNon-Functional Requirements:\n"
            + "\n".join(f"- {nfr}" for nfr in analyzed_req.non_functional_requirements)
            + f"\n\nNormalized Problem: {analyzed_req.normalized_problem}"
            + f"\n\nAssumptions:\n"
            + "\n".join(f"- {a}" for a in analyzed_req.assumptions)
        )

        result = self._llm.ask_json(SYSTEM_PROMPT, user_prompt, max_tokens=2048)

        # Parse tasks from LLM response
        if "raw_response" in result:
            self._logger.warning(f"LLM returned unparseable response, using fallback tasks")
            result = {"tasks": self._fallback_tasks()}

        tasks = []
        for task_data in result.get("tasks", []):
            tasks.append(Task(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data["description"],
                agent=task_data["agent"],
                dependencies=task_data.get("dependencies", []),
                status=TaskStatus.PENDING,
            ))

        # Compute execution order (topological layers)
        execution_order = self._compute_execution_order(tasks)

        task_graph = TaskGraph(tasks=tasks, execution_order=execution_order)

        self._logger.info(
            f"Generated {len(tasks)} tasks in {len(execution_order)} execution layers"
        )

        return {"task_graph": task_graph}

    def _compute_execution_order(self, tasks: list[Task]) -> list[list[str]]:
        """
        Compute topological execution layers.
        Tasks in the same layer can be executed in parallel.
        """
        task_map = {t.id: t for t in tasks}
        completed = set()
        layers = []
        remaining = set(t.id for t in tasks)

        while remaining:
            ready = [
                tid for tid in remaining
                if all(dep in completed for dep in task_map[tid].dependencies)
            ]

            if not ready:
                # Break circular dependency by forcing one task
                self._logger.warning("Circular dependency detected, forcing progress")
                ready = [next(iter(remaining))]

            layers.append(ready)
            completed.update(ready)
            remaining -= set(ready)

        return layers

    def _fallback_tasks(self) -> list[dict]:
        """Return a sensible default task breakdown if LLM response is unparseable."""
        return [
            {"id": "task-001", "name": "Design System Architecture", "description": "Design components, APIs, data models, and technology stack", "agent": "architect", "dependencies": []},
            {"id": "task-002", "name": "Generate Code", "description": "Implement the service code based on architecture", "agent": "code_generator", "dependencies": ["task-001"]},
            {"id": "task-003", "name": "Generate Tests", "description": "Create unit and integration tests", "agent": "test_generator", "dependencies": ["task-001", "task-002"]},
            {"id": "task-004", "name": "Validate and Assess Risks", "description": "Risk assessment, trade-offs, and guardrails", "agent": "validator", "dependencies": ["task-002", "task-003"]},
        ]
