"""
Code Generator Agent.

Responsibilities:
- Generate production-quality code based on architecture and task specs
- Produce data models, service logic, API handlers, and infrastructure code
- Follow clean code principles: modularity, single responsibility

Uses Claude LLM for dynamic code generation for ANY requirement.
"""

from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import CodeArtifact, ArchitectureDesign
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior software engineer generating production-quality code.

You must output a JSON object with this structure:
{
  "artifacts": [
    {
      "filename": "filename.py",
      "filepath": "project_name/filename.py",
      "language": "python",
      "content": "full file content as a string",
      "description": "What this file does"
    }
  ]
}

Rules:
- Generate COMPLETE, RUNNABLE code (not pseudocode or stubs)
- Use Python with FastAPI for web services unless the requirement specifies otherwise
- Include proper imports, type hints, docstrings, and error handling
- Follow clean architecture: separate models, services, repositories, routes
- Generate 5-8 files covering: models, service logic, API routes, config, main app, Dockerfile
- Each file should be self-contained and production-ready
- Use async/await for I/O operations
- Include proper error handling and validation
- Add inline comments for complex logic
- The content field must be a valid string (escape quotes properly)
"""


class CodeGeneratorAgent(BaseAgent):
    """Generates production-quality code using LLM for any requirement."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="code_generator",
            description="Generates production-quality code from architecture specs",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Generate code artifacts based on architecture design.

        Inputs:
            - architecture: ArchitectureDesign model or dict
            - analyzed_requirement: The original requirement for context

        Returns:
            - code_artifacts: list[CodeArtifact]
        """
        architecture = inputs.get("architecture")
        if isinstance(architecture, dict):
            architecture = ArchitectureDesign(**architecture)

        req_data = inputs.get("analyzed_requirement") or inputs.get("requirement")

        self._logger.info("Generating code artifacts...")

        # Build context for code generation
        arch_context = ""
        if architecture:
            arch_context = (
                f"System: {architecture.system_name}\n"
                f"Overview: {architecture.overview}\n\n"
                f"Components:\n"
                + "\n".join(
                    f"- {c['name']}: {c['responsibility']} ({c['technology']})"
                    for c in architecture.components
                )
                + f"\n\nAPI Endpoints:\n"
                + "\n".join(
                    f"- {ep.method} {ep.path}: {ep.description}"
                    for ep in architecture.api_endpoints
                )
                + f"\n\nData Models:\n"
                + "\n".join(
                    f"- {dm['name']}: {json.dumps(dm['fields'])}"
                    for dm in architecture.data_models
                )
                + f"\n\nTechnology Stack:\n"
                + "\n".join(
                    f"- {k}: {v}" for k, v in architecture.technology_stack.items()
                )
            )

        req_context = ""
        if req_data:
            if isinstance(req_data, dict):
                req_context = (
                    f"\n\nRequirement Intent: {req_data.get('intent', '')}\n"
                    f"Functional Requirements:\n"
                    + "\n".join(f"- {fr}" for fr in req_data.get('functional_requirements', []))
                )
            else:
                req_context = f"\n\nRequirement: {req_data.intent}"

        user_prompt = (
            f"Generate production code for the following system:\n\n"
            f"{arch_context}\n{req_context}"
        )

        result = self._llm.ask_json(
            SYSTEM_PROMPT, user_prompt, max_tokens=16000,
            model="claude-sonnet-4-6",
        )

        if "raw_response" in result or not result.get("artifacts"):
            self._logger.warning("Code generator got empty/unparseable response, retrying with shorter request")
            # Retry asking for fewer, shorter files
            retry_prompt = (
                f"Generate 4 Python files for: {arch_context[:500]}\n\n"
                f"Rules: Return JSON with 'artifacts' array. Each artifact has: "
                f"filename, filepath, language, content (keep each file under 50 lines), description. "
                f"Generate: models.py, service.py, routes.py, main.py"
            )
            result = self._llm.ask_json(
                SYSTEM_PROMPT, retry_prompt, max_tokens=8000,
                model="claude-sonnet-4-6", use_cache=False,
            )

        artifacts = []
        for art_data in result.get("artifacts", []):
            artifacts.append(CodeArtifact(
                filename=art_data.get("filename", "unknown.py"),
                filepath=art_data.get("filepath", art_data.get("filename", "unknown.py")),
                language=art_data.get("language", "python"),
                content=art_data.get("content", "# Generated code placeholder"),
                description=art_data.get("description", ""),
            ))

        self._logger.info(f"Generated {len(artifacts)} code artifacts")
        return {"code_artifacts": artifacts}
