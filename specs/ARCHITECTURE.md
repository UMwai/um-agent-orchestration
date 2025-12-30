# um-agent-orchestration Architecture

## System Overview

um-agent-orchestration is a lightweight system for managing multiple specialized AI agents working in parallel. The architecture prioritizes simplicity while enabling powerful autonomous development workflows.

---

## High-Level Architecture

```
                        +--------------------+
                        |      User CLI      |
                        |  (orchestrate cmd) |
                        +---------+----------+
                                  |
                                  v
+-------------------------------------------------------------------------+
|                          HEAD NODE                                       |
|  +------------------+   +------------------+   +--------------------+    |
|  |  Interactive     |   |  Task            |   |  Context           |    |
|  |  Planner         |   |  Decomposer      |   |  Manager           |    |
|  +--------+---------+   +--------+---------+   +---------+----------+    |
|           |                      |                       |               |
|           v                      v                       v               |
|  +------------------+   +------------------+   +--------------------+    |
|  |  Task Queue      |   |  Task            |   |  File-based IPC    |    |
|  |  (SQLite)        |   |  Distributor     |   |  (/tmp/agent_*)    |    |
|  +--------+---------+   +--------+---------+   +--------------------+    |
|           |                      |                                       |
|           +----------+-----------+                                       |
|                      |                                                   |
|                      v                                                   |
|           +--------------------+                                         |
|           |  Agent Spawner     |                                         |
|           +--------------------+                                         |
+-------------------------------------------------------------------------+
                                  |
                 +----------------+----------------+
                 |                |                |
                 v                v                v
        +--------+-------+ +-----+-------+ +------+------+
        | Claude Agent   | | Codex Agent | | Gemini Agent|
        | (Specialist)   | | (Specialist)| | (Specialist)|
        +----------------+ +-------------+ +-------------+
```

---

## Core Components

### 1. CLI Interface (`src/cli/orchestrate.py`)

**Responsibility**: Command-line interface for all orchestration operations.

**Commands**:

| Command | Description |
|---------|-------------|
| `plan <goal>` | Start interactive planning session |
| `plan-list` | List all planning sessions |
| `plan-continue <id>` | Resume planning session |
| `execute-plan <id>` | Execute approved plan |
| `submit <task>` | Submit task to queue |
| `run` | Start processing tasks |
| `status` | View queue and agents |
| `task <id>` | View specific task |
| `agents` | List active agents |
| `kill <id>` | Kill stuck agent |
| `cleanup` | Clean old data |
| `demo` | Run demo tasks |

**Implementation**:
```python
@click.group()
def cli():
    """Agent Orchestrator - 23x/7 Autonomous Development"""
    pass

@cli.command()
@click.argument('goal')
def plan(goal: str):
    """Start interactive planning session"""
    planner = InteractivePlanner()
    planner.start_session(goal)
```

### 2. Task Queue (`src/core/task_queue.py`)

**Responsibility**: Persistent task storage and management.

**Database Schema**:
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    agent_type TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 2,
    context TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    assigned_to TEXT,
    output TEXT,
    error TEXT
);
```

**Status Flow**:
```
pending --> assigned --> in_progress --> completed
                    \               \--> failed
                     \--> timeout --> pending (retry)
