"""
Task Graph - DAG-based dependency management for workflow orchestration.

Implements topological sorting and parallel execution layer computation.
Demonstrates cross-step coordination, not just sequential execution.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models.schemas import Task, TaskStatus, TaskGraph as TaskGraphModel

logger = logging.getLogger(__name__)


class TaskGraph:
    """
    Manages a directed acyclic graph of tasks.
    Provides dependency resolution, execution ordering, and status tracking.
    """

    def __init__(self, task_graph_model: TaskGraphModel):
        self._model = task_graph_model
        self._tasks: dict[str, Task] = {t.id: t for t in task_graph_model.tasks}
        self._execution_layers = task_graph_model.execution_order

    @property
    def tasks(self) -> dict[str, Task]:
        return self._tasks

    @property
    def execution_layers(self) -> list[list[str]]:
        return self._execution_layers

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks whose dependencies are all completed (ready to execute)."""
        ready = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps_met = all(
                self._tasks[dep].status == TaskStatus.COMPLETED
                for dep in task.dependencies
            )
            if deps_met:
                ready.append(task)
        return ready

    def mark_completed(self, task_id: str, outputs: dict = None) -> None:
        """Mark a task as completed with its outputs."""
        task = self._tasks[task_id]
        task.status = TaskStatus.COMPLETED
        if outputs:
            task.outputs = outputs
        logger.info(f"Task '{task.name}' ({task_id}) completed")

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        task = self._tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error_message = error
        logger.error(f"Task '{task.name}' ({task_id}) failed: {error}")

        # Mark dependent tasks as blocked
        self._propagate_failure(task_id)

    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in progress."""
        self._tasks[task_id].status = TaskStatus.IN_PROGRESS

    def can_retry(self, task_id: str) -> bool:
        """Check if a failed task can be retried."""
        task = self._tasks[task_id]
        return task.retry_count < task.max_retries

    def increment_retry(self, task_id: str) -> None:
        """Increment retry count for a task."""
        self._tasks[task_id].retry_count += 1
        self._tasks[task_id].status = TaskStatus.PENDING

    def is_complete(self) -> bool:
        """Check if all tasks are completed (or blocked/failed)."""
        terminal_states = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED}
        return all(t.status in terminal_states for t in self._tasks.values())

    def get_completion_summary(self) -> dict:
        """Get summary of task completion status."""
        summary = {"total": len(self._tasks)}
        for status in TaskStatus:
            count = sum(1 for t in self._tasks.values() if t.status == status)
            if count > 0:
                summary[status.value] = count
        return summary

    def _propagate_failure(self, failed_task_id: str) -> None:
        """Block tasks that depend on a failed task (transitively)."""
        to_block = set()
        queue = [failed_task_id]

        while queue:
            current = queue.pop(0)
            for task in self._tasks.values():
                if current in task.dependencies and task.id not in to_block:
                    if task.status == TaskStatus.PENDING:
                        to_block.add(task.id)
                        queue.append(task.id)

        for task_id in to_block:
            self._tasks[task_id].status = TaskStatus.BLOCKED
            logger.warning(
                f"Task '{self._tasks[task_id].name}' blocked due to "
                f"dependency failure"
            )

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID."""
        return self._tasks.get(task_id)

    def get_outputs_for_task(self, task_id: str) -> dict:
        """Collect outputs from all dependency tasks (cross-step data flow)."""
        task = self._tasks[task_id]
        collected = {}
        for dep_id in task.dependencies:
            dep_task = self._tasks[dep_id]
            if dep_task.outputs:
                collected.update(dep_task.outputs)
        return collected
