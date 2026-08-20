"""Tests for the Workflow Engine (Orchestrator)."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.requirement_analyzer import RequirementAnalyzerAgent
from src.agents.task_decomposer import TaskDecomposerAgent
from src.agents.architect_agent import ArchitectAgent
from src.agents.code_generator import CodeGeneratorAgent
from src.agents.test_generator import TestGeneratorAgent
from src.agents.validator_agent import ValidatorAgent
from src.orchestrator.workflow_engine import WorkflowEngine
from src.models.schemas import TaskStatus
from tests.mock_llm import MockLLMClient


class TestWorkflowEngine:
    """Test suite for workflow orchestration."""

    def setup_method(self):
        self.llm = MockLLMClient()

        analyzer = RequirementAnalyzerAgent(llm_client=self.llm)
        decomposer = TaskDecomposerAgent(llm_client=self.llm)

        analysis = analyzer.run({
            "raw_text": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
        })
        self.analyzed_req = analysis["analyzed_requirement"]

        decomp = decomposer.run({"analyzed_requirement": self.analyzed_req})
        self.task_graph_model = decomp["task_graph"]

        self.agents = {
            "architect": ArchitectAgent(llm_client=self.llm),
            "code_generator": CodeGeneratorAgent(llm_client=self.llm),
            "test_generator": TestGeneratorAgent(llm_client=self.llm),
            "validator": ValidatorAgent(llm_client=self.llm),
        }

    def test_full_workflow_execution(self):
        """Test that the full workflow completes without errors."""
        engine = WorkflowEngine(self.agents)
        engine._context["analyzed_requirement"] = self.analyzed_req.model_dump()
        engine._context["requirement"] = self.analyzed_req.model_dump()

        outputs = engine.execute_workflow(self.task_graph_model)

        assert "architecture" in outputs
        assert "code_artifacts" in outputs
        assert "test_suite" in outputs
        assert "validation_report" in outputs

    def test_all_tasks_completed(self):
        """Test that all tasks reach completed status."""
        engine = WorkflowEngine(self.agents)
        engine._context["analyzed_requirement"] = self.analyzed_req.model_dump()
        engine._context["requirement"] = self.analyzed_req.model_dump()

        engine.execute_workflow(self.task_graph_model)

        task_graph = engine._task_graph
        for task in task_graph.tasks.values():
            assert task.status == TaskStatus.COMPLETED, f"Task {task.name} not completed"

    def test_execution_log_recorded(self):
        """Test that execution log captures all task runs."""
        engine = WorkflowEngine(self.agents)
        engine._context["analyzed_requirement"] = self.analyzed_req.model_dump()
        engine._context["requirement"] = self.analyzed_req.model_dump()

        engine.execute_workflow(self.task_graph_model)

        log = engine.get_execution_log()
        assert len(log) == len(self.task_graph_model.tasks)
        for entry in log:
            assert entry["status"] == "completed"

    def test_cross_step_data_flow(self):
        """Test that outputs from earlier tasks flow to later tasks."""
        engine = WorkflowEngine(self.agents)
        engine._context["analyzed_requirement"] = self.analyzed_req.model_dump()
        engine._context["requirement"] = self.analyzed_req.model_dump()

        outputs = engine.execute_workflow(self.task_graph_model)

        assert outputs["architecture"] is not None
        assert len(outputs["code_artifacts"]) > 0
