# AGENTS.md

This file provides comprehensive guidance for multi-agent task distribution and coordination patterns. Works in conjunction with CLAUDE.md to enable parallel task execution across specialized AI agents.

## Multi-Agent Architecture

The system supports multiple AI agents working in parallel, each with specialized roles and capabilities:

- **Claude Code** (`claude`): Primary orchestrator and generalist
- **Codex** (`codex`): Code-focused specialist with full access capabilities
- **Gemini** (`gemini`): Alternative provider for specific tasks
- **Cursor** (`cursor-agent`): IDE-integrated development agent

Model Defaults
- OpenAI API default model: gpt-5
- Configure via `config/config.yaml` under `providers.openai_api.model: "gpt-5"`.
- CLI agents pass model hints in prompts; API calls respect the configured model.

## Agent Roles and Specialization

### Primary Orchestrator (Claude)
```bash
# Launch as primary coordinator
claude --dangerously-skip-permissions

# Load orchestration helpers
exec(open('scripts/agent_helpers.py').read())

# Coordinate multi-agent tasks
coordinate_agents()
distribute_task("feature-implementation", ["backend", "frontend", "testing"])
monitor_agent_progress()
```

**Responsibilities:**
- Task decomposition and assignment
- Progress monitoring and coordination  
- Integration testing and quality assurance
- Final review and merge coordination

### Backend Specialist (Codex)
```bash
# Launch backend-focused agent
codex --ask-for-approval never --sandbox danger-full-access exec "Handle backend development"

# Load backend-specific configurations
exec(open('scripts/agent_helpers.py').read())
load_agent_role('backend')

# Backend task patterns
handle_api_development()
manage_database_changes()
implement_business_logic()
```

**Specializes in:**
- FastAPI endpoint development (`orchestrator/`)
- Database schema and models (`orchestrator/models.py`, `orchestrator/persistence.py`)
- Queue management (`orchestrator/queue.py`)
- Provider integrations (`providers/`)

### Frontend Specialist (Codex)
```bash
# Launch frontend-focused agent  
codex --ask-for-approval never --sandbox danger-full-access exec "Handle frontend development"

# Load frontend-specific configurations
exec(open('scripts/agent_helpers.py').read())
load_agent_role('frontend')

# Frontend task patterns
develop_dashboard_components()
implement_websocket_client()
handle_ui_interactions()
```

**Specializes in:**
- Dashboard development (`dashboard/`)
- WebSocket client implementation
- UI/UX improvements
- Frontend testing and validation

### Infrastructure Specialist (Codex)
```bash
# Launch infrastructure-focused agent
codex --ask-for-approval never --sandbox danger-full-access exec "Handle infrastructure tasks"

# Load infrastructure-specific configurations  
exec(open('scripts/agent_helpers.py').read())
load_agent_role('infrastructure')

# Infrastructure task patterns
manage_deployment_configs()
monitor_system_health()
optimize_performance()
```

**Specializes in:**
- GitOps and worktree management (`gitops/`)
- Monitoring and metrics (`monitoring/`)
- Configuration management (`config/`)
- CI/CD pipeline optimization

### Testing and QA Specialist (Codex)
```bash
# Launch testing-focused agent
codex --ask-for-approval never --sandbox danger-full-access exec "Handle testing and QA"

# Load testing-specific configurations
exec(open('scripts/agent_helpers.py').read())  
load_agent_role('testing')

# Testing task patterns
implement_test_suites()
perform_integration_testing()
validate_security_requirements()
```

**Specializes in:**
- Test implementation (`tests/`)
- Security validation
- Performance testing
- Acceptance criteria verification

## Task Distribution Patterns

### Pattern 1: Feature Development Pipeline
```bash
# 1. Primary orchestrator decomposes feature
claude --dangerously-skip-permissions
exec(open('scripts/agent_helpers.py').read())
decompose_feature("user-authentication", ["backend", "frontend", "security", "testing"])

# 2. Backend agent handles API development
codex --ask-for-approval never --sandbox danger-full-access exec "Implement authentication API"

# 3. Frontend agent handles UI components  
codex --ask-for-approval never --sandbox danger-full-access exec "Implement authentication UI"

# 4. Security agent reviews and hardens
codex --ask-for-approval never --sandbox danger-full-access exec "Security review authentication"

# 5. Testing agent validates implementation
codex --ask-for-approval never --sandbox danger-full-access exec "Test authentication flow"

# 6. Orchestrator integrates and reviews
claude --dangerously-skip-permissions
integrate_feature_components()
```

### Pattern 2: Bug Fix Coordination
```bash
# 1. Orchestrator analyzes bug report
claude --dangerously-skip-permissions
exec(open('scripts/agent_helpers.py').read())
analyze_bug("AUTH-501", "Login endpoint returns 500 error")

# 2. Backend agent investigates and fixes
codex --ask-for-approval never --sandbox danger-full-access exec "Fix AUTH-501 backend issue"

# 3. Testing agent validates fix
codex --ask-for-approval never --sandbox danger-full-access exec "Verify AUTH-501 fix"

# 4. Orchestrator ensures regression testing
claude --dangerously-skip-permissions  
run_regression_suite("authentication")
```

