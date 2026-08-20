# Testing Approach

## How Correctness and Output Quality Are Validated

### 1. System-Level Tests (this system)

```bash
pytest tests/ -v
```

Tests verify:
- Requirement analysis produces correct classification and extraction
- Task decomposition generates valid DAGs (no cycles, correct dependencies)
- Workflow engine executes tasks in correct order
- Agents handle errors and retry correctly
- Generated code passes AST validation

### 2. Generated Output Validation

The system validates its own outputs through:

1. **AST Parsing**: All generated Python code is parsed with `ast.parse()` to confirm syntax validity
2. **Schema Conformance**: Pydantic models validate all inter-agent data
3. **Dependency Integrity**: TaskGraph verifies no circular dependencies
4. **Coverage Estimation**: Test generator estimates coverage based on code paths

### 3. Quality Metrics

| Metric | Target | How Verified |
|--------|--------|--------------|
| Code syntax validity | 100% | AST parsing |
| Task dependency correctness | No cycles | Topological sort succeeds |
| Requirement coverage | All FRs addressed | Cross-reference tasks to requirements |
| Risk identification | ≥5 risks per scenario | Validator output count |
| Test case relevance | Each test targets a specific behavior | Test description review |

### 4. Manual Review Points (Controlled Autonomy)

In interactive mode, humans validate:
- Requirement interpretation is correct
- Assumptions are reasonable
- Task plan covers all requirements
- Generated code meets standards
- Risk assessment is complete

## Known Limitations

1. **Deterministic Generation**: The prototype uses templated code generation rather than dynamic LLM-based generation. This means:
   - Outputs are predictable and reproducible
   - But limited to pre-built scenarios (URL shortener, common patterns)
   - LLM integration (OpenAI) is architecturally ready but optional

2. **No Actual Compilation/Execution**: Generated code is syntax-validated but not compiled or executed within the pipeline. In production, this would include:
   - Docker-based build verification
   - Actual test execution
   - Integration environment spin-up

3. **Single-Language Output**: Currently generates Python/FastAPI only. Architecture supports multi-language via additional CodeGenerator strategies.

4. **Brownfield Scope**: Codebase reasoning is demonstrated through classification and assumption generation, but does not parse actual existing codebases (would require AST analysis tools in production).

5. **No Persistent State**: Each run is independent. Production system would persist previous analyses for learning and reuse.

## Trade-offs in Testing Strategy

| Decision | Trade-off |
|----------|-----------|
| AST validation only (no execution) | Fast, no dependencies, but misses runtime errors |
| Pydantic schema validation | Catches structural errors, but not semantic correctness |
| Deterministic outputs | Reproducible tests, but doesn't test dynamic generation paths |
| Template-based generation | Predictable quality, but limited flexibility |
| No external dependency tests | Runs anywhere, but doesn't verify Redis/PostgreSQL integration |
