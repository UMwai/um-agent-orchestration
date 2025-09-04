# Simplified Multi-Agent Orchestration System Specifications

## Document Version
- **Version**: 3.0.0
- **Date**: 2025-09-04
- **Status**: IMPLEMENTED & ENHANCED
- **Author**: Specifications Engineer Agent
- **Reviewers**: Backend Engineer, Frontend Engineer, User

## Recent Enhancements (v3.0.0)
- ✅ **Interactive Planning**: Collaborative task planning with Claude
- ✅ **Specialized Agent Types**: 10+ domain-specific agents
- ✅ **Enhanced Launch System**: One-command setup with guided experience
- ✅ **Session Persistence**: Save/resume planning sessions
- ✅ **API Mode Support**: Direct Anthropic API integration

## Executive Summary

This specification defines a simplified multi-agent orchestration system that enables efficient task distribution across multiple CLI-based AI agents (claude, codex, gemini, cursor). The system prioritizes simplicity, maintainability, and effectiveness over complex features.

### Core Principles
1. **Simplicity First**: Minimize architectural complexity
2. **CLI-Native**: Direct CLI process management without unnecessary abstractions
3. **Stateless Design**: Reduce state management complexity
4. **Fail-Fast**: Clear error handling without complex recovery mechanisms
5. **Observable**: Simple, transparent operations with clear logging

## 1. System Requirements and Objectives

### 1.1 Business Requirements

**BR-1**: Enable parallel task execution across multiple AI agents
- **Rationale**: Leverage multiple agents for faster development
- **Priority**: CRITICAL
- **Success Metric**: 3+ agents working simultaneously

**BR-2**: Maintain simplicity for easy maintenance
- **Rationale**: Current system is overcomplicated per engineer feedback
- **Priority**: CRITICAL
- **Success Metric**: Core system < 1000 lines of code

**BR-3**: Support local development workflow
- **Rationale**: Primary use case is local development
- **Priority**: HIGH
- **Success Metric**: Single command startup

### 1.2 Functional Objectives

**FO-1**: Task submission and distribution
- Submit tasks via CLI or simple API
- Distribute tasks to available agents
- Track task status and completion

**FO-2**: Agent process management
- Spawn CLI processes (claude, codex)
- Monitor process health
- Clean termination on completion

**FO-3**: Basic coordination
- Prevent task duplication
- Share context between agents
- Simple dependency handling

### 1.3 Non-Functional Requirements

**NFR-1**: Performance
- Task assignment latency < 1 second
- Agent spawn time < 3 seconds
- Memory usage < 500MB per agent

**NFR-2**: Reliability
- Graceful handling of agent failures
- No data loss on system restart
- 99% uptime for local development

**NFR-3**: Usability
- Single configuration file
- Clear console output
- Minimal setup steps

## 2. Architecture Overview (Simplified Design)

### 2.1 System Components

```
┌─────────────────────────────────────────────────────┐
│                   HEAD NODE                         │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Task Queue  │  │   Task    │  │   Context    │  │
│  │  (SQLite)   │◄─┤Distributor│─►│   Manager    │  │
│  └─────────────┘  └──────────┘  └──────────────┘  │
│         ▲              │                 │          │
│         │              ▼                 ▼          │
│  ┌─────────────┐  ┌──────────────────────────┐    │
│  │   Simple    │  │   Agent Process Pool      │    │
│  │   CLI/API   │  │  ┌──────┐  ┌──────┐     │    │
│  └─────────────┘  │  │Agent1│  │Agent2│ ... │    │
│                   │  └──────┘  └──────┘     │    │
│                   └──────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────┐
│                 DOWNSTREAM NODES                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  Claude    │  │   Codex    │  │   Gemini   │   │
│  │  Instance  │  │  Instance  │  │  Instance  │   │
│  └────────────┘  └────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 2.2 Simplified Technology Stack

- **Language**: Python 3.11+
- **Task Storage**: SQLite (no Redis required)
- **Process Management**: subprocess + asyncio
- **API**: FastAPI (optional, CLI-first)
- **Configuration**: Single YAML file
- **Logging**: Python logging to console/file

### 2.3 Key Design Decisions

1. **SQLite over Redis**: Simpler deployment, no external dependencies
2. **Direct subprocess**: No complex process pooling or PTY management
3. **File-based context**: Share context via filesystem, not complex IPC
4. **Stateless agents**: Agents don't maintain session state
5. **Simple task format**: Plain text descriptions, not complex schemas

## 3. Core Components and Responsibilities

### 3.1 Task Queue Manager

**Purpose**: Simple persistent task queue using SQLite

**Responsibilities**:
- Store tasks with status (pending, assigned, completed, failed)
- Atomic task assignment to prevent duplication
- Basic priority ordering (FIFO with priority levels)

**Interface**:
```python
class TaskQueue:
    def add_task(self, description: str, priority: int = 0) -> str
    def get_next_task(self, agent_id: str) -> Optional[Task]
    def complete_task(self, task_id: str, result: str) -> None
    def fail_task(self, task_id: str, error: str) -> None
    def list_tasks(self, status: Optional[str] = None) -> List[Task]
