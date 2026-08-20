# Example Scenarios

## Scenario 1: Greenfield Requirement (Mandatory Use Case)

### Input
```
"Build a scalable URL shortener service with APIs, persistence, and analytics."
```

### Task Decomposition Output
```
Layer 1: [Design System Architecture]
Layer 2: [Define Data Models] [Design API Contracts]        ← parallel
Layer 3: [Implement Core Service Logic] [Implement Data Access Layer]  ← parallel
Layer 4: [Implement API Endpoints] [Implement Caching Layer]  ← parallel
Layer 5: [Generate Unit Tests] [Generate Integration Tests]   ← parallel
Layer 6: [Validate and Assess Risks]
```

### Multi-step Orchestration Demonstrated
- Architecture design feeds into both data models AND API contracts (fork)
- Code generator uses architecture + data models together (join)
- Tests depend on implementation being complete
- Validator consumes ALL prior outputs (full convergence)

### Output Validation
- 8 code artifacts generated and syntax-validated
- 5 unit tests + 4 integration tests produced
- 6 risks identified with mitigations
- 6 trade-offs documented
- 8 verification steps defined

---

## Scenario 2: Brownfield Requirement

### Input
```python
python main.py --requirement "Refactor the existing user authentication module to support OAuth2.0 with Google and GitHub providers, while maintaining backward compatibility with the current session-based auth."
```

### Expected Analysis
- **Type**: Brownfield
- **Intent**: Add OAuth2.0 without breaking existing auth
- **Key Ambiguities**:
  - Which OAuth2.0 flow? (Authorization Code, PKCE?)
  - Session migration strategy for existing users?
  - Token storage approach?
- **Assumptions Generated**:
  - Authorization Code flow with PKCE for security
  - Existing sessions remain valid; new users get OAuth tokens
  - Both auth methods coexist behind a strategy pattern

### Task Decomposition
```
Layer 1: [Analyze existing auth codebase] [Design OAuth2 integration]
Layer 2: [Define provider interfaces] [Design token storage schema]
Layer 3: [Implement Google provider] [Implement GitHub provider]    ← parallel
Layer 4: [Implement auth strategy selector] [Update middleware]
Layer 5: [Migration script for existing users] [Integration tests]
Layer 6: [Validate backward compatibility]
```

### Key Orchestration Points
- Existing codebase analysis informs architecture decisions
- Two OAuth providers developed in parallel (same interface)
- Backward compatibility verified as final validation step

---

## Scenario 3: Ambiguous Requirement

### Input
```python
python main.py --requirement "Make the system faster and more reliable."
```

### Expected Analysis
- **Type**: Ambiguous
- **Intent**: Performance and reliability improvements (scope unclear)
- **Ambiguities**:
  - Which system? No specific system identified
  - What's the current performance baseline?
  - "Faster" - latency? throughput? both?
  - "Reliable" - uptime SLA? error rate? data durability?
- **Clarification Questions Generated**:
  1. Which system or service should be optimized?
  2. What are current latency/throughput numbers and targets?
  3. What reliability metric matters most (uptime, error rate, RPO/RTO)?
  4. Is there a budget constraint for infrastructure changes?
- **Assumptions (if proceeding without clarification)**:
  - Focus on the most critical path (API response time)
  - Target: 50% latency reduction, 99.9% uptime
  - Approach: caching, connection pooling, circuit breakers

### Demonstration Value
Shows the system's ability to:
- Recognize insufficient information
- Generate meaningful clarification questions
- Make reasonable assumptions to proceed
- Flag assumption-dependency in final report

---

## Running the Examples

```bash
# Scenario 1: Greenfield (default)
python main.py

# Scenario 2: Brownfield
python main.py -r "Refactor the existing user authentication module to support OAuth2.0 with Google and GitHub providers, while maintaining backward compatibility with the current session-based auth."

# Scenario 3: Ambiguous
python main.py -r "Make the system faster and more reliable."

# Interactive mode (any scenario)
python main.py --interactive
```
