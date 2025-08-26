# Full Access Mode Examples

This document showcases various scenarios where full access mode is beneficial for autonomous development tasks.

## 🚨 Security Notice

Full access mode bypasses safety restrictions. Use only in trusted development environments for legitimate development tasks.

## Infrastructure & DevOps Examples

### Complete Production Setup

```yaml
id: INFRA-PROD-001
title: "Setup Complete Production Infrastructure"
description: >
  Configure production-ready infrastructure from scratch:
  - Docker containerization with multi-stage builds
  - Kubernetes deployment manifests and ingress
  - Terraform infrastructure as code
  - GitHub Actions CI/CD pipelines
  - Prometheus/Grafana monitoring stack
  - SSL certificates and domain configuration
  - Database migrations and backups
role: backend
full_access: true
provider_override: "claude_interactive"
acceptance:
  tests:
    - "tests/infrastructure/test_deployment.py"
  lint: true
  typecheck: false
target_dir: "."
```

### Database Migration & Schema Management

```yaml
id: DB-MIGRATION-001
title: "Database Schema Migration and Optimization"
description: >
  Perform complex database operations:
  - Analyze existing schema and identify bottlenecks
  - Create migration scripts for schema changes
  - Set up database replication and backup strategies
  - Implement data archiving and retention policies
  - Add database monitoring and alerting
  - Optimize queries and add appropriate indexes
role: data
full_access: true
provider_override: "codex_interactive"
acceptance:
  tests:
    - "tests/migrations/test_schema_changes.py"
    - "tests/performance/test_query_optimization.py"
  lint: true
  typecheck: true
target_dir: "database"
```

## Advanced Frontend Development

### Framework Migration with Build System Changes

```yaml
id: FRONTEND-MIGRATION-001
title: "Migrate React App to Next.js with Custom Tooling"
description: >
  Complete frontend framework migration:
  - Migrate from Create React App to Next.js
  - Implement custom Webpack configuration
  - Set up advanced build optimization
  - Configure ESLint and Prettier for new setup
  - Implement pre-commit hooks and automated formatting
  - Update all dependencies and resolve conflicts
  - Set up Storybook for component documentation
role: frontend
full_access: true
provider_override: "claude_interactive"
acceptance:
  tests:
    - "tests/frontend/**/*.test.tsx"
    - "tests/e2e/**/*.spec.ts"
  lint: true
  typecheck: true
target_dir: "frontend"
```

### Advanced State Management & Architecture

```yaml
id: FRONTEND-ARCHITECTURE-001
title: "Implement Advanced Frontend Architecture"
description: >
  Build sophisticated frontend architecture:
  - Implement micro-frontend architecture
  - Set up Module Federation with Webpack 5
  - Create advanced state management with Redux Toolkit
  - Implement service worker for offline functionality
  - Add advanced caching strategies
  - Set up performance monitoring and analytics
  - Implement A/B testing framework
role: frontend
full_access: true
provider_override: "codex_interactive"
acceptance:
  tests:
    - "tests/architecture/**/*.test.ts"
    - "tests/performance/**/*.spec.ts"
  lint: true
  typecheck: true
target_dir: "frontend"
```

## Data Engineering & ML Pipeline

### Complete ETL Pipeline with Infrastructure

```yaml
id: DATA-PIPELINE-001
title: "Build Production ETL Pipeline with Monitoring"
description: >
  Create comprehensive data infrastructure:
  - Set up Apache Airflow for workflow orchestration
  - Build Docker containers for data processing jobs
  - Implement data quality checks and validation
  - Create monitoring dashboards with Grafana
  - Set up data lineage tracking
  - Implement automated data backup and recovery
  - Create alerting for pipeline failures
role: data
full_access: true
provider_override: "claude_interactive"
acceptance:
  tests:
    - "tests/data_pipeline/**/*.py"
    - "tests/data_quality/**/*.py"
  lint: true
  typecheck: true
target_dir: "data_pipeline"
```

### ML Model Training & Deployment Pipeline

```yaml
id: ML-PIPELINE-001
title: "ML Model Training and Deployment Infrastructure"
description: >
  Build end-to-end ML infrastructure:
  - Set up MLflow for experiment tracking
  - Create automated model training pipelines
  - Implement model validation and testing
  - Set up model serving with FastAPI and Docker
  - Create monitoring for model drift and performance
  - Implement automated model retraining
  - Set up A/B testing for model variants
role: ml
full_access: true
provider_override: "codex_interactive"
acceptance:
  tests:
    - "tests/ml_pipeline/**/*.py"
    - "tests/model_validation/**/*.py"
  lint: true
  typecheck: true
target_dir: "ml_pipeline"
```