```

### 3.2 Task Distributor

**Purpose**: Assign tasks to available agents

**Responsibilities**:
- Monitor agent availability
- Assign tasks based on simple rules
- Track task assignments
- Handle timeouts and reassignment

**Interface**:
```python
class TaskDistributor:
    def assign_task(self, task: Task) -> Optional[str]  # Returns agent_id
    def register_agent(self, agent_id: str, type: str) -> None
    def unregister_agent(self, agent_id: str) -> None
    def get_agent_status(self) -> Dict[str, AgentStatus]
```

### 3.3 Agent Process Manager

**Purpose**: Spawn and manage CLI agent processes

**Responsibilities**:
- Spawn CLI processes with appropriate arguments
- Send prompts and capture output
- Monitor process health
- Clean termination

**Interface**:
```python
class AgentProcess:
    def __init__(self, agent_type: str, agent_id: str)
    async def execute_task(self, task: Task) -> str
    def is_alive(self) -> bool
    def terminate(self) -> None
```

### 3.4 Context Manager

**Purpose**: Share context between agents via filesystem

**Responsibilities**:
- Maintain shared context directory
- Update context files after task completion
- Provide context to agents via file references

**Structure**:
```
context/
├── project_overview.md
├── completed_tasks.json
├── current_state.md
└── agent_outputs/
    ├── task_001_output.md
    └── task_002_output.md
```

## 4. Inter-Node Communication Protocol

### 4.1 Communication Model

**Approach**: File-based communication with polling

**Rationale**: Simpler than WebSockets or message queues

### 4.2 Task Assignment Protocol

```yaml
# tasks/pending/task_001.yaml
id: task_001
description: "Implement user authentication"
priority: 1
created_at: "2025-01-15T10:00:00Z"
dependencies: []
context_files:
  - "context/project_overview.md"
  - "context/current_state.md"
```

```yaml
# tasks/assigned/task_001_agent_01.yaml  
task_id: task_001
agent_id: agent_01
agent_type: claude
assigned_at: "2025-01-15T10:01:00Z"
```

### 4.3 Result Protocol

```yaml
# tasks/completed/task_001_result.yaml
task_id: task_001
agent_id: agent_01
completed_at: "2025-01-15T10:15:00Z"
status: success
output_file: "context/agent_outputs/task_001_output.md"
files_modified:
  - "src/auth.py"
  - "tests/test_auth.py"
```

## 5. Task Distribution Algorithm

### 5.1 Simple Round-Robin with Type Affinity

```python
def distribute_task(task: Task, agents: List[Agent]) -> Optional[Agent]:
    # 1. Check for agent type preference
    if task.preferred_agent_type:
        suitable_agents = [a for a in agents if a.type == task.preferred_agent_type]
        if suitable_agents:
            return min(suitable_agents, key=lambda a: a.task_count)
    
    # 2. Find least loaded available agent
    available_agents = [a for a in agents if a.is_available()]
    if not available_agents:
        return None
        
    return min(available_agents, key=lambda a: a.task_count)
