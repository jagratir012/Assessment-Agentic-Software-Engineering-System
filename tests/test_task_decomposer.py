"""Tests for the Task Decomposer Agent."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.requirement_analyzer import RequirementAnalyzerAgent
from src.agents.task_decomposer import TaskDecomposerAgent
from src.models.schemas import TaskStatus
from tests.mock_llm import MockLLMClient


class TestTaskDecomposer:
    """Test suite for task decomposition."""

    def setup_method(self):
        self.llm = MockLLMClient()
        analyzer = RequirementAnalyzerAgent(llm_client=self.llm)
        self.decomposer = TaskDecomposerAgent(llm_client=self.llm)
        result = analyzer.run({
            "raw_text": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
        })
        self.analyzed_req = result["analyzed_requirement"]

    def test_generates_tasks(self):
        """Test that tasks are generated from a requirement."""
        result = self.decomposer.run({"analyzed_requirement": self.analyzed_req})
        task_graph = result["task_graph"]
        assert len(task_graph.tasks) >= 8

    def test_execution_layers_computed(self):
        """Test that execution layers are computed correctly."""
        result = self.decomposer.run({"analyzed_requirement": self.analyzed_req})
        task_graph = result["task_graph"]
        assert len(task_graph.execution_order) >= 4

    def test_no_circular_dependencies(self):
        """Test that the task graph has no cycles."""
        result = self.decomposer.run({"analyzed_requirement": self.analyzed_req})
        task_graph = result["task_graph"]

        all_task_ids = {t.id for t in task_graph.tasks}
        layered_ids = set()
        for layer in task_graph.execution_order:
            for tid in layer:
                assert tid not in layered_ids, f"Task {tid} in multiple layers"
                layered_ids.add(tid)
        assert layered_ids == all_task_ids

    def test_first_layer_has_no_dependencies(self):
        """Test that first execution layer tasks have zero dependencies."""
        result = self.decomposer.run({"analyzed_requirement": self.analyzed_req})
        task_graph = result["task_graph"]
        first_layer = task_graph.execution_order[0]
        task_map = {t.id: t for t in task_graph.tasks}
        for tid in first_layer:
            assert task_map[tid].dependencies == []

    def test_all_tasks_pending(self):
        """Test that all generated tasks start in PENDING status."""
        result = self.decomposer.run({"analyzed_requirement": self.analyzed_req})
        task_graph = result["task_graph"]
        for task in task_graph.tasks:
            assert task.status == TaskStatus.PENDING
