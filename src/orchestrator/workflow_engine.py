"""
Workflow Engine - orchestrates multi-step execution across agents.

Demonstrates:
- Task sequencing and dependency management
- Cross-step coordination (outputs of one step feed into next)
- Error handling and recovery (retry with backoff)
- Parallel task execution within dependency layers
- Controlled autonomy with human review checkpoints
"""

from __future__ import annotations

import logging
import time
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .task_graph import TaskGraph
from ..agents.base_agent import BaseAgent
from ..models.schemas import (
    TaskStatus,
    EngineeringSummary,
    AnalyzedRequirement,
    ArchitectureDesign,
)

logger = logging.getLogger(__name__)
console = Console()


class WorkflowEngine:
    """
    Orchestrates the end-to-end SDLC workflow.
    
    Coordinates multiple agents through a dependency-aware task graph,
    managing data flow between steps and handling failures gracefully.
    """

    def __init__(self, agents: dict[str, BaseAgent]):
        """
        Initialize with a registry of available agents.
        
        Args:
            agents: Map of agent_name -> BaseAgent instance
        """
        self._agents = agents
        self._task_graph: TaskGraph | None = None
        self._context: dict[str, Any] = {}  # Shared context across steps
        self._execution_log: list[dict] = []

    def execute_workflow(self, task_graph_model) -> dict[str, Any]:
        """
        Execute the full workflow through the task graph.
        
        Processes tasks layer by layer, respecting dependencies.
        Tasks in the same layer are conceptually parallelizable.
        
        Returns:
            Aggregated outputs from all completed tasks.
        """
        from ..models.schemas import TaskGraph as TaskGraphModel
        self._task_graph = TaskGraph(task_graph_model)

        console.print(Panel(
            f"[bold green]Starting Workflow Execution[/bold green]\n"
            f"Tasks: {len(self._task_graph.tasks)} | "
            f"Layers: {len(self._task_graph.execution_layers)}",
            title="Orchestrator",
        ))

        layer_num = 0
        while not self._task_graph.is_complete():
            ready_tasks = self._task_graph.get_ready_tasks()
            if not ready_tasks:
                # All remaining tasks are blocked or failed
                break

            layer_num += 1
            console.print(f"\n[bold cyan]═══ Execution Layer {layer_num} ═══[/bold cyan]")
            console.print(f"  Tasks in this layer: {[t.name for t in ready_tasks]}")

            # Execute tasks in this layer (simulated parallel)
            for task in ready_tasks:
                self._execute_task(task)

        # Print completion summary
        self._print_summary()
        return self._context

    def _execute_task(self, task) -> None:
        """Execute a single task, handling errors and retries."""
        agent_name = task.agent

        # Flexible agent matching - handle variations Claude might produce
        agent = self._agents.get(agent_name)
        if not agent:
            # Try common variations
            name_map = {
                "architecture": "architect",
                "design": "architect",
                "system_architect": "architect",
                "coder": "code_generator",
                "code": "code_generator",
                "implementation": "code_generator",
                "developer": "code_generator",
                "testing": "test_generator",
                "test": "test_generator",
                "tester": "test_generator",
                "qa": "test_generator",
                "validation": "validator",
                "risk": "validator",
                "security": "validator",
                "review": "validator",
            }
            mapped = name_map.get(agent_name.lower())
            if mapped:
                agent = self._agents.get(mapped)

        if not agent:
            # Last resort: pick based on task name keywords
            task_lower = task.name.lower() + " " + task.description.lower()
            if any(w in task_lower for w in ["architect", "design", "api contract", "component"]):
                agent = self._agents.get("architect")
            elif any(w in task_lower for w in ["test", "unit", "integration", "coverage"]):
                agent = self._agents.get("test_generator")
            elif any(w in task_lower for w in ["valid", "risk", "assess", "guardrail"]):
                agent = self._agents.get("validator")
            else:
                agent = self._agents.get("code_generator")

        if not agent:
            self._task_graph.mark_failed(task.id, f"No agent found: {agent_name}")
            console.print(f"  [red]✗[/red] No agent for: {task.name} (agent: {agent_name})")
            return

        self._task_graph.mark_in_progress(task.id)

        # Gather inputs from dependency outputs (cross-step coordination)
        task_inputs = self._task_graph.get_outputs_for_task(task.id)
        task_inputs.update(task.inputs)
        task_inputs.update(self._context)

        console.print(f"  [yellow]▶[/yellow] Executing: {task.name} (agent: {agent_name})")
        start_time = time.time()

        try:
            outputs = agent.run(task_inputs, max_retries=task.max_retries)
            elapsed = (time.time() - start_time) * 1000

            # Store outputs for downstream tasks
            self._task_graph.mark_completed(task.id, outputs)
            self._context.update(outputs)

            console.print(
                f"  [green]✓[/green] Completed: {task.name} ({elapsed:.0f}ms)"
            )

            self._execution_log.append({
                "task_id": task.id,
                "task_name": task.name,
                "agent": agent_name,
                "status": "completed",
                "duration_ms": elapsed,
            })

        except RuntimeError as e:
            elapsed = (time.time() - start_time) * 1000
            error_msg = str(e)

            # Check if retry is possible
            if self._task_graph.can_retry(task.id):
                self._task_graph.increment_retry(task.id)
                console.print(
                    f"  [red]✗[/red] Failed: {task.name} - retrying "
                    f"({task.retry_count}/{task.max_retries})"
                )
            else:
                self._task_graph.mark_failed(task.id, error_msg)
                console.print(f"  [red]✗[/red] Failed permanently: {task.name}")

            self._execution_log.append({
                "task_id": task.id,
                "task_name": task.name,
                "agent": agent_name,
                "status": "failed",
                "error": error_msg,
                "duration_ms": elapsed,
            })

    def _print_summary(self) -> None:
        """Print execution summary table."""
        summary = self._task_graph.get_completion_summary()

        table = Table(title="Workflow Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for key, value in summary.items():
            table.add_row(key, str(value))

        console.print(table)

    def get_execution_log(self) -> list[dict]:
        """Return full execution log for audit/review."""
        return self._execution_log

    def get_human_review_summary(self) -> str:
        """
        Generate a human-readable summary for review.
        Supports controlled autonomy: humans validate agent decisions.
        """
        lines = ["=" * 60, "WORKFLOW EXECUTION REPORT (for Human Review)", "=" * 60, ""]

        lines.append(f"Total Tasks: {len(self._execution_log)}")
        completed = sum(1 for e in self._execution_log if e["status"] == "completed")
        failed = sum(1 for e in self._execution_log if e["status"] == "failed")
        lines.append(f"Completed: {completed} | Failed: {failed}")
        lines.append("")

        lines.append("Task Execution Details:")
        lines.append("-" * 40)
        for entry in self._execution_log:
            status_icon = "✓" if entry["status"] == "completed" else "✗"
            lines.append(
                f"  {status_icon} {entry['task_name']} "
                f"[{entry['agent']}] - {entry['duration_ms']:.0f}ms"
            )
            if entry.get("error"):
                lines.append(f"    Error: {entry['error']}")

        lines.append("")
        lines.append("Agent Decision Logs:")
        lines.append("-" * 40)
        for agent in self._agents.values():
            history = agent.get_execution_history()
            if history:
                lines.append(f"  {agent.name}:")
                for entry in history:
                    lines.append(f"    - {entry['action']}: {entry['status']}")

        return "\n".join(lines)