```

### 5.2 Task Prioritization

- **Priority Levels**: HIGH (0), NORMAL (1), LOW (2)
- **FIFO within priority**: Tasks processed in order within same priority
- **Starvation prevention**: Promote LOW priority after 30 minutes

## 6. Context Sharing Mechanism

### 6.1 Context Structure

```python
@dataclass
class SharedContext:
    project_overview: str
    current_objectives: List[str]
    completed_tasks: List[TaskSummary]
    code_structure: Dict[str, str]  # module -> description
    known_issues: List[str]
    agent_notes: Dict[str, str]  # agent_id -> notes
```

### 6.2 Context Update Protocol

1. **Pre-task**: Agent reads current context files
2. **Post-task**: Agent writes output to designated file
3. **Context merge**: System updates shared context
4. **Broadcast**: Updated context available to all agents

### 6.3 Context Files

```markdown
# context/project_overview.md
## Project: User Management System
Current Phase: Authentication Implementation
Tech Stack: FastAPI, SQLAlchemy, PostgreSQL

# context/current_state.md
## Completed Tasks
- [x] Database schema design
- [x] User model implementation
- [ ] Authentication endpoints
- [ ] Authorization middleware

# context/agent_outputs/task_001_output.md
## Task: Implement user authentication
### Changes Made:
- Created auth.py with JWT implementation
- Added login/logout endpoints
- Created test suite for authentication
```

## 7. Error Handling and Recovery

### 7.1 Error Categories

**Level 1 - Recoverable**:
- Agent timeout: Reassign task to another agent
- Parse error: Retry with clarified prompt
- Resource busy: Queue for retry

**Level 2 - Escalation Required**:
- Multiple failures: Mark task for human review
- Agent crash: Restart agent, reassign tasks
- Conflicting outputs: Flag for resolution

**Level 3 - System Failure**:
- All agents down: Alert and halt
- Database corruption: Restore from backup
- Out of resources: Graceful shutdown

### 7.2 Recovery Strategies

```python
class ErrorHandler:
    def handle_agent_failure(self, agent_id: str, task_id: str):
        # 1. Mark agent as failed
        # 2. Return task to queue with retry count
        # 3. If retry_count > 3, escalate to human
        
    def handle_task_timeout(self, task_id: str):
        # 1. Send interrupt to agent
        # 2. Wait for graceful completion (30s)
        # 3. Force terminate if needed
        # 4. Reassign task
        
    def handle_system_error(self, error: Exception):
        # 1. Log error with full context
        # 2. Save current state
        # 3. Attempt recovery or shutdown
```

## 8. Minimum Viable Product (MVP) Features

### 8.1 Core MVP Features (Phase 1)

✅ **Required for MVP**:

1. **Task Submission**
   - CLI command: `orchestrate add "task description"`
   - Basic task queue in SQLite
   - Manual task addition

2. **Agent Spawning**
   - Support for claude and codex CLI
   - Single agent type at a time
   - Basic subprocess management

3. **Task Distribution**
   - Simple FIFO queue processing
   - One task per agent
   - No dependency handling

4. **Status Monitoring**
   - CLI command: `orchestrate status`
   - Show active tasks and agents
   - Basic console output

5. **Context Sharing**
   - Shared context directory
   - Manual context updates
   - Read-only for agents

### 8.2 MVP Command Interface

```bash
# Start orchestrator
orchestrate start

# Add tasks
orchestrate add "Implement user authentication"
orchestrate add "Write unit tests for auth" --priority high

# Check status
orchestrate status
orchestrate tasks
orchestrate agents

# Stop system
orchestrate stop
```

### 8.3 MVP Configuration

```yaml
# config.yaml
agents:
  claude:
    command: "claude --dangerously-skip-permissions"
    max_instances: 2
  codex:
    command: "codex --ask-for-approval never --sandbox danger-full-access exec"
    max_instances: 3

