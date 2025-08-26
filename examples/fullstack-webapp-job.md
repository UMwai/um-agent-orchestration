# Full Stack Web App Job Example

This example demonstrates how to submit and launch a job for a sample full stack web application using the AutoDev orchestration system.

## Prerequisites & Setup

Before submitting jobs, ensure your environment is properly configured:

### 1. Initial Setup
```bash
# Clone and setup the repository
git clone <your-repo>
cd um-agent-orchestration

# Install dependencies and configure environment
make install
cp .env.example .env
# Edit .env file with your API keys and configuration

# Optional: Setup full access mode for unrestricted development
./scripts/init-full-access.sh
```

### 2. Start the Orchestrator System
```bash
# Terminal 1: Start the FastAPI orchestrator server
make dev  # Starts server at localhost:8000

# Terminal 2: Start Redis and RQ worker
make run

# Terminal 3 (optional): Start additional workers for parallel processing
make workers
```

### 3. Verify System Health
```bash
# Check orchestrator is running
curl http://localhost:8000/docs

# Check metrics endpoint
curl http://localhost:8000/metrics
```

## Sample Full Stack Web App Job

### Frontend Task Example

Create a task specification for building the frontend components:

**File: `examples/frontend-task.yaml`**
```yaml
id: WEBAPP-FRONTEND-001
title: "Build React Todo App Frontend"
description: >
  Create a modern React TypeScript frontend for a todo application with:
  - Todo list component with add/edit/delete functionality
  - Responsive design using Tailwind CSS or similar
  - State management with React hooks or Redux Toolkit
  - API integration for CRUD operations
  - Unit tests with React Testing Library
role: frontend
full_access: false  # Standard mode - safe for UI development
acceptance:
  tests:
    - "tests/frontend/test_todo_components.test.tsx"
    - "tests/frontend/test_app_integration.test.tsx"
  lint: true
  typecheck: true
target_dir: "frontend"
```

**File: `examples/frontend-task-full-access.yaml`** (Advanced Version)
```yaml
id: WEBAPP-FRONTEND-002
title: "Build Advanced React Todo App with Full Stack Integration"
description: >
  Create a comprehensive React TypeScript frontend with full development autonomy:
  - Complete project scaffolding with Vite/Next.js
  - Advanced state management with Zustand or Redux Toolkit
  - E2E testing with Playwright
  - Automated deployment configuration
  - Performance optimization and bundling
  - Full CI/CD pipeline setup
role: frontend
full_access: true  # Enable full access for complex setup
provider_override: "claude_interactive"  # Force Claude with full permissions
acceptance:
  tests:
    - "tests/frontend/**/*.test.tsx"
    - "tests/e2e/**/*.spec.ts"
  lint: true
  typecheck: true
target_dir: "frontend"
```

### Backend Task Example

Create a task specification for the backend API:

**File: `examples/backend-task.yaml`**
```yaml
id: WEBAPP-BACKEND-001
title: "Build FastAPI Todo Backend"
description: >
  Create a FastAPI backend for a todo application with:
  - SQLAlchemy models for Todo items
  - CRUD endpoints: GET/POST/PUT/DELETE /todos
  - PostgreSQL database integration
  - Pydantic schemas for validation
  - Authentication middleware
  - Comprehensive test coverage
role: backend
full_access: true  # Backend often needs system access for DB setup
provider_override: "codex_interactive"  # Use Codex for backend development
acceptance:
  tests:
    - "tests/backend/test_todo_api.py"
    - "tests/backend/test_auth.py"
  lint: true
  typecheck: true
target_dir: "backend"
```

### Data Pipeline Task Example

Create a task for analytics and reporting:

**File: `examples/data-task.yaml`**
```yaml
id: WEBAPP-DATA-001
title: "Todo Analytics Pipeline"
description: >
  Build data pipeline for todo app analytics:
  - ETL pipeline to extract todo completion metrics
  - Data warehouse schema for user behavior analysis
  - Daily/weekly reporting dashboards
  - User engagement scoring algorithm
role: data
acceptance:
  tests:
    - "tests/data/test_etl_pipeline.py"
    - "tests/data/test_analytics.py"
  lint: true
  typecheck: true
target_dir: "analytics"
```

## Full Access Mode vs Standard Mode

### When to Use Full Access Mode

**Use Full Access Mode (`full_access: true`) for:**
- Complex project scaffolding and setup
- Database migrations and schema changes  
- System configuration and deployment scripts
- CI/CD pipeline configuration
- Advanced tooling setup (Docker, K8s, etc.)
- Tasks requiring unrestricted file system access

**Use Standard Mode (`full_access: false` or omitted) for:**
- Simple feature development
- UI/UX components and styling
- Business logic implementation
- Unit test writing
- Documentation updates

### Full Access Mode Examples

