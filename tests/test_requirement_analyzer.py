"""Tests for the Requirement Analyzer Agent."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.requirement_analyzer import RequirementAnalyzerAgent
from src.models.schemas import RequirementType
from tests.mock_llm import MockLLMClient


class TestRequirementAnalyzer:
    """Test suite for requirement analysis."""

    def setup_method(self):
        self.llm = MockLLMClient()
        self.agent = RequirementAnalyzerAgent(llm_client=self.llm)

    def test_greenfield_classification(self):
        """Test that 'Build...' requirements are classified as greenfield."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener service with APIs.",
        })
        analyzed = result["analyzed_requirement"]
        assert analyzed.requirement_type == RequirementType.GREENFIELD

    def test_intent_extracted(self):
        """Test that intent is extracted from the requirement."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener service with APIs.",
        })
        analyzed = result["analyzed_requirement"]
        assert len(analyzed.intent) > 10

    def test_functional_requirements_extracted(self):
        """Test that functional requirements are extracted."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
        })
        analyzed = result["analyzed_requirement"]
        assert len(analyzed.functional_requirements) >= 3

    def test_non_functional_requirements_extracted(self):
        """Test that NFRs are identified."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener service.",
        })
        analyzed = result["analyzed_requirement"]
        assert len(analyzed.non_functional_requirements) >= 2

    def test_ambiguities_detected(self):
        """Test that ambiguities are identified."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener with analytics and persistence.",
        })
        analyzed = result["analyzed_requirement"]
        assert len(analyzed.ambiguities) > 0

    def test_normalized_problem_produced(self):
        """Test that a clear normalized problem statement is generated."""
        result = self.agent.run({
            "raw_text": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
        })
        analyzed = result["analyzed_requirement"]
        assert len(analyzed.normalized_problem) > 20
