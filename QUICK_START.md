# Quick Start Guide

Get up and running with the Agent Orchestrator in under 2 minutes.

## One-Command Launch

```bash
# Complete setup and launch (first time)
./quickstart.sh
```

**What this does:**
- ✅ Checks Python 3.8+ requirement  
- ✅ Creates virtual environment
- ✅ Installs all dependencies
- ✅ Configures .env with API key
- ✅ Shows interactive launch options
- ✅ Optional demo to try the system

## Launch Options

After setup, you'll see these options:

### 1. Interactive Planning (Recommended)
```bash
./orchestrate plan "Build a REST API with authentication"
```
Start a collaborative planning session with Claude to:
- Discuss approach and requirements
- Break down tasks into phases
- Approve the plan before execution
- Automatically execute approved tasks

### 2. Quick Demo
```bash
./orchestrate demo
```
Try the system with sample tasks to see how it works.

### 3. Direct Task Submission
```bash
# Submit with automatic decomposition
./orchestrate submit "Create a blog platform" --decompose
./orchestrate run --max-agents 3

# Check progress
./orchestrate status
```

### 4. Interactive Menu
```bash
# Run without arguments for menu
./run.sh
```
Shows an interactive menu with options to plan, submit, run, or check status.

## Key Features

### Specialized Agents
The system routes tasks to appropriate specialists:
- `backend-systems-engineer`: APIs, databases, microservices
- `frontend-ui-engineer`: React/Vue/Svelte, UI components  
- `data-pipeline-engineer`: ETL/ELT, data processing
- `aws-cloud-architect`: Infrastructure, deployment
- `ml-systems-architect`: ML pipelines, MLOps
- And more...

### Parallel Processing
- Run multiple agents simultaneously (default: 3, configurable up to 10+)
- Agents share context for coordinated development
- Automatic load balancing and task routing

## Example Workflows

### Overnight Development Workflow
```bash
# Evening: Start planning session
./orchestrate plan "Build a complete e-commerce platform"

# During planning session:
# [d] Discuss approach with Claude
# [a] Add specific requirements  
# [m] Modify task breakdown
# [p] Proceed to approval and execution

# Morning: Review completed work
./orchestrate status
```

### Quick Task Workflow  
```bash
# Submit and run immediately
./run.sh submit "Add user authentication" --decompose
./run.sh run --max-agents 5

# Monitor progress
watch -n 5 './run.sh status'
```

## Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `plan <goal>` | Interactive planning session | `./orchestrate plan "Build API"` |
| `submit <task>` | Add task to queue | `./orchestrate submit "Fix bug" --decompose` |
| `run` | Process queued tasks | `./orchestrate run --max-agents 3` |
| `status` | Show queue & agent status | `./orchestrate status` |
| `task <id>` | View task details | `./orchestrate task abc123` |
| `agents` | List active agents | `./orchestrate agents` |
| `kill <id>` | Terminate agent | `./orchestrate kill agent-123` |
| `cleanup` | Remove old data | `./orchestrate cleanup` |
| `demo` | Run demo tasks | `./orchestrate demo` |

## Planning Session Commands

During interactive planning (`./orchestrate plan "goal"`):

| Command | Description |
|---------|-------------|
| `[d]` | Discuss approach with Claude |
| `[a]` | Add new tasks |
| `[r]` | Remove tasks |  
| `[m]` | Modify existing tasks |
| `[s]` | Split complex tasks |
| `[p]` | Proceed to approval/execution |

## Configuration

The system uses `.env` for configuration:

```bash
ANTHROPIC_API_KEY=your-api-key          # Required for API mode
USE_API_MODE=true                       # Recommended: true  
MAX_AGENTS=3                           # Concurrent agents
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator
```

## Troubleshooting

### Setup Issues
```bash
# If quickstart.sh fails, check Python version
python3 --version  # Should be 3.8+

# Manual setup
python3 -m venv venv_orchestrator
source venv_orchestrator/bin/activate
pip install click pyyaml anthropic python-dotenv
chmod +x orchestrate
```

### API Key Issues
```bash
# Edit configuration
nano .env  # Update ANTHROPIC_API_KEY

# Or run setup again
./quickstart.sh
```

### Agent Issues
```bash
# Check running agents
./orchestrate agents

# Kill stuck agent
./orchestrate kill <agent-id>

# Clean up old data
./orchestrate cleanup
```

## How It Works

1. **SQLite Task Queue**: Simple, file-based task storage
2. **Agent Spawning**: Direct subprocess execution of Claude CLI or API calls
3. **File-based Context**: Agents share context via `/tmp/agent_orchestrator/`
4. **No External Dependencies**: No Redis, no databases, just Python + SQLite

## Next Steps

- Try the interactive planning: `./orchestrate plan "Your goal"`
- Explore examples: `cat examples/overnight_development.sh`
- Read the full [README](README.md) for detailed architecture
- Check [CLAUDE.md](CLAUDE.md) for development guidelines