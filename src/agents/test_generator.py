"""
Test Generator Agent.

Responsibilities:
- Generate unit tests for core business logic
- Generate integration tests for API endpoints
- Define test strategy and coverage goals

Uses Claude LLM for dynamic test generation for ANY requirement.
"""

from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import TestSuite, TestCase, ArchitectureDesign, CodeArtifact
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior QA engineer generating comprehensive test suites.

You must output a JSON object with this structure:
{
  "test_cases": [
    {
      "name": "test_function_name",
      "description": "What this test verifies",
      "test_type": "unit" | "integration",
      "code": "pytest test function code (keep under 20 lines per test)"
    }
  ],
  "coverage_estimate": "Estimated coverage percentage and what it covers",
  "testing_strategy": "Overall testing strategy description"
}

Rules:
- Generate 5-7 test cases total (mix of unit and integration)
- KEEP EACH TEST SHORT: maximum 15-20 lines of code per test
- Unit tests should use mocks for external dependencies
- Integration tests should test the API request/response cycle
- Use pytest with pytest-asyncio for async code
- Include both happy path and error/edge cases
- Test names should be descriptive (test_<what>_<scenario>)
- Do NOT generate overly verbose tests — focus on the assertion logic
"""


class TestGeneratorAgent(BaseAgent):
    """Generates comprehensive test suites using LLM."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="test_generator",
            description="Generates unit and integration tests",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Generate test suite based on architecture and code artifacts.

        Returns:
            - test_suite: TestSuite with unit and integration tests
        """
        self._logger.info("Generating test suite...")

        architecture = inputs.get("architecture")
        code_artifacts = inputs.get("code_artifacts", [])
        req_data = inputs.get("analyzed_requirement") or inputs.get("requirement")

        # Build context for test generation
        context_parts = []

        if architecture:
            if isinstance(architecture, dict):
                context_parts.append(f"System: {architecture.get('system_name', 'Unknown')}")
                context_parts.append(f"Overview: {architecture.get('overview', '')}")
                for ep in architecture.get("api_endpoints", []):
                    if isinstance(ep, dict):
                        context_parts.append(f"API: {ep.get('method', 'GET')} {ep.get('path', '/')}")
                    else:
                        context_parts.append(f"API: {ep.method} {ep.path}")
            else:
                context_parts.append(f"System: {architecture.system_name}")
                context_parts.append(f"Overview: {architecture.overview}")
                for ep in architecture.api_endpoints:
                    context_parts.append(f"API: {ep.method} {ep.path} - {ep.description}")

        if code_artifacts:
            context_parts.append("\nGenerated Code Files:")
            for art in code_artifacts[:5]:  # Limit to avoid token overflow
                if isinstance(art, dict):
                    context_parts.append(f"- {art.get('filename', 'unknown')}: {art.get('description', '')}")
                else:
                    context_parts.append(f"- {art.filename}: {art.description}")

        if req_data:
            if isinstance(req_data, dict):
                context_parts.append(f"\nRequirement: {req_data.get('intent', '')}")
            else:
                context_parts.append(f"\nRequirement: {req_data.intent}")

        user_prompt = (
            "Generate a test suite for the following system:\n\n"
            + "\n".join(context_parts)
        )

        result = self._llm.ask_json(SYSTEM_PROMPT, user_prompt, max_tokens=12000)

        # If parsing failed or no test cases, retry with simpler prompt
        if "raw_response" in result or not result.get("test_cases"):
            self._logger.warning("Test generation got empty/unparseable result, retrying with simpler prompt")
            simple_prompt = (
                f"Generate 5 pytest test cases for a system with this description: "
                f"{context_parts[0] if context_parts else 'a microservice'}. "
                f"Return JSON with test_cases array. Each test_case has: name, description, test_type (unit or integration), code (short pytest function)."
            )
            result = self._llm.ask_json(SYSTEM_PROMPT, simple_prompt, max_tokens=8000, use_cache=False)

        test_cases = []
        for tc_data in result.get("test_cases", []):
            test_cases.append(TestCase(
                name=tc_data.get("name", "test_unnamed"),
                description=tc_data.get("description", ""),
                test_type=tc_data.get("test_type", "unit"),
                code=tc_data.get("code", "# Test placeholder"),
            ))

        test_suite = TestSuite(
            test_cases=test_cases,
            coverage_estimate=result.get("coverage_estimate", "~80% estimated"),
            testing_strategy=result.get("testing_strategy", "Multi-layer testing approach"),
        )

        self._logger.info(f"Generated {len(test_cases)} test cases")
        return {"test_suite": test_suite}
