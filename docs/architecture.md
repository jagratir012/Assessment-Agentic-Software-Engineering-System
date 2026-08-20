# Architecture Overview

## System Components

### 1. Agents

Each agent is a specialized unit with a single responsibility:

| Agent | Responsibility | Inputs | Outputs |
|-------|---------------|--------|---------|
| RequirementAnalyzer | Parse, classify, normalize requirements | Raw text | AnalyzedRequirement |
| TaskDecomposer | Break into dependency-aware task DAG | AnalyzedRequirement | TaskGraph |
| Architect | Design system architecture & APIs | AnalyzedRequirement | ArchitectureDesign |
| CodeGenerator | Generate production code | ArchitectureDesign | CodeArtifact[] |
| TestGenerator | Create unit & integration tests | CodeArtifact[], Architecture | TestSuite |
| Validator | Assess risks, define guardrails | All outputs | ValidationReport |

### 2. Orchestrator

The `WorkflowEngine` coordinates agents through a `TaskGraph`:

- **TaskGraph**: DAG-based dependency manager with topological layer computation
- **WorkflowEngine**: Executes tasks layer-by-layer, manages cross-step data flow

### 3. Tools

- **FileWriter**: Writes generated artifacts to disk
- **CodeValidator**: AST-based Python syntax validation

### 4. Models (Pydantic Schemas)

All data flowing between agents is strongly typed using Pydantic:
- `Requirement` → `AnalyzedRequirement` → `TaskGraph` → `ArchitectureDesign` → `CodeArtifact` → `TestSuite` → `ValidationReport` → `EngineeringSummary`

## Execution Model

```
Input: Raw Requirement Text
         │
         ▼
┌─────────────────────────┐
│  RequirementAnalyzer    │  ← Phase 1: Understand
│  - Classify type        │
│  - Extract FRs/NFRs     │
│  - Identify ambiguities │
└────────────┬────────────┘
             │ AnalyzedRequirement
             ▼
┌─────────────────────────┐
│  TaskDecomposer         │  ← Phase 2: Plan
│  - Generate task DAG    │
│  - Compute exec layers  │
│  - Assign to agents     │
└────────────┬────────────┘
             │ TaskGraph
             ▼
┌─────────────────────────────────────────────┐
│  WorkflowEngine                             │  ← Phase 3: Execute
│                                             │
│  Layer 1: [Architecture Design]             │
│  Layer 2: [Data Models] [API Contracts]     │  ← Parallel tasks
│  Layer 3: [Core Logic] [Data Access]        │  ← Parallel tasks
│  Layer 4: [API Endpoints] [Caching]         │  ← Parallel tasks
│  Layer 5: [Unit Tests] [Integration Tests]  │  ← Parallel tasks
│  Layer 6: [Validation]                      │
│                                             │
│  Cross-step coordination:                   │
│  - Outputs of Layer N feed into Layer N+1   │
│  - Shared context accumulates all outputs   │
│  - Error in one task blocks dependents      │
└────────────┬────────────────────────────────┘
             │ All outputs
             ▼
┌─────────────────────────┐
│  Output Generation      │  ← Phase 4: Produce
│  - Validate code (AST)  │
│  - Write to disk        │
│  - Generate summary     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  EngineeringSummary     │  ← Phase 5: Report
│  - Implementation plan  │
│  - Generated artifacts  │
│  - Risks & trade-offs   │
│  - Validation approach  │
└─────────────────────────┘
```

## Key Design Decisions

### 1. DAG-based Task Orchestration (vs. Linear Pipeline)

**Choice**: Directed Acyclic Graph with topological sorting
**Rationale**: Tasks have complex dependencies (not just A→B→C). DAG allows:
- Parallel execution of independent tasks
- Proper dependency tracking
- Failure propagation without re-executing completed work

### 2. Agent-per-Concern (vs. Monolithic)

**Choice**: Separate agent for each SDLC phase
**Rationale**:
- Clear responsibility boundaries
- Independently testable
- Composable for different workflows
- Easy to add new agents without modifying existing ones

### 3. Pydantic Models for Inter-Agent Communication

**Choice**: Strongly-typed Pydantic schemas
**Rationale**:
- Runtime validation catches data flow errors early
- Self-documenting interfaces
- JSON serialization for persistence/debugging
- IDE autocompletion support

### 4. Mock/Deterministic Mode (vs. LLM-only)

**Choice**: Built-in deterministic execution with optional LLM enhancement
**Rationale**:
- Reproducible demonstrations without API keys
- Testable without external dependencies
- Shows the orchestration logic clearly
- LLM can be layered on top for dynamic generation

### 5. Retry with Exponential Backoff

**Choice**: Per-task retry with configurable limits
**Rationale**:
- Transient failures (network, rate limits) self-heal
- Permanent failures propagate to block dependents
- Prevents infinite loops with max retry cap

## Control Flow

```
Human Input → Requirement → [Analyze] → Approval Gate (interactive)
                                          │
                                          ▼
                              [Decompose] → Approval Gate
                                          │
                                          ▼
                              [Execute Workflow]
                                   │
                              ┌────┴────┐
                              ▼         ▼
                          [Agents]  [Agents]  ← Parallel execution
                              │         │
                              └────┬────┘
                                   ▼
                          [Validate & Report]
                                   │
                                   ▼
                          Human Review ← Controlled Autonomy
```

## Extensibility

The system is designed for extension:

1. **New Agents**: Implement `BaseAgent.execute()` and register in `WorkflowEngine`
2. **New Scenarios**: Add requirement handling logic to `RequirementAnalyzerAgent`
3. **LLM Integration**: Replace deterministic methods with LLM calls (OpenAI client ready)
4. **New Tools**: Add to `src/tools/` and inject into pipeline
5. **Brownfield Support**: Feed existing codebase context into `RequirementAnalyzer`
