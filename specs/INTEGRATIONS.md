# um-agent-orchestration Integrations

## Overview

um-agent-orchestration integrates with multiple AI CLI tools and can operate in both API and CLI modes. The system is designed to be extensible while maintaining simplicity.

---

## CLI Tool Integrations

### 1. Claude CLI

**Purpose**: Primary agent for complex reasoning and code generation

**Binary**: `claude`

**Modes**:

| Mode | Command | Use Case |
|------|---------|----------|
| Interactive | `claude` | Manual interaction |
| Full Access | `claude --dangerously-skip-permissions` | Automated execution |
| Print Only | `claude --print -p "prompt"` | Single prompt response |
| JSON Output | `claude --output-format stream-json` | Programmatic parsing |

**Integration Configuration**:
```python
CLAUDE_CLI = {
    "binary": "claude",
    "interactive_args": ["--dangerously-skip-permissions"],
    "batch_args": ["--print", "--output-format", "stream-json", "-p"],
    "timeout": 300,
    "max_retries": 3
}
```

**Spawning Example**:
```python
def spawn_claude_agent(task: Task) -> subprocess.Popen:
    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        "--output-format", "stream-json",
        "-p", task.prompt
    ]

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd()
    )
```

### 2. Codex CLI

**Purpose**: Code generation and implementation tasks

**Binary**: `codex`

**Modes**:

| Mode | Command | Use Case |
|------|---------|----------|
| Safe | `codex exec "prompt"` | Sandboxed execution |
| Full Access | `codex --sandbox danger-full-access exec "prompt"` | Full filesystem access |
| No Approval | `codex --ask-for-approval never exec "prompt"` | Automated execution |

**Integration Configuration**:
```python
CODEX_CLI = {
    "binary": "codex",
    "args": [
        "--ask-for-approval", "never",
        "--sandbox", "danger-full-access",
        "exec"
    ],
    "timeout": 600,
    "max_retries": 3
}
```

**Spawning Example**:
```python
def spawn_codex_agent(task: Task) -> subprocess.Popen:
    cmd = [
        "codex",
        "--ask-for-approval", "never",
        "--sandbox", "danger-full-access",
        "exec",
        task.prompt
    ]

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd()
    )
```

### 3. Gemini CLI

**Purpose**: Research, exploration, large context analysis

**Binary**: `gemini`

**Modes**:

| Mode | Command | Use Case |
|------|---------|----------|
| Interactive | `gemini` | Manual interaction |
| Yolo | `gemini -y "prompt"` | Auto-approve |
| Model Select | `gemini -m gemini-3-pro "prompt"` | Specific model |
| JSON Output | `gemini -o stream-json "prompt"` | Programmatic parsing |

**Integration Configuration**:
```python
GEMINI_CLI = {
    "binary": "gemini",
    "args": ["-m", "gemini-3-pro", "-y", "-o", "stream-json"],
    "timeout": 300,
    "max_retries": 3
}
```

---

## API Mode Integration

### Anthropic API

**Purpose**: Direct Claude API access (recommended for reliability)

**Configuration**:
```python
# .env
ANTHROPIC_API_KEY=sk-ant-...
USE_API_MODE=true
```

**Implementation**:
```python
import anthropic

class AnthropicAPIAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def execute_task(self, task: Task, system_prompt: str) -> str:
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": task.prompt}]
        )
        return message.content[0].text
```

**Agent Type Mapping**:
```python
AGENT_SYSTEM_PROMPTS = {
    "backend-systems-engineer": """
        You are a senior backend systems engineer...
    """,
    "frontend-ui-engineer": """
        You are a senior frontend UI engineer...
    """,
    # ... other agent types
}
```

---

## File-Based IPC Integration

### Context Directory Structure

```
/tmp/agent_orchestrator/
├── project_context.json      # Shared project metadata
├── completed_tasks.json      # Completed task summaries
├── active_agents.json        # Currently running agents
├── agent_outputs/            # Individual agent outputs
│   ├── agent_001.md
│   ├── agent_002.md
│   └── ...
├── shared_artifacts/         # Shared files between agents
│   ├── schema.sql
│   ├── api_spec.yaml
│   └── requirements.md
└── locks/                    # File locks for coordination
    └── context.lock
```

### Context Manager Interface

```python
class ContextManager:
    def __init__(self, base_dir: str = "/tmp/agent_orchestrator"):
        self.base_dir = Path(base_dir)

    def get_project_context(self) -> Dict:
        """Load shared project context"""
        path = self.base_dir / "project_context.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def save_agent_output(self, agent_id: str, output: str):
        """Save agent output for sharing"""
        path = self.base_dir / "agent_outputs" / f"{agent_id}.md"
        path.write_text(output)

    def get_completed_tasks(self) -> List[Dict]:
        """Get list of completed tasks"""
        path = self.base_dir / "completed_tasks.json"
        return json.loads(path.read_text()) if path.exists() else []

    def add_shared_artifact(self, name: str, content: str):
        """Add shared artifact"""
        path = self.base_dir / "shared_artifacts" / name
        path.write_text(content)
```