### Pattern 3: Parallel Development
```bash
# Multiple agents working simultaneously on different components

# Terminal 1: Backend API development
codex --ask-for-approval never --sandbox danger-full-access exec "Develop user management API"

# Terminal 2: Frontend component development  
codex --ask-for-approval never --sandbox danger-full-access exec "Build user management UI"

# Terminal 3: Database schema updates
codex --ask-for-approval never --sandbox danger-full-access exec "Update user management schema"

# Terminal 4: Orchestrator monitoring progress
claude --dangerously-skip-permissions
exec(open('scripts/agent_helpers.py').read())
monitor_parallel_development()
```

## Agent Communication and Synchronization

### Shared State Management
```python
# All agents share state through Redis and database
exec(open('scripts/agent_helpers.py').read())

# Update task progress
update_task_status("TASK-123", "in_progress", "Implementing authentication API")

# Check dependencies
dependencies = check_task_dependencies("TASK-124") 

# Coordinate with other agents
notify_agent_completion("backend-auth-api", "TASK-123")
wait_for_dependency("frontend-auth-ui", "TASK-123")
```

### Git Worktree Coordination
```bash
# Each agent works in isolated worktrees
exec(open('scripts/agent_helpers.py').read())

# Backend agent
create_worktree("backend/auth-api", "feature/auth-api-implementation")

# Frontend agent  
create_worktree("frontend/auth-ui", "feature/auth-ui-components")

# Orchestrator manages merges
coordinate_worktree_merges(["feature/auth-api-implementation", "feature/auth-ui-components"])
```

## Configuration and Role Management

### Agent Role Configuration
```yaml
# roles/backend.yaml
name: "backend"
branch_prefix: "backend/"
specialization: "API and service development"
full_access: true
reviewers: ["senior-backend-dev"]
prompt: |
  You are a backend development specialist. Focus on:
  - FastAPI endpoint implementation
  - Database operations and models
  - Service layer logic
  - Provider integrations
  
# roles/frontend.yaml  
name: "frontend"
branch_prefix: "frontend/"
specialization: "UI and client development"
full_access: true
reviewers: ["senior-frontend-dev"]
prompt: |
  You are a frontend development specialist. Focus on:
  - Dashboard and UI components
  - WebSocket client implementation
  - User experience optimization
  - Frontend testing
```

Model Configuration
```yaml
# config/config.yaml (excerpt)
providers:
  openai_api:
    mode: "api"
    provider_type: "api"
    model: "gpt-5"          # Use GPT-5 by default
    available_models: ["gpt-5", "gpt-5-mini", "gpt-5-nano", "o3", "o4-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"]
```

### Dynamic Agent Assignment
```python
# scripts/agent_helpers.py extensions for multi-agent support

def assign_agent_by_expertise(task_type: str) -> str:
    """Dynamically assign tasks to appropriate agents based on expertise"""
    assignments = {
        "api": "codex --ask-for-approval never --sandbox danger-full-access",
        "database": "codex --ask-for-approval never --sandbox danger-full-access", 
        "ui": "codex --ask-for-approval never --sandbox danger-full-access",
        "infrastructure": "codex --ask-for-approval never --sandbox danger-full-access",
        "testing": "codex --ask-for-approval never --sandbox danger-full-access",
        "coordination": "claude --dangerously-skip-permissions"
    }
    return assignments.get(task_type, "claude --dangerously-skip-permissions")

def load_agent_role(role: str):
    """Load role-specific configuration and context"""
    import yaml
    with open(f'roles/{role}.yaml') as f:
        config = yaml.safe_load(f)
    
    # Set context and constraints for the agent
    set_agent_context(config['prompt'])
    set_branch_prefix(config['branch_prefix'])
    set_reviewers(config['reviewers'])
```

## Best Practices for Multi-Agent Coordination

### 1. Clear Task Boundaries
- Define specific, non-overlapping responsibilities
- Use explicit handoff points between agents
- Maintain clear communication protocols

### 2. Progress Transparency
```bash
# All agents should regularly update status
exec(open('scripts/agent_helpers.py').read())
update_progress("Implementing user authentication API", 65)
log_milestone("API endpoints completed, starting validation")
```

### 3. Quality Gates
```bash
# Each agent validates their work before handoff
run_local_tests()
check_code_quality() 
validate_requirements()
mark_ready_for_review()
```

### 4. Conflict Resolution
```python
def resolve_merge_conflicts():
    """Handle conflicts between parallel development streams"""
    conflicts = detect_conflicts()
    for conflict in conflicts:
        if conflict.type == "schema":
            coordinate_schema_merge()
        elif conflict.type == "api": 
            coordinate_api_merge()
        else:
            escalate_to_orchestrator()
```

## Integration with CLAUDE.md

This file extends the core development patterns in CLAUDE.md by providing:

1. **Multi-agent coordination patterns** that build on the basic CLI usage
2. **Specialized role configurations** that use the same underlying infrastructure  
3. **Parallel development workflows** that leverage the git worktree system
4. **Task distribution mechanisms** that integrate with the orchestration API

**Usage Pattern:**
1. Read CLAUDE.md for basic setup and single-agent workflows
2. Read AGENTS.md for multi-agent coordination and parallel development
3. Use both together for complex, multi-component feature development

**Command Integration:**
```bash
# Basic setup (from CLAUDE.md)
make install
cp .env.example .env
make dev

# Multi-agent coordination (from AGENTS.md)  
claude --dangerously-skip-permissions  # Primary orchestrator
codex --ask-for-approval never --sandbox danger-full-access exec "Backend tasks"  # Specialists

# Shared helpers (both files)
exec(open('scripts/agent_helpers.py').read())
```

This approach enables scaling from single-agent development to coordinated multi-agent teams while maintaining consistency and quality across all work streams.
