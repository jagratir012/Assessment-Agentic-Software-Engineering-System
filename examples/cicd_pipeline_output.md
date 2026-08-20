# Example: Secure CI/CD Pipeline (Processed Output)

## Input Requirement
```
"Create a secure CI/CD pipeline with automated testing, vulnerability scanning, secrets management, and deployment gates"
```

## Phase 1: Requirement Analysis

**Type**: Greenfield  
**Intent**: Design and implement a secure, automated CI/CD pipeline that integrates testing, security scanning, secrets management, and manual/automated deployment approval gates.

### Functional Requirements
1. Automated build triggering on code push/PR
2. Multi-stage pipeline: build → test → scan → deploy
3. Unit test and integration test execution with reporting
4. Static Application Security Testing (SAST)
5. Dependency vulnerability scanning (SCA)
6. Container image scanning
7. Secrets management via vault integration (no plaintext secrets)
8. Manual approval gates for production deployments
9. Automated rollback on deployment failure
10. Audit logging of all pipeline executions

### Non-Functional Requirements
- Pipeline execution < 15 minutes for standard builds
- Secrets never exposed in logs or artifacts
- Support for multiple environments (dev/staging/prod)
- Idempotent deployments
- Integration with GitHub/GitLab webhooks

### Ambiguities Identified
- Target cloud provider not specified (AWS/GCP/Azure?)
- CI/CD tool not specified (GitHub Actions, Jenkins, GitLab CI?)
- Container-based or VM-based deployments?
- What secret vault? (HashiCorp Vault, AWS Secrets Manager, etc.)
- Compliance requirements (SOC2, HIPAA, etc.)?

### Assumptions Made
- GitHub Actions as CI/CD platform (most common, portable)
- AWS as deployment target with ECS/EKS
- HashiCorp Vault for secrets management
- Docker-based containerized deployments
- No specific compliance framework (general best practices)

---

## Phase 2: Task Decomposition

```
Layer 1: [Design Pipeline Architecture]
Layer 2: [Define Pipeline Stages] [Design Secrets Integration]         ← parallel
Layer 3: [Implement Build Stage] [Implement Test Stage]                ← parallel
Layer 4: [Implement Security Scanning] [Implement Secrets Injection]   ← parallel
Layer 5: [Implement Deployment Gates] [Implement Rollback Logic]       ← parallel
Layer 6: [Generate Pipeline Tests] [Documentation]                     ← parallel
Layer 7: [Validate and Risk Assessment]
```

---

## Phase 3: Generated Architecture

### Components
| Component | Responsibility | Technology |
|-----------|---------------|------------|
| Pipeline Engine | Workflow execution | GitHub Actions |
| Build Stage | Compile, lint, package | Docker multi-stage |
| Test Stage | Unit + integration tests | pytest/jest + testcontainers |
| SAST Scanner | Static code analysis | Semgrep / CodeQL |
| SCA Scanner | Dependency vulnerabilities | Trivy / Snyk |
| Image Scanner | Container CVE detection | Trivy |
| Secrets Manager | Inject secrets at runtime | HashiCorp Vault |
| Deployment Gate | Manual/auto approval | GitHub Environments |
| Rollback Controller | Revert failed deployments | Helm/ArgoCD |
| Audit Logger | Pipeline execution records | CloudWatch/ELK |

### Pipeline Flow
```
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌────────────┐
│  Build   │───▶│   Test   │───▶│   Security   │───▶│  Approval  │
│  Stage   │    │  Stage   │    │    Scan      │    │    Gate    │
└──────────┘    └──────────┘    └──────────────┘    └─────┬──────┘
                                                          │
                                                          ▼
                                                   ┌────────────┐
                                                   │   Deploy   │
                                                   │  (+ watch) │
                                                   └─────┬──────┘
                                                         │
                                              ┌──────────┴──────────┐
                                              ▼                     ▼
                                        ┌──────────┐         ┌──────────┐
                                        │ Success  │         │ Rollback │
                                        └──────────┘         └──────────┘
```

---

## Phase 4: Generated Code Artifacts