task_queue:
  database: "tasks.db"
  timeout_minutes: 30
  max_retries: 3

context:
  directory: "./context"
  update_on_completion: true
```

## 9. Future Enhancements (Nice-to-Have)

### 9.1 Phase 2 Enhancements

1. **Web Dashboard**
   - Simple HTML interface
   - Real-time task status
   - Agent monitoring
   - *Complexity: Medium*

2. **Task Dependencies**
   - DAG-based task ordering
   - Prerequisite checking
   - Parallel execution where possible
   - *Complexity: Medium*

3. **Agent Specialization**
   - Agent capability profiles
   - Task-to-agent matching
   - Learning from success patterns
   - *Complexity: High*

### 9.2 Phase 3 Enhancements

4. **Persistent Sessions**
   - Reuse agent sessions
   - Context preservation
   - Reduced startup time
   - *Complexity: High*

5. **Advanced Coordination**
   - Multi-agent collaboration
   - Conflict resolution
   - Consensus mechanisms
   - *Complexity: Very High*

6. **Remote Agents**
   - Network-based agents
   - Distributed execution
   - Cloud agent support
   - *Complexity: Very High*

### 9.3 Phase 4 (Long-term)

7. **AI-Driven Orchestration**
   - Automatic task decomposition
   - Intelligent agent selection
   - Performance optimization
   - *Complexity: Very High*

8. **Enterprise Features**
   - Multi-project support
   - User authentication
   - Audit logging
   - *Complexity: High*

## 10. Success Criteria and Acceptance Tests

### 10.1 Functional Success Criteria

**SC-1**: Task Processing
- ✓ Can submit 10 tasks via CLI
- ✓ All tasks assigned within 10 seconds
- ✓ 90% task completion rate
- ✓ Results saved to context directory

**SC-2**: Agent Management
- ✓ Spawn 3 agents simultaneously
- ✓ Agents terminate cleanly
- ✓ No zombie processes
- ✓ Resource usage within limits

**SC-3**: System Reliability
- ✓ Runs for 2 hours without crash
- ✓ Handles agent failures gracefully
- ✓ Recovers from restart
- ✓ No data loss

### 10.2 Acceptance Test Scenarios

#### Test 1: Basic Task Flow
```bash
# Setup
orchestrate start

# Test
orchestrate add "Create README.md with project description"
orchestrate status  # Should show task pending
# Wait for completion
orchestrate status  # Should show task completed

# Verify
cat context/agent_outputs/task_001_output.md  # Should contain result
ls README.md  # File should exist

# Cleanup
orchestrate stop
```

#### Test 2: Multi-Agent Parallel Execution
```bash
# Setup
orchestrate start --agents claude:2,codex:2

# Test - Add multiple tasks
orchestrate add "Task 1: Create auth module"
orchestrate add "Task 2: Create user module"  
orchestrate add "Task 3: Create database module"
orchestrate add "Task 4: Create API module"

# Monitor - Should show multiple agents working
orchestrate agents  # Should show 4 agents active

# Verify parallel execution
orchestrate tasks --status active  # Should show multiple active

# Cleanup
orchestrate stop
```

#### Test 3: Error Recovery
```bash
# Setup
orchestrate start

# Test - Add task that will fail
orchestrate add "Invalid task: @#$%^&*()"

# Monitor failure handling
orchestrate status  # Should show task failed
orchestrate tasks --status failed  # Should list failed task

# Test recovery
orchestrate retry task_001  # Retry failed task
orchestrate status  # Should show retry attempt

# Cleanup
orchestrate stop
```

#### Test 4: Context Sharing
```bash
# Setup
echo "Project: Test System" > context/project_overview.md
orchestrate start

# Test - Tasks that build on each other
orchestrate add "Read project overview and create implementation plan"
# Wait for completion
orchestrate add "Based on plan in context, implement first module"

# Verify context usage
grep "Test System" context/agent_outputs/task_001_output.md
grep "plan" context/agent_outputs/task_002_output.md