## Security & Compliance

### Security Hardening & Compliance Setup

```yaml
id: SECURITY-AUDIT-001
title: "Security Hardening and Compliance Implementation"
description: >
  Implement comprehensive security measures:
  - Set up dependency scanning and vulnerability management
  - Implement SAST/DAST security testing in CI/CD
  - Configure secrets management with HashiCorp Vault
  - Set up log aggregation and security monitoring
  - Implement authentication and authorization improvements
  - Create security compliance reporting
  - Set up penetration testing automation
role: backend
full_access: true
provider_override: "claude_interactive"
acceptance:
  tests:
    - "tests/security/**/*.py"
    - "tests/compliance/**/*.py"
  lint: true
  typecheck: true
target_dir: "security"
```

## Performance Optimization

### Full Stack Performance Optimization

```yaml
id: PERF-OPTIMIZATION-001
title: "Comprehensive Performance Optimization"
description: >
  Optimize entire application stack:
  - Profile application and identify bottlenecks
  - Implement caching strategies (Redis, CDN)
  - Optimize database queries and add indexes
  - Implement connection pooling and async processing
  - Set up load balancing and auto-scaling
  - Optimize frontend bundle size and loading
  - Implement performance monitoring and alerting
role: backend
full_access: true
provider_override: "codex_interactive"
acceptance:
  tests:
    - "tests/performance/**/*.py"
    - "tests/load_testing/**/*.py"
  lint: true
  typecheck: true
target_dir: "."
```

## Multi-Service Architecture

### Microservices Migration

```yaml
id: MICROSERVICES-001
title: "Migrate Monolith to Microservices Architecture"
description: >
  Break monolith into microservices:
  - Analyze monolith and identify service boundaries
  - Create separate service repositories and configurations
  - Implement service-to-service communication
  - Set up API gateway and service discovery
  - Implement distributed tracing and logging
  - Create deployment strategies for multiple services
  - Set up monitoring and alerting for service mesh
role: backend
full_access: true
provider_override: "claude_interactive"
acceptance:
  tests:
    - "tests/integration/**/*.py"
    - "tests/microservices/**/*.py"
  lint: true
  typecheck: true
target_dir: "."
```

## Usage Examples

### Submitting Full Access Tasks

```bash
# Submit infrastructure task
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d @examples/infra-prod-task.yaml

# Submit with explicit full access via API
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "CUSTOM-FULL-ACCESS-001",
    "title": "Custom Full Access Task", 
    "description": "Task requiring unrestricted development access",
    "role": "backend",
    "full_access": true,
    "provider_override": "claude_interactive",
    "acceptance": {
      "tests": [],
      "lint": true,
      "typecheck": true
    },
    "target_dir": "."
  }'
```

### Monitoring Full Access Tasks

```bash
# Check task status
curl http://localhost:8000/tasks/INFRA-PROD-001

# Monitor git branches for full access tasks
git branch -a | grep auto/ | grep -E "(infra|migration|optimization)"

# View logs for full access task execution
tail -f logs/orchestrator.log | grep "INFRA-PROD-001"
```

## Best Practices

### 1. Use Full Access Sparingly
Only enable full access for tasks that genuinely require system-level operations or unrestricted file access.

### 2. Choose the Right Provider
- **Claude Interactive** (`claude_interactive`) - Better for architectural decisions and complex reasoning
- **Codex Interactive** (`codex_interactive`) - Better for code generation and technical implementation

### 3. Comprehensive Testing
Always include thorough acceptance criteria for full access tasks since they can make significant system changes.

### 4. Monitor and Review
- Review git commits from full access tasks carefully
- Use worktrees to isolate full access task changes
- Enable branch protection rules for production environments

### 5. Environment Isolation  
Run full access tasks in development environments first before applying to staging/production.

## Troubleshooting Full Access Mode

### CLI Not Found
```bash
# Verify CLI installation
claude --version
codex --version

# Test full access flags
claude --dangerously-skip-permissions -p "test"
codex --ask-for-approval never --sandbox danger-full-access exec "test"
```

### Permission Denied
```bash
# Check file permissions
ls -la scripts/init-full-access.sh

# Make script executable
chmod +x scripts/init-full-access.sh
```

### Task Stuck in Queue
```bash
# Check worker status
rq worker --url redis://localhost:6379

# Restart with full access provider order
# Edit config/config.yaml to ensure full_access_order is configured
```

Full access mode enables powerful autonomous development capabilities when used responsibly in appropriate environments.