### 1. GitHub Actions Workflow (`.github/workflows/ci-cd.yml`)
```yaml
name: Secure CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  test:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4
      
      - name: Run unit tests
        run: |
          pip install -r requirements.txt
          pytest tests/unit/ --junitxml=reports/unit.xml --cov=src
      
      - name: Run integration tests
        run: pytest tests/integration/ --junitxml=reports/integration.xml
      
      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: reports/

  security-scan:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4
      
      - name: SAST - CodeQL Analysis
        uses: github/codeql-action/analyze@v3
      
      - name: SCA - Dependency scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
      
      - name: Container image scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

  deploy-staging:
    runs-on: ubuntu-latest
    needs: [test, security-scan]
    environment: staging
    steps:
      - name: Import secrets from Vault
        uses: hashicorp/vault-action@v2
        with:
          url: ${{ secrets.VAULT_ADDR }}
          token: ${{ secrets.VAULT_TOKEN }}
          secrets: |
            secret/data/staging/db DB_URL ;
            secret/data/staging/api API_KEY
      
      - name: Deploy to staging
        run: |
          helm upgrade --install app ./helm \
            --namespace staging \
            --set image.tag=${{ github.sha }} \
            --set secrets.dbUrl="${{ env.DB_URL }}"

  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    environment:
      name: production
      url: https://app.example.com
    steps:
      - name: Import production secrets
        uses: hashicorp/vault-action@v2
        with:
          url: ${{ secrets.VAULT_ADDR }}
          token: ${{ secrets.VAULT_TOKEN }}
          secrets: |
            secret/data/prod/db DB_URL ;
            secret/data/prod/api API_KEY
      
      - name: Deploy to production
        run: |
          helm upgrade --install app ./helm \
            --namespace production \
            --set image.tag=${{ github.sha }} \
            --wait --timeout=5m
      
      - name: Verify deployment health
        run: |
          for i in {1..10}; do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://app.example.com/health)
            if [ "$STATUS" = "200" ]; then exit 0; fi
            sleep 5
          done
          echo "Health check failed - triggering rollback"
          helm rollback app --namespace production
          exit 1
```

### 2. Vault Secrets Policy (`vault/policy.hcl`)
```hcl
# Staging secrets - CI/CD read-only access
path "secret/data/staging/*" {
  capabilities = ["read"]
}

# Production secrets - requires additional approval
path "secret/data/prod/*" {
  capabilities = ["read"]
  required_parameters = ["request_id"]
}

# Deny access to secret metadata
path "secret/metadata/*" {
  capabilities = ["deny"]
}
```

### 3. Rollback Script (`scripts/rollback.sh`)
```bash
#!/bin/bash
set -euo pipefail

NAMESPACE="${1:-production}"
RELEASE="app"
MAX_HISTORY=5

echo "Rolling back ${RELEASE} in ${NAMESPACE}..."

# Get current revision
CURRENT=$(helm history ${RELEASE} -n ${NAMESPACE} --max 1 -o json | jq '.[0].revision')
TARGET=$((CURRENT - 1))

if [ ${TARGET} -lt 1 ]; then
  echo "ERROR: No previous revision to rollback to"
  exit 1
fi

helm rollback ${RELEASE} ${TARGET} -n ${NAMESPACE} --wait --timeout=3m

echo "Rollback complete. Verifying health..."
kubectl rollout status deployment/${RELEASE} -n ${NAMESPACE} --timeout=60s
```

---

## Phase 5: Validation & Risk Assessment

### Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Secrets leaked in pipeline logs | CRITICAL | Use masking, never echo secrets, audit log review |
| False positive in security scan blocks deploy | MEDIUM | Severity thresholds, exception list with expiry |
| Pipeline compromise via supply chain attack | HIGH | Pin action versions by SHA, verify checksums |
| Approval gate bypassed | HIGH | Branch protection rules, require CODEOWNERS review |
| Rollback fails, stuck deployment | MEDIUM | Blue/green deployment strategy, manual override |
| Vault unavailable during deployment | HIGH | Cache last-known secrets (encrypted), circuit breaker |

### Trade-offs
- **Strict security scan thresholds vs. developer velocity**: Blocking on HIGH vulns may slow development
- **Manual gates vs. fully automated**: Safer but slower time-to-production
- **Single pipeline vs. environment-specific**: Simpler maintenance but less flexibility
- **Vault vs. native cloud secrets**: More portable but added infrastructure

### Guardrails
- Branch protection: main requires PR + 1 approval
- No direct push to main or production branches
- Secrets masked in all log output
- All action versions pinned to specific SHA (not tags)
- Pipeline timeout: 30 min max
- Deployment window restrictions (no Friday deploys)
- Automated rollback on health check failure
