"""
Validator Agent.

Responsibilities:
- Identify risks, trade-offs, and failure scenarios
- Define validation approach and test strategy
- Establish guardrails for safe execution
- Verify outputs meet quality standards

Uses Claude LLM for dynamic risk assessment for ANY requirement.
"""

from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import (
    ValidationReport,
    RiskAssessment,
    Severity,
    ArchitectureDesign,
)
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior security and reliability engineer performing a risk assessment.

You must output a JSON object with this structure:
{
  "is_valid": true,
  "risks": [
    {
      "category": "Security|Performance|Availability|Data Integrity|Operational|Scalability",
      "description": "Description of the risk",
      "severity": "low|medium|high|critical",
      "mitigation": "How to mitigate this risk",
      "likelihood": "low|medium|high"
    }
  ],
  "trade_offs": ["Description of each trade-off decision"],
  "verification_steps": ["Numbered steps to verify the implementation"],
  "test_strategy": "Overall test strategy description",
  "guardrails": ["Safety guardrails and limits"],
  "recommendations": ["Future improvements and recommendations"]
}

Rules:
- Identify 5-8 specific risks (not generic platitudes)
- Each risk must have a concrete mitigation strategy
- Trade-offs should reflect actual design decisions made
- Verification steps should be actionable (someone could follow them)
- Guardrails should be specific limits/thresholds
- Recommendations should be forward-looking improvements
- Consider: security, performance, reliability, data integrity, operational concerns
"""


class ValidatorAgent(BaseAgent):
    """Validates engineering outputs and assesses risks using LLM."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="validator",
            description="Validates outputs, identifies risks, and defines guardrails",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the generated artifacts and produce a risk report.

        Returns:
            - validation_report: ValidationReport
        """
        self._logger.info("Running validation and risk assessment...")

        architecture = inputs.get("architecture")
        code_artifacts = inputs.get("code_artifacts", [])
        req_data = inputs.get("analyzed_requirement") or inputs.get("requirement")
        test_suite = inputs.get("test_suite")

        # Build context
        context_parts = []

        if req_data:
            if isinstance(req_data, dict):
                context_parts.append(f"Requirement: {req_data.get('intent', '')}")
                context_parts.append(f"Assumptions: {json.dumps(req_data.get('assumptions', []))}")
            else:
                context_parts.append(f"Requirement: {req_data.intent}")

        if architecture:
            if isinstance(architecture, dict):
                context_parts.append(f"\nArchitecture: {architecture.get('system_name', '')}")
                context_parts.append(f"Tech Stack: {json.dumps(architecture.get('technology_stack', {}))}")
                context_parts.append(f"Components: {json.dumps(architecture.get('components', []))}")
            else:
                context_parts.append(f"\nArchitecture: {architecture.system_name}")
                context_parts.append(f"Tech Stack: {json.dumps(architecture.technology_stack)}")

        if code_artifacts:
            context_parts.append(f"\nCode Artifacts: {len(code_artifacts)} files generated")
            for art in code_artifacts[:5]:
                if isinstance(art, dict):
                    context_parts.append(f"- {art.get('filename', '')}")
                else:
                    context_parts.append(f"- {art.filename}: {art.description}")

        if test_suite:
            if isinstance(test_suite, dict):
                tc = test_suite.get("test_cases", [])
                context_parts.append(f"\nTests: {len(tc)} test cases")
            else:
                context_parts.append(f"\nTests: {len(test_suite.test_cases)} test cases")

        user_prompt = (
            "Perform a risk assessment and validation for:\n\n"
            + "\n".join(context_parts)
        )

        result = self._llm.ask_json(SYSTEM_PROMPT, user_prompt, max_tokens=8000)

        # If parsing failed, retry with simpler prompt
        if "raw_response" in result or not result.get("risks"):
            self._logger.warning("Validator got empty/unparseable result, retrying")
            simple_prompt = (
                f"Assess risks for: {context_parts[0] if context_parts else 'a microservice'}. "
                f"Return JSON with: risks (array of category/description/severity/mitigation), "
                f"trade_offs (array of strings), guardrails (array of strings), "
                f"verification_steps (array), test_strategy (string), is_valid (true), recommendations (array)."
            )
            result = self._llm.ask_json(SYSTEM_PROMPT, simple_prompt, max_tokens=4096, use_cache=False)

        # Parse risks
        risks = []
        for risk_data in result.get("risks", []):
            try:
                severity = Severity(risk_data.get("severity", "medium"))
            except ValueError:
                severity = Severity.MEDIUM

            risks.append(RiskAssessment(
                category=risk_data.get("category", "General"),
                description=risk_data.get("description", ""),
                severity=severity,
                mitigation=risk_data.get("mitigation", ""),
                likelihood=risk_data.get("likelihood", "medium"),
            ))

        report = ValidationReport(
            is_valid=result.get("is_valid", True),
            risks=risks,
            trade_offs=result.get("trade_offs", []),
            verification_steps=result.get("verification_steps", []),
            test_strategy=result.get("test_strategy", ""),
            guardrails=result.get("guardrails", []),
            recommendations=result.get("recommendations", []),
        )

        self._logger.info(
            f"Validation complete: {len(risks)} risks, {len(report.trade_offs)} trade-offs"
        )
        return {"validation_report": report}
