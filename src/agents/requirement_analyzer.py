"""
Requirement Analyzer Agent.

Responsibilities:
- Interpret intent from raw requirement text
- Identify ambiguities and ask clarification questions
- Classify requirement type (greenfield/brownfield/ambiguous)
- Normalize into a clear engineering problem statement

Uses Claude LLM for dynamic reasoning about ANY requirement.
"""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import (
    AnalyzedRequirement,
    RequirementType,
)
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior software architect analyzing a software requirement.
Your job is to produce a structured analysis of the requirement.

You must output a JSON object with exactly these fields:
{
  "requirement_type": "greenfield" | "brownfield" | "ambiguous",
  "intent": "Clear one-sentence statement of what the system should do",
  "functional_requirements": ["list of specific functional requirements"],
  "non_functional_requirements": ["list of NFRs like performance, security, scalability"],
  "ambiguities": ["list of things that are unclear or underspecified"],
  "assumptions": ["list of reasonable assumptions to resolve ambiguities"],
  "constraints": ["list of technical constraints"],
  "clarification_questions": ["questions to ask the user to resolve ambiguities"],
  "normalized_problem": "A clear, normalized engineering problem statement (2-3 sentences)"
}

Rules:
- requirement_type: "greenfield" if building something new, "brownfield" if modifying existing, "ambiguous" if unclear
- Extract at least 5 functional requirements
- Extract at least 3 non-functional requirements
- Identify at least 2 ambiguities (there are always some)
- Generate assumptions that resolve the ambiguities
- The normalized_problem should be a precise engineering statement
"""


class RequirementAnalyzerAgent(BaseAgent):
    """Analyzes raw requirements using Claude LLM for dynamic reasoning."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="requirement_analyzer",
            description="Interprets requirements, identifies ambiguities, and normalizes into engineering problems",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a raw requirement and produce a structured analysis.

        Inputs:
            - raw_text: The raw requirement string
            - context: Optional context about the project
            - existing_codebase: Optional path/description of existing code

        Returns:
            - analyzed_requirement: AnalyzedRequirement model
        """
        raw_text = inputs.get("raw_text", "")
        context = inputs.get("context", "")
        existing_codebase = inputs.get("existing_codebase")

        self._logger.info(f"Analyzing requirement: {raw_text[:100]}...")

        user_prompt = f"Requirement: {raw_text}"
        if context:
            user_prompt += f"\n\nAdditional context: {context}"
        if existing_codebase:
            user_prompt += f"\n\nExisting codebase: {existing_codebase}"
            user_prompt += "\n\nNote: This involves modifying an existing system."

        result = self._llm.ask_json(SYSTEM_PROMPT, user_prompt)

        # Map string to enum
        req_type_str = result.get("requirement_type", "greenfield")
        try:
            req_type = RequirementType(req_type_str)
        except ValueError:
            req_type = RequirementType.AMBIGUOUS

        analyzed = AnalyzedRequirement(
            original_text=raw_text,
            requirement_type=req_type,
            intent=result.get("intent", raw_text),
            functional_requirements=result.get("functional_requirements", []),
            non_functional_requirements=result.get("non_functional_requirements", []),
            ambiguities=result.get("ambiguities", []),
            assumptions=result.get("assumptions", []),
            constraints=result.get("constraints", []),
            clarification_questions=result.get("clarification_questions", []),
            normalized_problem=result.get("normalized_problem", raw_text),
        )

        return {"analyzed_requirement": analyzed}
