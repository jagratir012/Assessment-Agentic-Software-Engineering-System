"""
Mock LLM Client for testing.

Returns pre-defined JSON responses so tests can run without an API key.
Demonstrates that the system architecture supports dependency injection.
"""

import json


class MockLLMClient:
    """Mock LLM client that returns deterministic responses for testing."""

    def ask(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return json.dumps(self.ask_json(system_prompt, user_prompt, **kwargs))

    def ask_json(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        """Return appropriate mock response based on the system prompt content."""

        if "analyzing a software requirement" in system_prompt.lower():
            return self._mock_requirement_analysis()
        elif "decomposing a software requirement" in system_prompt.lower():
            return self._mock_task_decomposition()
        elif "designing software architecture" in system_prompt.lower():
            return self._mock_architecture()
        elif "generating production-quality code" in system_prompt.lower():
            return self._mock_code_generation()
        elif "generating comprehensive test" in system_prompt.lower():
            return self._mock_test_generation()
        elif "risk assessment" in system_prompt.lower():
            return self._mock_validation()

        return {"raw_response": "Mock response"}

    def _mock_requirement_analysis(self) -> dict:
        return {
            "requirement_type": "greenfield",
            "intent": "Build a production-ready URL shortener service",
            "functional_requirements": [
                "Shorten long URLs to unique short codes",
                "Redirect short URLs to original long URLs",
                "Track click analytics per URL",
                "CRUD API for URL management",
                "Support custom short codes",
            ],
            "non_functional_requirements": [
                "Handle 10,000+ requests/sec",
                "Sub-50ms redirect latency",
                "99.9% uptime",
            ],
            "ambiguities": [
                "Storage technology not specified",
                "Authentication model unclear",
            ],
            "assumptions": [
                "PostgreSQL for storage, Redis for cache",
                "API key auth for creation, public for redirects",
            ],
            "constraints": [
                "Must be containerized",
                "RESTful HTTP API",
            ],
            "clarification_questions": [
                "Preferred database technology?",
                "Target throughput?",
            ],
            "normalized_problem": (
                "Design and implement a URL shortening microservice with "
                "RESTful APIs, persistent storage, caching, and analytics."
            ),
        }

    def _mock_task_decomposition(self) -> dict:
        return {
            "tasks": [
                {"id": "task-001", "name": "Design Architecture", "description": "Design system architecture", "agent": "architect", "dependencies": []},
                {"id": "task-002", "name": "Define Data Models", "description": "Design database schemas", "agent": "code_generator", "dependencies": ["task-001"]},
                {"id": "task-003", "name": "Design APIs", "description": "Define API contracts", "agent": "architect", "dependencies": ["task-001"]},
                {"id": "task-004", "name": "Implement Service", "description": "Core business logic", "agent": "code_generator", "dependencies": ["task-002", "task-003"]},
                {"id": "task-005", "name": "Implement Data Layer", "description": "Repository pattern", "agent": "code_generator", "dependencies": ["task-002"]},
                {"id": "task-006", "name": "Implement API Routes", "description": "HTTP handlers", "agent": "code_generator", "dependencies": ["task-004", "task-005"]},
                {"id": "task-007", "name": "Implement Cache", "description": "Redis caching", "agent": "code_generator", "dependencies": ["task-004"]},
                {"id": "task-008", "name": "Unit Tests", "description": "Test service logic", "agent": "test_generator", "dependencies": ["task-004", "task-005"]},
                {"id": "task-009", "name": "Integration Tests", "description": "Test API endpoints", "agent": "test_generator", "dependencies": ["task-006"]},
                {"id": "task-010", "name": "Validation", "description": "Risk assessment", "agent": "validator", "dependencies": ["task-006", "task-007", "task-008", "task-009"]},
            ]
        }

    def _mock_architecture(self) -> dict:
        return {
            "system_name": "URL Shortener Service",
            "overview": "A scalable URL shortening microservice with FastAPI, PostgreSQL, and Redis.",
            "components": [
                {"name": "API Gateway", "responsibility": "Request routing and rate limiting", "technology": "FastAPI"},
                {"name": "URL Service", "responsibility": "Business logic", "technology": "Python"},
                {"name": "Cache", "responsibility": "Hot URL caching", "technology": "Redis"},
                {"name": "Database", "responsibility": "Persistent storage", "technology": "PostgreSQL"},
            ],
            "api_endpoints": [
                {"method": "POST", "path": "/api/v1/urls", "description": "Create short URL", "request_body": {"long_url": "string"}, "response_schema": {"short_code": "string"}, "status_codes": {"201": "Created"}},
                {"method": "GET", "path": "/{code}", "description": "Redirect", "request_body": None, "response_schema": None, "status_codes": {"301": "Redirect"}},
                {"method": "GET", "path": "/api/v1/urls/{code}/analytics", "description": "Get analytics", "request_body": None, "response_schema": {"clicks": "int"}, "status_codes": {"200": "OK"}},
            ],
            "data_models": [
                {"name": "URL", "fields": {"id": "UUID", "short_code": "VARCHAR(10)", "long_url": "TEXT", "created_at": "TIMESTAMP"}},
                {"name": "ClickEvent", "fields": {"id": "BIGINT", "url_id": "UUID", "clicked_at": "TIMESTAMP"}},
            ],
            "technology_stack": {"language": "Python 3.12", "framework": "FastAPI", "database": "PostgreSQL", "cache": "Redis"},
            "design_patterns": ["Repository Pattern", "Service Layer", "CQRS"],
            "scalability_considerations": ["Stateless API for horizontal scaling", "Redis cache for read-heavy traffic"],
            "diagram_description": "Client -> API -> Service -> DB/Cache",
        }

    def _mock_code_generation(self) -> dict:
        return {
            "artifacts": [
                {"filename": "models.py", "filepath": "url_shortener/models.py", "language": "python", "content": "# Models\nfrom sqlalchemy.orm import DeclarativeBase\n\nclass Base(DeclarativeBase):\n    pass\n\nclass URL(Base):\n    __tablename__ = 'urls'\n    id = None  # Placeholder\n", "description": "Database models"},
                {"filename": "service.py", "filepath": "url_shortener/service.py", "language": "python", "content": "# Service\nclass URLService:\n    async def shorten(self, url: str) -> str:\n        return 'abc123'\n", "description": "Business logic"},
                {"filename": "routes.py", "filepath": "url_shortener/routes.py", "language": "python", "content": "# Routes\nfrom fastapi import APIRouter\nrouter = APIRouter()\n\n@router.post('/api/v1/urls')\nasync def create():\n    return {'short_code': 'abc'}\n", "description": "API routes"},
                {"filename": "main.py", "filepath": "url_shortener/main.py", "language": "python", "content": "# Main\nfrom fastapi import FastAPI\napp = FastAPI()\n", "description": "App entry point"},
                {"filename": "config.py", "filepath": "url_shortener/config.py", "language": "python", "content": "# Config\nclass Settings:\n    db_url: str = 'postgresql://localhost/urls'\n", "description": "Configuration"},
            ]
        }

    def _mock_test_generation(self) -> dict:
        return {
            "test_cases": [
                {"name": "test_shorten_url", "description": "Test URL shortening", "test_type": "unit", "code": "def test_shorten_url():\n    assert True\n"},
                {"name": "test_redirect", "description": "Test redirect", "test_type": "unit", "code": "def test_redirect():\n    assert True\n"},
                {"name": "test_analytics", "description": "Test analytics", "test_type": "unit", "code": "def test_analytics():\n    assert True\n"},
                {"name": "test_create_api", "description": "Test POST endpoint", "test_type": "integration", "code": "def test_create_api():\n    assert True\n"},
                {"name": "test_redirect_api", "description": "Test redirect endpoint", "test_type": "integration", "code": "def test_redirect_api():\n    assert True\n"},
            ],
            "coverage_estimate": "~85% line coverage",
            "testing_strategy": "Unit tests for logic, integration tests for API",
        }

    def _mock_validation(self) -> dict:
        return {
            "is_valid": True,
            "risks": [
                {"category": "Security", "description": "Short code enumeration", "severity": "medium", "mitigation": "Rate limiting + long codes", "likelihood": "medium"},
                {"category": "Availability", "description": "Cache failure impact", "severity": "high", "mitigation": "Circuit breaker pattern", "likelihood": "low"},
                {"category": "Performance", "description": "DB bottleneck at scale", "severity": "medium", "mitigation": "Read replicas", "likelihood": "medium"},
            ],
            "trade_offs": [
                "Base62 vs UUID: shorter but collision risk",
                "301 vs 302 redirect: SEO vs flexibility",
                "Async analytics: speed vs consistency",
            ],
            "verification_steps": [
                "Run unit tests",
                "Run integration tests",
                "Load test with 10K concurrent users",
                "Security scan with OWASP ZAP",
            ],
            "test_strategy": "Multi-layer: unit, integration, load, security",
            "guardrails": ["Rate limiting", "Input validation", "SQL injection prevention"],
            "recommendations": ["Add monitoring", "Add CDN for global latency"],
        }