```

**Interface**:
```python
class TaskQueue:
    def __init__(self, db_path: str = "tasks.db"):
        self.conn = sqlite3.connect(db_path)

    def add_task(self, description: str, agent_type: str = None,
                 priority: int = 2, context: dict = None) -> str:
        """Add task to queue, return task ID"""

    def get_next_task(self, agent_id: str) -> Optional[Task]:
        """Get highest priority unassigned task"""

    def complete_task(self, task_id: str, output: str) -> None:
        """Mark task as completed with output"""

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed with error"""

    def list_tasks(self, status: str = None) -> List[Task]:
        """List tasks, optionally filtered by status"""
```

### 3. Agent Spawner (`src/core/agent_spawner.py`)

**Responsibility**: Spawn and manage CLI agent processes.

**Supported CLIs**:

| CLI | Command | Mode |
|-----|---------|------|
| Claude | `claude --dangerously-skip-permissions` | Full access |
| Codex | `codex --ask-for-approval never --sandbox danger-full-access exec` | Full access |
| Gemini | `gemini -m gemini-3-pro -y` | Yolo mode |

**Implementation**:
```python
class AgentSpawner:
    def __init__(self, use_api_mode: bool = True):
        self.use_api_mode = use_api_mode
        self.active_agents = {}

    def spawn_agent(self, agent_type: str, task: Task) -> str:
        """Spawn agent for task, return agent ID"""
        if self.use_api_mode:
            return self._spawn_api_agent(agent_type, task)
        else:
            return self._spawn_cli_agent(agent_type, task)

    def _spawn_cli_agent(self, agent_type: str, task: Task) -> str:
        """Spawn subprocess for CLI agent"""
        cmd = self.get_command(agent_type, task)
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        return self._register_agent(process, agent_type)

    def _spawn_api_agent(self, agent_type: str, task: Task) -> str:
        """Use Anthropic API directly"""
        # Direct API call with specialized system prompt
        pass
```

### 4. Task Decomposer (`src/core/task_decomposer.py`)

**Responsibility**: Break high-level tasks into specialized subtasks.

**Decomposition Strategy**:
```
High-Level Goal
    |
    v
+-------------------+
| Task Decomposer   |
|                   |
| 1. Analyze goal   |
| 2. Identify scope |
| 3. Create phases  |
| 4. Assign agents  |
+-------------------+
    |
    v
+-------------------------------------------+
| Phase 1: Design                           |
|   - [specifications-engineer] Requirements|
|   - [data-architect] Schema design        |
+-------------------------------------------+
| Phase 2: Implementation (parallel)        |
|   - [backend-systems-engineer] API        |
|   - [frontend-ui-engineer] UI             |
+-------------------------------------------+
| Phase 3: Testing                          |
|   - [backend-systems-engineer] Tests      |
+-------------------------------------------+
```

**Agent Type Mapping**:

| Keywords | Assigned Agent |
|----------|---------------|
| API, backend, database | backend-systems-engineer |
| UI, frontend, React | frontend-ui-engineer |
| ETL, pipeline, data | data-pipeline-engineer |
| AWS, cloud, deploy | aws-cloud-architect |
| ML, model, training | ml-systems-architect |
| analysis, report | data-science-analyst |
| schema, governance | data-architect-governance |
| requirements, spec | specifications-engineer |
| LLM, RAG, prompt | llm-architect |

### 5. Interactive Planner (`src/core/interactive_planner.py`)

**Responsibility**: Collaborative planning sessions with Claude.

**Session Flow**:
```
User: plan "Build REST API with auth"
    |
    v
+-------------------+
| Claude Analysis   |
| - Scope analysis  |
| - Initial tasks   |
| - Dependency map  |
+-------------------+
    |
    v
Interactive Loop:
    [d] Discuss - Ask Claude questions
    [a] Add - Add new task
    [m] Modify - Change existing task
    [s] Split - Break task into subtasks
    [r] Remove - Delete task
    [v] View - Show current plan
    [p] Proceed - Move to approval
    |
    v
+-------------------+
| Approval Phase    |
| - Review tasks    |
| - Confirm deps    |
| - Start execution |
+-------------------+
```

**Session Persistence**:
```python
@dataclass
class PlanningSession:
    id: str
    goal: str
    tasks: List[PlannedTask]
    dependencies: Dict[str, List[str]]
    discussion_history: List[Message]
    status: SessionStatus  # draft, approved, executing, completed
    created_at: datetime
    updated_at: datetime
```

### 6. Context Manager (`src/core/context_manager.py`)

**Responsibility**: File-based context sharing between agents.

**Directory Structure**:
```
/tmp/agent_orchestrator/
├── project_context.json       # Shared project info
├── completed_tasks.json       # Results from completed tasks
├── active_agents.json         # Currently running agents
├── agent_outputs/
│   ├── agent_001_output.md   # Output from agent 001
│   ├── agent_002_output.md   # Output from agent 002
│   └── ...
└── shared_artifacts/
    ├── requirements.md       # Shared requirements
    ├── schema.sql            # Database schema
    └── api_spec.yaml         # API specification
```

**Implementation**:
```python
class ContextManager:
    def __init__(self, base_dir: str = "/tmp/agent_orchestrator"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_context_for_agent(self, agent_id: str, task: Task) -> Dict:
        """Build context for agent execution"""
        return {
            "project": self._load_project_context(),
            "completed_tasks": self._get_relevant_completed(task),
            "shared_artifacts": self._list_artifacts(),
            "agent_outputs": self._get_relevant_outputs(task)
        }

    def save_agent_output(self, agent_id: str, output: str) -> None:
        """Save agent output for other agents"""
        output_file = self.base_dir / "agent_outputs" / f"{agent_id}_output.md"
        output_file.write_text(output)

    def update_project_context(self, updates: Dict) -> None:
        """Update shared project context"""
        context = self._load_project_context()
        context.update(updates)
        self._save_project_context(context)
```

---

## Data Flow

### Task Execution Flow

```
1. User Input
   orchestrate plan "Build user authentication"
        |
        v
2. Interactive Planning
   [InteractivePlanner.start_session()]
   - Claude collaboration
   - Task refinement
   - Dependency mapping
        |
        v
3. Plan Approval
   [User reviews and approves]
        |
        v
4. Task Queue Population
   [TaskQueue.add_task() for each task]
        |
        v
5. Task Distribution
   [TaskDistributor.assign_tasks()]
        |
        v
6. Agent Spawning
   [AgentSpawner.spawn_agent() per task]
        |
        +---> Agent 1: backend-systems-engineer
        +---> Agent 2: frontend-ui-engineer
        +---> Agent 3: specifications-engineer
        |
        v
7. Execution & Monitoring
   [Monitor status, collect outputs]
        |
        v
8. Result Aggregation
   [ContextManager.save_outputs()]
        |
        v
9. Completion
   orchestrate status -> All tasks completed
```

### Context Sharing Flow

```
Agent 1 (Backend)                   Agent 2 (Frontend)
     |                                    |
     |-- Complete task ----------------->|
     |                                    |
     v                                    |
Save output to:                           |
/tmp/agent_orchestrator/                  |
  agent_outputs/agent_001.md              |
                                          |
     |<-- Read context -------------------|
     |                                    v
     |                              Read:
     |                              - project_context.json
     |                              - agent_001_output.md
     |                                    |
     |                                    v
     |                              Use backend API spec
     |                              in frontend implementation
```

---

## Configuration

### Environment Variables

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-...     # Required for API mode
USE_API_MODE=true                 # true for API, false for CLI
MAX_AGENTS=3                      # Concurrent agents
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator
```

### No Complex Configuration Files

The system intentionally avoids complex configuration to maintain simplicity. Configuration is done through:
1. Environment variables
2. CLI arguments
3. Interactive prompts

---

## Security Considerations

### Process Isolation

```
Main Process (orchestrate)
    |
    +-- subprocess.Popen --> Agent 1 (isolated)
    |
    +-- subprocess.Popen --> Agent 2 (isolated)
    |
    +-- subprocess.Popen --> Agent 3 (isolated)
```

Each agent runs in its own subprocess with:
- Separate memory space
- Own stdout/stderr
- Timeout enforcement
- Clean termination on completion

### API Key Security

- Keys stored only in environment variables
- Never logged or persisted
- Passed via environment to subprocesses

### File System Access

- Agents run in current working directory
- Full access via `--dangerously-skip-permissions` (Claude)
- Full access via `--sandbox danger-full-access` (Codex)
- User must trust agent actions

---

## Extension Points

### Adding New Agent Types

```python
# src/core/agent_types.py
AGENT_TYPES = {
    "new-specialist": {
        "name": "New Specialist Agent",
        "description": "Handles X, Y, Z tasks",
        "keywords": ["x", "y", "z"],
        "system_prompt": "You are a specialist in..."
    }
}
```

### Custom CLI Integration

```python
# src/core/agent_spawner.py
CLI_COMMANDS = {
    "new-cli": {
        "binary": "new-cli-tool",
        "args": ["--flag1", "--flag2"],
        "timeout": 300
    }
}
```

---

## Performance Characteristics

### Resource Usage

| Component | Memory | CPU | Disk |
|-----------|--------|-----|------|
| Head Node | ~50MB | ~5% | SQLite DB |
| Per Agent | ~200MB | ~10% | Output files |
| Context | - | - | ~10MB |

### Scalability Limits

| Metric | Current | Target |
|--------|---------|--------|
| Concurrent Agents | 3-5 | 10-15 |
| Queue Size | 1000 | 10000 |
| Context Size | 100MB | 1GB |

### Bottlenecks

1. **Agent Spawn Time**: ~2-3 seconds per agent
2. **API Rate Limits**: ~50 req/min for Anthropic
3. **Disk I/O**: Context file reads/writes
4. **SQLite**: Single-writer limitation

---

## Comparison with Complex Alternatives

### Why Simple?

| Feature | This System | Complex Alternative |
|---------|-------------|---------------------|
| Database | SQLite | PostgreSQL + Redis |
| IPC | File-based | WebSockets + Message Queue |
| UI | CLI | React Dashboard |
| Deployment | Single process | Docker Compose + K8s |
| Setup | 1 command | Multiple services |
| Lines of Code | ~500 | ~5000+ |

### Trade-offs

**Gained**:
- Easy to understand
- Fast to deploy
- Simple to debug
- Minimal dependencies

**Lost**:
- Real-time dashboard
- Complex task dependencies
- Distributed execution
- Enterprise features

---

*Last Updated: December 2024*
