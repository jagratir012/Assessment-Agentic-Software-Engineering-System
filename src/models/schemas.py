"""
Core data models for the Agentic SDLC System.
Uses Pydantic for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RequirementType(str, Enum):
    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    AMBIGUOUS = "ambiguous"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Requirement(BaseModel):
    """Raw requirement input from the user."""
    raw_text: str
    context: Optional[str] = None
    existing_codebase: Optional[str] = None  # Path or description for brownfield


class AnalyzedRequirement(BaseModel):
    """Structured output from the Requirement Analyzer Agent."""
    original_text: str
    requirement_type: RequirementType
    intent: str = Field(description="Clear statement of what the system should do")
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    normalized_problem: str = Field(description="Normalized engineering problem statement")


class Task(BaseModel):
    """A single actionable task in the execution plan."""
    id: str
    name: str
    description: str
    agent: str = Field(description="Which agent is responsible for executing this task")
    dependencies: list[str] = Field(default_factory=list, description="Task IDs this depends on")
    status: TaskStatus = TaskStatus.PENDING
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 2
    error_message: Optional[str] = None


class TaskGraph(BaseModel):
    """Directed acyclic graph of tasks with dependencies."""
    tasks: list[Task]
    execution_order: list[list[str]] = Field(
        default_factory=list,
        description="Ordered execution layers; tasks in same layer can run in parallel"
    )


class APIEndpoint(BaseModel):
    """API endpoint specification."""
    method: str
    path: str
    description: str
    request_body: Optional[dict] = None
    response_schema: Optional[dict] = None
    status_codes: dict[str, str] = Field(default_factory=dict)


class ArchitectureDesign(BaseModel):
    """System architecture output from the Architect Agent."""
    system_name: str = "System"
    overview: str = ""
    components: list[dict] = Field(default_factory=list)
    api_endpoints: list[APIEndpoint] = Field(default_factory=list)
    data_models: list[dict] = Field(default_factory=list)
    technology_stack: dict[str, str] = Field(default_factory=dict)
    design_patterns: list[str] = Field(default_factory=list)
    scalability_considerations: list[str] = Field(default_factory=list)
    diagram_description: str = ""


class CodeArtifact(BaseModel):
    """Generated code file."""
    filename: str
    filepath: str
    language: str
    content: str
    description: str


class TestCase(BaseModel):
    """A single test case."""
    name: str
    description: str
    test_type: str  # unit, integration, e2e
    code: str


class TestSuite(BaseModel):
    """Collection of test cases."""
    test_cases: list[TestCase] = Field(default_factory=list)
    coverage_estimate: str = ""
    testing_strategy: str = ""


class RiskAssessment(BaseModel):
    """Individual risk item."""
    category: str
    description: str
    severity: Severity
    mitigation: str
    likelihood: str = "medium"


class ValidationReport(BaseModel):
    """Output from the Validator Agent."""
    is_valid: bool = True
    risks: list[RiskAssessment] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    test_strategy: str = ""
    guardrails: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class EngineeringSummary(BaseModel):
    """Final structured engineering summary - the deliverable."""
    requirement: AnalyzedRequirement
    architecture: ArchitectureDesign
    task_graph: TaskGraph
    code_artifacts: list[CodeArtifact] = Field(default_factory=list)
    test_suite: TestSuite = Field(default_factory=TestSuite)
    validation: ValidationReport = Field(default_factory=ValidationReport)
    implementation_rationale: str = ""
    assumptions_and_limitations: list[str] = Field(default_factory=list)