---

## SQLite Integration

### Database Schema

```sql
-- Task Queue Table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    agent_type TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 2,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    assigned_to TEXT,
    output TEXT,
    error TEXT
);

-- Planning Sessions Table
CREATE TABLE planning_sessions (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    tasks TEXT,  -- JSON array
    dependencies TEXT,  -- JSON object
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Agent History Table
CREATE TABLE agent_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    task_id TEXT,
    action TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT
);
```

### Database Operations

```python
class TaskQueue:
    def __init__(self, db_path: str = "tasks.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def add_task(self, description: str, **kwargs) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            """INSERT INTO tasks (id, description, agent_type, priority, context)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, description, kwargs.get('agent_type'),
             kwargs.get('priority', 2), json.dumps(kwargs.get('context', {})))
        )
        self.conn.commit()
        return task_id

    def get_next_task(self, agent_id: str) -> Optional[Dict]:
        cursor = self.conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'pending'
               ORDER BY priority ASC, created_at ASC
               LIMIT 1"""
        )
        row = cursor.fetchone()
        if row:
            self.conn.execute(
                """UPDATE tasks SET status = 'assigned',
                   assigned_at = CURRENT_TIMESTAMP, assigned_to = ?
                   WHERE id = ?""",
                (agent_id, row['id'])
            )
            self.conn.commit()
            return dict(row)
        return None
```

---

## Environment Configuration

### Required Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...     # Required for API mode
USE_API_MODE=true                 # true = API, false = CLI
MAX_AGENTS=3                      # Max concurrent agents
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator
```

### Optional Variables

```bash
# Optional CLI paths
CLAUDE_CLI_PATH=/usr/local/bin/claude
CODEX_CLI_PATH=/usr/local/bin/codex
GEMINI_CLI_PATH=/usr/local/bin/gemini

# Timeouts
TASK_TIMEOUT=300                  # Default task timeout (seconds)
AGENT_SPAWN_TIMEOUT=10            # Agent spawn timeout

# Logging
LOG_LEVEL=INFO
LOG_FILE=orchestrator.log
```

---

## Integration Testing

### CLI Availability Check

```python
def check_cli_availability() -> Dict[str, bool]:
    """Check which CLI tools are available"""
    results = {}

    for cli in ["claude", "codex", "gemini"]:
        try:
            result = subprocess.run(
                [cli, "--version"],
                capture_output=True,
                timeout=5
            )
            results[cli] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results[cli] = False

    return results
```

### Integration Health Check

```python
def health_check() -> Dict[str, Any]:
    """Full system health check"""
    return {
        "database": check_database_connection(),
        "context_dir": check_context_directory(),
        "cli_tools": check_cli_availability(),
        "api_mode": check_api_credentials(),
        "active_agents": count_active_agents()
    }
```

---

## Future Integrations (Planned)

### GitHub Integration

```yaml
# Planned
integrations:
  github:
    enabled: true
    token: ${GITHUB_TOKEN}
    features:
      - issue_creation
      - pr_creation
      - branch_management
```

### Slack Notifications

```yaml
# Planned
integrations:
  slack:
    enabled: true
    webhook: ${SLACK_WEBHOOK}
    channels:
      status: "#dev-updates"
      errors: "#dev-alerts"
```

### Monitoring (Prometheus)

```yaml
# Planned
integrations:
  prometheus:
    enabled: true
    port: 9090
    metrics:
      - tasks_completed_total
      - tasks_failed_total
      - agent_active_count
      - task_duration_seconds
```

---

## Integration Best Practices

### Error Handling

```python
class IntegrationError(Exception):
    """Base exception for integrations"""
    pass

class CLINotFoundError(IntegrationError):
    """CLI tool not found"""
    pass

class APIAuthError(IntegrationError):
    """API authentication failed"""
    pass

def handle_integration_error(error: IntegrationError):
    if isinstance(error, CLINotFoundError):
        # Fall back to API mode
        return use_api_fallback()
    elif isinstance(error, APIAuthError):
        # Prompt for credentials
        return prompt_for_credentials()
    else:
        raise error
```

### Rate Limiting

```python
from functools import wraps
import time

def rate_limit(calls_per_minute: int):
    """Rate limit decorator"""
    min_interval = 60.0 / calls_per_minute
    last_call = [0.0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_call[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(calls_per_minute=50)
def call_anthropic_api(prompt: str) -> str:
    # API call
    pass
```

### Retry Logic

```python
import time
from functools import wraps

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Retry with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
        return wrapper
    return decorator
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| CLI not found | Not in PATH | Install CLI or set path in .env |
| API auth failed | Invalid key | Check ANTHROPIC_API_KEY |
| Timeout | Task too complex | Increase TASK_TIMEOUT |
| Context not shared | Permission issue | Check /tmp permissions |

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG orchestrate run

# Test specific CLI
claude --version
codex --version
gemini --version

# Test database
sqlite3 tasks.db ".schema"
```

---

*Last Updated: December 2024*