```yaml
# Complex infrastructure task
id: WEBAPP-DEVOPS-001
title: "Setup Production Infrastructure"
description: "Configure Docker, K8s, CI/CD, monitoring, and deployment"
role: backend
full_access: true
provider_override: "claude_interactive"

# Advanced frontend with build system changes
id: WEBAPP-FRONTEND-ADVANCED-001  
title: "Migrate to Next.js with Custom Webpack Config"
description: "Complete migration from CRA to Next.js with custom tooling"
role: frontend
full_access: true
provider_override: "codex_interactive"
```

## Submitting Jobs

### Method 1: Using curl (REST API)
```bash
# Submit frontend task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "id": "WEBAPP-FRONTEND-001",
    "title": "Build React Todo App Frontend",
    "description": "Create a modern React TypeScript frontend...",
    "role": "frontend",
    "acceptance": {
      "tests": ["tests/frontend/test_todo_components.test.tsx"],
      "lint": true,
      "typecheck": true
    },
    "target_dir": "frontend"
  }'

# Submit backend task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d @examples/backend-task.yaml

# Submit data pipeline task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d @examples/data-task.yaml
```

### Method 2: Using Python requests
```python
import requests
import yaml

# Load task specification
with open('examples/frontend-task.yaml', 'r') as f:
    task_spec = yaml.safe_load(f)

# Submit task
response = requests.post('http://localhost:8000/tasks', json=task_spec)
result = response.json()

print(f"Job ID: {result['job_id']}")
print(f"Task ID: {result['task_id']}")
```

## Monitoring Job Progress

### Check Task Status
```bash
# Get task status by task ID
curl http://localhost:8000/tasks/WEBAPP-FRONTEND-001

# Example response:
# {
#   "id": "WEBAPP-FRONTEND-001",
#   "role": "frontend", 
#   "branch": "auto/frontend/WEBAPP-FRONTEND-001",
#   "state": "running",
#   "last_error": null
# }
```

### Monitor Git Branches
```bash
# View all active feature branches
git branch -a | grep auto/

# Check specific task branch
git log auto/frontend/WEBAPP-FRONTEND-001 --oneline

# View worktree status
ls -la worktrees/
```

### View System Metrics
```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics

# Start monitoring dashboard (if configured)
make monitoring
```

## Job Lifecycle

1. **Submission**: Task submitted via POST `/tasks` with role specification
2. **Queuing**: Task queued in Redis, assigned to role-specific agent  
3. **Execution**: Agent creates feature branch in dedicated git worktree
4. **Provider Routing**: System tries providers in configured order (CLI-first)
5. **Development**: Agent implements solution following role-specific guidelines
6. **Testing**: Runs acceptance tests, linting, and type checking
7. **Auto-commit**: Commits progress every 30 minutes via systemd timer
8. **Auto-PR**: Creates pull request every 2 hours for review
9. **Completion**: Task marked as "passed", "failed", or "error"

## Troubleshooting

### Common Issues

**Task stuck in "queued" state:**
```bash
# Check RQ worker status
rq worker --url redis://localhost:6379

# Restart workers
make run
```

**Provider failures:**
```bash
# Check provider configuration
cat config/config.yaml | grep -A 20 providers

# Test Claude CLI directly
claude -p "Hello, test message"

# Check API keys in .env
grep -E "(ANTHROPIC|OPENAI|GEMINI)" .env
```

**Git worktree conflicts:**
```bash
# Clean up stale worktrees
git worktree prune

# List active worktrees
git worktree list
```

### Logs and Debugging
```bash
# View orchestrator logs
tail -f logs/orchestrator.log

# RQ worker logs
rq worker --logging_level DEBUG

# Enable detailed monitoring
make monitoring
# Then visit Grafana at http://localhost:3000
```

## Advanced Configuration

### Custom Roles
Create custom roles for your specific needs:

**File: `roles/fullstack_lead.yaml`**
```yaml
name: fullstack_lead
branch_prefix: "feat/fullstack"
reviewers: ["@org/tech-leads"]
prompt: |
  You are a full-stack technical lead. Coordinate between frontend and backend,
  ensure consistent API contracts, implement integration tests, and maintain
  architectural coherence across the stack.
```

### Provider Preferences
Customize provider order in `config/config.yaml`:
```yaml
providers:
  order:
    - "claude_cli"      # Prefer Claude for complex reasoning
    - "cursor_cli"      # Good for code generation
    - "codex_cli"       # Fallback for specific tasks
    - "anthropic_api"   # API fallback
```

### Git Hygiene Settings
Adjust auto-commit and PR timing:
```yaml
hygiene:
  checkpoint_minutes: 15  # More frequent commits
  pr_minutes: 60         # Faster PR creation
  conventional_commits: true
```

This example provides a complete workflow for orchestrating full stack web application development using the AutoDev multi-agent system.