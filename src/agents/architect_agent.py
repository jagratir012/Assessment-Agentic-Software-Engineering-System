"""
Architect Agent.

Responsibilities:
- Design system architecture based on analyzed requirements
- Define components, their interactions, and data flow
- Specify API contracts and schema definitions
- Select appropriate technology stack

Uses Claude LLM for dynamic architecture design for ANY requirement.
"""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..models.schemas import (
    AnalyzedRequirement,
    ArchitectureDesign,
    APIEndpoint,
)
from ..llm.client import LLMClient


SYSTEM_PROMPT = """You are a senior system architect designing software architecture.

You must output a JSON object with this structure:
{
  "system_name": "Name of the system",
  "overview": "2-3 sentence overview of the architecture",
  "components": [
    {
      "name": "Component Name",
      "responsibility": "What this component does",
      "technology": "Specific technology choice"
    }
  ],
  "api_endpoints": [
    {
      "method": "GET|POST|PUT|DELETE",
      "path": "/api/v1/...",
      "description": "What this endpoint does",
      "request_body": {"field": "type"} or null,
      "response_schema": {"field": "type"},
      "status_codes": {"200": "Success", "404": "Not found"}
    }
  ],
  "data_models": [
    {
      "name": "ModelName",
      "fields": {"field_name": "type and constraints"}
    }
  ],
  "technology_stack": {"category": "technology choice"},
  "design_patterns": ["Pattern Name (reason for using it)"],
  "scalability_considerations": ["How the system scales"],
  "diagram_description": "Describe the data flow as a list of connections in format: ComponentA -> ComponentB: label. Example: Client -> API Gateway: HTTP requests, API Gateway -> Service Layer: validated requests, Service Layer -> Database: queries"
}

Rules:
- Design for production use (not toy/demo)
- Choose specific, modern technologies (not generic "a database")
- Include 4-8 components
- Include 4-6 API endpoints minimum
- Include 2-4 data models
- Design patterns should be relevant to the problem
- Scalability considerations should be specific and actionable
- diagram_description MUST list data flow connections between components using the arrow format: ComponentA -> ComponentB: description
"""


class ArchitectAgent(BaseAgent):
    """Designs system architecture using LLM for any requirement."""

    def __init__(self, llm_client: LLMClient = None):
        super().__init__(
            name="architect",
            description="Designs system architecture, components, and API contracts",
        )
        self._llm = llm_client

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Design system architecture based on analyzed requirement.

        Inputs:
            - analyzed_requirement: AnalyzedRequirement (or dict)
            - requirement: Alternative key for the requirement

        Returns:
            - architecture: ArchitectureDesign model
        """
        req_data = inputs.get("analyzed_requirement") or inputs.get("requirement")

        if isinstance(req_data, dict):
            req = AnalyzedRequirement(**req_data)
        else:
            req = req_data

        self._logger.info(f"Designing architecture for: {req.intent[:80]}...")

        user_prompt = (
            f"Design a system architecture for:\n\n"
            f"Intent: {req.intent}\n\n"
            f"Functional Requirements:\n"
            + "\n".join(f"- {fr}" for fr in req.functional_requirements)
            + f"\n\nNon-Functional Requirements:\n"
            + "\n".join(f"- {nfr}" for nfr in req.non_functional_requirements)
            + f"\n\nConstraints:\n"
            + "\n".join(f"- {c}" for c in req.constraints)
            + f"\n\nAssumptions:\n"
            + "\n".join(f"- {a}" for a in req.assumptions)
        )

        result = self._llm.ask_json(SYSTEM_PROMPT, user_prompt, max_tokens=4096)

        if "raw_response" in result and len(result) == 1:
            self._logger.warning("Architect got unparseable response, retrying with simpler prompt")
            # Retry with a simpler prompt
            simple_prompt = (
                f"Design architecture for: {req.intent}\n"
                f"Include: system_name, overview, components (name/responsibility/technology), "
                f"api_endpoints (method/path/description), data_models, technology_stack, design_patterns"
            )
            result = self._llm.ask_json(SYSTEM_PROMPT, simple_prompt, max_tokens=3000, use_cache=False)

        # Parse API endpoints
        api_endpoints = []
        for ep_data in result.get("api_endpoints", []):
            api_endpoints.append(APIEndpoint(
                method=ep_data.get("method", "GET"),
                path=ep_data.get("path", "/"),
                description=ep_data.get("description", ""),
                request_body=ep_data.get("request_body"),
                response_schema=ep_data.get("response_schema"),
                status_codes=ep_data.get("status_codes", {}),
            ))

        architecture = ArchitectureDesign(
            system_name=result.get("system_name", "System"),
            overview=result.get("overview", ""),
            components=result.get("components", []),
            api_endpoints=api_endpoints,
            data_models=result.get("data_models", []),
            technology_stack=result.get("technology_stack", {}),
            design_patterns=result.get("design_patterns", []),
            scalability_considerations=result.get("scalability_considerations", []),
            diagram_description=result.get("diagram_description", ""),
        )

        return {"architecture": architecture}
