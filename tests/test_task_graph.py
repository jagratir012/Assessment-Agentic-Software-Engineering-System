"""Tests for the TaskGraph dependency management."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.task_graph import TaskGraph
from src.models.schemas import Task, TaskGraph as TaskGraphModel, TaskStatus


class TestTaskGraph:
    """Test suite for DAG-based task graph."""

    def _make_simple_graph(self) -> TaskGraph:
        """Create a simple test task graph: A -> B -> C, A -> D."""
        tasks = [
            Task(id="A", name="Task A", description="First", agent="test", dependencies=[]),
            Task(id="B", name="Task B", description="Second", agent="test", dependencies=["A"]),
            Task(id="C", name="Task C", description="Third", agent="test", dependencies=["B"]),
            Task(id="D", name="Task D", description="Parallel", agent="test", dependencies=["A"]),
        ]
        model = TaskGraphModel(tasks=tasks, execution_order=[["A"], ["B", "D"], ["C"]])
        return TaskGraph(model)

    def test_get_ready_tasks_initial(self):
        """Test that only root tasks are ready initially."""
        graph = self._make_simple_graph()
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "A"

    def test_mark_completed_unlocks_dependents(self):
        """Test that completing a task makes its dependents ready."""
        graph = self._make_simple_graph()
        graph.mark_completed("A", {"result": "done"})

        ready = graph.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "B" in ready_ids
        assert "D" in ready_ids

    def test_failure_propagation(self):
        """Test that failing a task blocks its dependents."""
        graph = self._make_simple_graph()
        graph.mark_completed("A")
        graph.mark_failed("B", "Something went wrong")

        # C depends on B, should be blocked
        assert graph.tasks["C"].status == TaskStatus.BLOCKED
        # D doesn't depend on B, should still be ready
        assert graph.tasks["D"].status == TaskStatus.PENDING

    def test_is_complete(self):
        """Test completion detection."""
        graph = self._make_simple_graph()
        assert not graph.is_complete()

        graph.mark_completed("A")
        graph.mark_completed("B")
        graph.mark_completed("C")
        graph.mark_completed("D")
        assert graph.is_complete()

    def test_retry_logic(self):
        """Test that retry increments count and resets status."""
        graph = self._make_simple_graph()
        assert graph.can_retry("A")

        graph.increment_retry("A")
        assert graph.tasks["A"].retry_count == 1
        assert graph.tasks["A"].status == TaskStatus.PENDING

    def test_get_outputs_for_task(self):
        """Test cross-step data collection from dependencies."""
        graph = self._make_simple_graph()
        graph.mark_completed("A", {"architecture": {"name": "test"}})
        graph.mark_completed("B", {"code": "generated"})

        # C depends on B, should get B's outputs
        outputs = graph.get_outputs_for_task("C")
        assert "code" in outputs