# Cleanup
orchestrate stop
```

### 10.3 Performance Criteria

**PC-1**: Latency Requirements
- Task submission: < 100ms
- Task assignment: < 1000ms  
- Agent spawn: < 3000ms
- Status query: < 50ms

**PC-2**: Resource Requirements
- Memory per agent: < 500MB
- CPU per agent: < 25%
- Disk I/O: < 10MB/s
- Network (future): < 1MB/s

**PC-3**: Scale Requirements (MVP)
- Concurrent agents: 5
- Queue size: 1000 tasks
- Context size: 100MB
- Runtime: 24 hours

## 11. Implementation Roadmap

### 11.1 Week 1: Core Infrastructure
- [ ] Set up project structure
- [ ] Implement TaskQueue with SQLite
- [ ] Create basic CLI interface
- [ ] Add configuration loader

### 11.2 Week 2: Agent Management
- [ ] Implement AgentProcess class
- [ ] Add subprocess spawning
- [ ] Create process monitoring
- [ ] Handle process termination

### 11.3 Week 3: Task Distribution
- [ ] Implement TaskDistributor
- [ ] Add assignment algorithm
- [ ] Create status tracking
- [ ] Handle failures and retries

### 11.4 Week 4: Context System
- [ ] Design context structure
- [ ] Implement ContextManager
- [ ] Add file-based sharing
- [ ] Create update mechanism

### 11.5 Week 5: Testing & Polish
- [ ] Write acceptance tests
- [ ] Add error handling
- [ ] Create documentation
- [ ] Performance optimization

## 12. Risk Mitigation

### 12.1 Technical Risks

**Risk**: CLI tools may change interface
- **Mitigation**: Abstract CLI interaction, version detection

**Risk**: Agent processes may hang
- **Mitigation**: Implement timeouts, health checks

**Risk**: Context conflicts between agents  
- **Mitigation**: Lock files, atomic updates

### 12.2 Operational Risks

**Risk**: System resource exhaustion
- **Mitigation**: Resource limits, monitoring

**Risk**: Data loss on crash
- **Mitigation**: SQLite WAL mode, periodic backups

## Appendix A: Example Task Specifications

### A.1 Simple Task
```yaml
id: TASK-001
description: "Create a README file"
priority: normal
context_required: false
preferred_agent: claude
timeout_minutes: 10
```

### A.2 Complex Task
```yaml
id: TASK-002  
description: "Implement complete authentication system"
priority: high
context_required: true
context_files:
  - "requirements.md"
  - "database_schema.sql"
preferred_agent: codex
timeout_minutes: 60
subtasks:
  - "Design auth schema"
  - "Implement JWT tokens"
  - "Create login endpoints"
  - "Add test coverage"
```

## Appendix B: Configuration Schema

```yaml
# Complete configuration example
orchestrator:
  mode: local  # local or distributed
  database: ./tasks.db
  context_dir: ./context
  log_level: INFO
  
agents:
  claude:
    command: "claude --dangerously-skip-permissions"
    max_instances: 3
    timeout_seconds: 300
    retry_on_failure: true
    
  codex:
    command: "codex --ask-for-approval never --sandbox danger-full-access exec"
    max_instances: 5
    timeout_seconds: 600
    retry_on_failure: true
    
task_queue:
  max_size: 1000
  default_priority: normal
  default_timeout_minutes: 30
  max_retries: 3
  retry_delay_seconds: 60
  
monitoring:
  enable_metrics: true
  metrics_port: 9090
  health_check_interval: 30
  
performance:
  max_memory_mb: 4096
  max_cpu_percent: 80
  max_disk_io_mbps: 10
```

## Document Control

### Revision History
- v1.0.0 (2025-01-15): Initial specification based on user requirements and engineer feedback

### Approvals Required
- [ ] User/Product Owner
- [ ] Backend Engineer
- [ ] Frontend Engineer
- [ ] System Architect

### Related Documents
- Original ARCHITECTURE_ANALYSIS.md
- CLI_INTEGRATION_SPECIFICATION.md
- AGENTS.md
- README.md

---

*End of Specification Document*