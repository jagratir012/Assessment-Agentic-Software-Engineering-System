# 🏗️ Agentic SDLC System

An **agentic software engineering system** that transforms any software requirement into a complete, reviewable engineering outcome — including architecture design, production code, tests, risk assessment, and a polished HTML report.

Built with **Python** and powered by **Anthropic Claude**, this system demonstrates end-to-end workflow automation across the Software Development Life Cycle (SDLC).

---

## 🎯 What It Does

You give it a requirement like:

> *"Build a scalable URL shortener service with APIs, persistence, and analytics."*

And it produces:

| Output | Description |
|--------|-------------|
| 📋 Requirement Analysis | Intent extraction, ambiguity detection, assumptions |
| 🏛️ Architecture Design | Components, API contracts, data models, tech stack, system diagram |
| 📊 Task Decomposition | DAG-based task breakdown with parallel execution layers |
| 💻 Generated Code | Production-quality Python/FastAPI code files |
| 🧪 Test Suite | Unit and integration tests with pytest |
| ⚠️ Risk Assessment | Security, performance, scalability risks with mitigations |
| 📄 HTML Report | Beautiful, shareable report with all of the above |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Web UI (Flask) / CLI                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │  Requirement    │───▶│  Task Decomposer │                   │
│  │  Analyzer       │    │  (DAG planner)   │                   │
│  └─────────────────┘    └────────┬─────────┘                   │
│                                  │                              │
│              ┌───────────────────┼───────────────┐              │
│              ▼                   ▼               ▼              │
│  ┌───────────────┐   ┌───────────────┐  ┌─────────────┐       │
│  │   Architect   │   │     Code      │  │    Test     │       │
│  │    Agent      │   │   Generator   │  │  Generator  │       │
│  └───────┬───────┘   └───────┬───────┘  └──────┬──────┘       │
│          │                   │                  │               │
│          └───────────────────┴──────────────────┘               │
│                              │                                  │
│                    ┌─────────▼──────────┐                       │
│                    │   Validator Agent  │                       │
│                    │  (Risk & Trade-offs)│                       │
│                    └─────────┬──────────┘                       │
│                              │                                  │
│                    ┌─────────▼──────────┐                       │
│                    │  Report Generator  │                       │
│                    │  (HTML + JSON)     │                       │
│                    └────────────────────┘                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  LLM Client (Anthropic Claude) │ Caching │ Token Tracking       │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Responsibility |
|-----------|------|---------------|
| **Requirement Analyzer** | `src/agents/requirement_analyzer.py` | Parse intent, detect ambiguities, classify type |
| **Task Decomposer** | `src/agents/task_decomposer.py` | Break into DAG with parallel execution layers |
| **Architect Agent** | `src/agents/architect_agent.py` | Design components, APIs, data models, tech stack |
| **Code Generator** | `src/agents/code_generator.py` | Generate production Python/FastAPI code |
| **Test Generator** | `src/agents/test_generator.py` | Create unit + integration tests |
| **Validator Agent** | `src/agents/validator_agent.py` | Risk assessment, trade-offs, guardrails |
| **Workflow Engine** | `src/orchestrator/workflow_engine.py` | DAG-based task orchestration with retries |
| **LLM Client** | `src/llm/client.py` | Claude API wrapper with caching + cost tracking |
| **Report Generator** | `src/tools/report_generator.py` | HTML report with diagrams and code listings |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** — [Download](https://python.org)
- **Anthropic API Key** — [Get one](https://console.anthropic.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/agentic-sdlc-system.git
cd agentic-sdlc-system

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your API key
# Option 1: Create .env file
echo ANTHROPIC_API_KEY=sk-ant-your-key-here > .env

# Option 2: Environment variable (Windows)
set ANTHROPIC_API_KEY=sk-ant-your-key-here

# Option 3: Environment variable (Mac/Linux)
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Run — Web UI (Recommended)

```bash
python app.py
```

Opens a web interface at **http://localhost:5000** where you can:
1. Type any requirement
2. Click "Generate Engineering Output"
3. Watch real-time progress
4. Open the generated HTML report

### Run — Command Line

```bash
# Default: URL Shortener (mandatory demo)
python main.py

# Custom requirement
python main.py -r "Build a real-time notification service with WebSocket support"

# Interactive mode (approve each phase)
python main.py -r "Your requirement" --interactive

# Force fresh API calls (ignore cache)
python main.py -r "Your requirement" --fresh
```

### Run — Individual Agents

If a section is missing from the report, fill it in:

```bash
# Run just the architect
python run_agent.py architect

# Run just the code generator
python run_agent.py code_generator

# Run just the test generator
python run_agent.py test_generator

# Run just the validator
python run_agent.py validator

# Run all agents on the latest output
python run_agent.py all
```

---

## 📋 Sample Execution: URL Shortener Service

### Input

```
"Build a scalable URL shortener service with APIs, persistence, and analytics."
```

### Output Summary

The system produces a complete engineering package:

#### 1. Requirement Analysis
- **Type:** Greenfield
- **Intent:** Build a production-grade URL shortener microservice with REST APIs, persistent storage, and click analytics
- **10 Functional Requirements** extracted (URL shortening, redirect, analytics, custom aliases, etc.)
- **8 Non-Functional Requirements** (10K req/sec, <100ms latency, 99.9% uptime, etc.)
- **8 Ambiguities** identified (storage technology, auth model, analytics granularity, etc.)
- **8 Assumptions** made to resolve ambiguities (PostgreSQL + Redis, API key auth, base62 encoding, etc.)

#### 2. Architecture Design

**Components:**
| Component | Technology |
|-----------|-----------|
| API Gateway | FastAPI with middleware |
| URL Service | Python service layer |
| Cache Layer | Redis (TTL-based eviction) |
| Database | PostgreSQL with read replicas |
| Analytics Service | Async event processor |
| ID Generator | Base62 counter with range allocation |

**API Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/urls` | Create shortened URL |
| `GET` | `/{short_code}` | Redirect to original URL |
| `GET` | `/api/v1/urls/{code}/analytics` | Get click analytics |
| `DELETE` | `/api/v1/urls/{code}` | Delete a URL |

**System Diagram:**
```
Client → API Gateway → URL Service → PostgreSQL
                    ↘ Redis Cache
                    ↘ Analytics Service (async)
```

#### 3. Task Decomposition (8-10 tasks, 6 layers)

```
Layer 1: [Design Architecture]
Layer 2: [Data Models] [API Contracts]           ← parallel
Layer 3: [Core Service] [Data Access Layer]      ← parallel
Layer 4: [API Routes] [Caching] [Unit Tests]     ← parallel
Layer 5: [Integration Tests]
Layer 6: [Validation & Risk Assessment]
```

#### 4. Generated Code (5-8 files)

- `models.py` — SQLAlchemy ORM models (URL, ClickEvent)
- `service.py` — Core business logic (shorten, resolve, analytics)
- `repository.py` — Data access layer with async queries
- `routes.py` — FastAPI route handlers
- `cache.py` — Redis caching layer
- `config.py` — Environment-based configuration
- `main.py` — Application entry point
- `Dockerfile` — Container deployment

#### 5. Test Suite (7-9 test cases)

- Unit tests: URL generation, collision handling, expiration, cache hits
- Integration tests: Create endpoint, redirect, analytics, 404 handling

#### 6. Risk Assessment

| Severity | Risk | Mitigation |
|----------|------|-----------|
| HIGH | Cache failure increases DB load | Circuit breaker, graceful degradation |
| MEDIUM | Short code enumeration | Rate limiting, long codes (base62×7) |
| MEDIUM | Analytics bottleneck | Async processing, batch writes |
| HIGH | No monitoring defined | Prometheus metrics, structured logging |

**Trade-offs:** Base62 vs UUID, 301 vs 302 redirects, sync vs async analytics, single service vs microservices

---

## 📁 Project Structure

```
agentic-sdlc-system/
├── app.py                       # Web UI (Flask) — recommended entry point
├── main.py                      # CLI entry point
├── run_agent.py                 # Run individual agents
├── generate_report.py           # Regenerate HTML from existing JSON
├── test_api_key.py              # Quick API key validation
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Project metadata
├── .env.example                 # Environment variable template
├── .gitignore
│
├── src/
│   ├── agents/                  # Specialized AI agents
│   │   ├── base_agent.py        # Abstract base (retry, logging, audit)
│   │   ├── requirement_analyzer.py
│   │   ├── task_decomposer.py
│   │   ├── architect_agent.py
│   │   ├── code_generator.py
│   │   ├── test_generator.py
│   │   └── validator_agent.py
│   │
│   ├── orchestrator/            # Workflow coordination
│   │   ├── task_graph.py        # DAG dependency management
│   │   └── workflow_engine.py   # Multi-step execution engine
│   │
│   ├── llm/                     # LLM integration
│   │   └── client.py            # Anthropic Claude client + caching
│   │
│   ├── models/                  # Pydantic data schemas
│   │   └── schemas.py           # All data models
│   │
│   └── tools/                   # Utility tools
│       ├── file_writer.py       # Write code to disk
│       ├── code_validator.py    # AST syntax validation
│       └── report_generator.py  # HTML report generation
│
├── tests/                       # System tests (run without API key)
│   ├── mock_llm.py              # Mock LLM for testing
│   ├── test_requirement_analyzer.py
│   ├── test_task_decomposer.py
│   ├── test_task_graph.py
│   └── test_workflow_engine.py
│
├── output/                      # Generated outputs (one folder per run)
│   └── YYYYMMDD_HHMMSS_requirement-slug/
│       ├── report.html          # Beautiful HTML report
│       ├── engineering_summary.json  # Full structured data
│       └── code/                # Generated source code files
│
├── docs/                        # Documentation
│   ├── architecture.md
│   └── testing_approach.md
│
└── examples/                    # Example scenarios
    └── scenarios.md
```

---

## 🧪 Running Tests

Tests use a **mock LLM client** — no API key or internet required:

```bash
pytest tests/ -v
```

All 21 tests verify:
- Requirement classification and extraction
- Task DAG generation (no cycles, correct layers)
- Workflow engine execution and cross-step data flow
- Error handling and retry logic
- Failure propagation in task graphs

---

## 💡 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **DAG-based orchestration** | Tasks have complex dependencies; allows parallel execution |
| **Agent-per-concern** | Clear boundaries, independently testable, composable |
| **Pydantic schemas** | Runtime validation, self-documenting, JSON serialization |
| **Response caching** | Same requirement = free instant re-run; saves API costs |
| **Retry with simpler prompts** | If JSON is truncated, retry asking for less data |
| **Separate output per run** | Compare different requirements side by side |
| **HTML report (no JS deps)** | Works offline, prints to PDF, no build step |
| **Claude Sonnet for code** | Best quality for code generation |

---

## 💰 Cost Management

Each full pipeline run costs approximately **$0.30–$0.50** (6 API calls to Claude Sonnet).

Cost-saving features:
- **Caching**: Same requirement re-runs are free (cached locally in `.cache/`)
- **`--fresh` flag**: Only clears cache when you explicitly want new responses
- **Token tracking**: Every run shows exact cost in the output
- **Individual agents**: Run only what you need with `run_agent.py`

---

## ⚙️ Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Claude API key | (required) |
| Model | Claude model to use | `claude-sonnet-4-6` |
| Cache directory | Where responses are cached | `.cache/` |
| Output directory | Where reports are saved | `output/` |

---

## 🔄 How Caching Works

| Scenario | What happens |
|----------|-------------|
| New requirement | Fresh API calls → cached for next time |
| Same requirement again | Instant (uses cache, $0 cost) |
| `python main.py --fresh` | Clears cache, forces new API calls |
| Different requirement | Fresh API calls (different cache key) |

---

## 📝 Example Commands

```bash
# Greenfield requirement
python main.py -r "Build a scalable URL shortener service with APIs, persistence, and analytics."

# Brownfield requirement
python main.py -r "Refactor the authentication module to support OAuth2 with Google and GitHub"

# Ambiguous requirement
python main.py -r "Make the system faster and more reliable"

# Infrastructure requirement
python main.py -r "Create a secure CI/CD pipeline with automated testing and deployment gates"

# Fill missing sections from last run
python run_agent.py test_generator
python run_agent.py validator

# Web UI
python app.py
```

---

## 🛡️ Controlled Autonomy

The system demonstrates **controlled autonomy** where:

1. **Agents execute independently** — each agent makes decisions within its scope
2. **All decisions are logged** — execution history available for audit
3. **Human checkpoints** — `--interactive` mode pauses for approval at each phase
4. **Partial output on failure** — even if a step fails, prior results are saved
5. **Retry with fallback** — agents retry with simpler prompts if responses fail

---

## 📊 Evaluation Criteria Coverage

| Criterion | How It's Demonstrated |
|-----------|----------------------|
| End-to-end workflow | Requirement → Analysis → Architecture → Code → Tests → Validation → Report |
| System design | Multi-agent architecture with clear separation of concerns |
| Task decomposition | DAG with 8-10 tasks across 6 parallel execution layers |
| Orchestration depth | Cross-step data flow, parallel execution, dependency management |
| Output quality | Production FastAPI code, typed models, async patterns |
| Validation & risk | 6-8 risks with mitigations, trade-offs, guardrails |
| Controlled autonomy | Logged decisions, interactive mode, human review points |

---

## 📄 License

MIT
