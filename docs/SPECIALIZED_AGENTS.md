# Specialized Agents in the Agent Orchestrator

## Overview

The Agent Orchestrator automatically routes tasks to specialized Claude agents optimized for different domains. Each agent has deep expertise in their area and can work independently or collaboratively with other agents.

## Available Specialized Agents

| Agent Type | CLI Name | Best For |
|------------|----------|----------|
| `data-pipeline-engineer` | Data Pipeline Engineer | ETL/ELT workflows, Apache Spark, Airflow, dbt |
| `backend-systems-engineer` | Backend Engineer | APIs, microservices, databases, authentication |
| `frontend-ui-engineer` | Frontend Engineer | React/Vue/Svelte, responsive design, UI/UX |
| `data-science-analyst` | Data Scientist | EDA, ML models, statistical analysis, visualization |
| `aws-cloud-architect` | AWS Architect | AWS infrastructure, IaC, monitoring, cost optimization |
| `ml-systems-architect` | ML Architect | ML pipelines, MLOps, model deployment |
| `project-delivery-manager` | Project Manager | Sprint planning, risk management, coordination |
| `data-architect-governance` | Data Architect | Data models, governance, lineage, quality |
| `llm-architect` | LLM Architect | LLM systems, RAG, prompting, fine-tuning |
| `specifications-engineer` | Specs Engineer | Requirements analysis, acceptance criteria |

## How It Works

1. **Task Submission**: When you submit a task, you can specify which agent to use, or let the system choose based on the task description.

2. **Agent Invocation**: The orchestrator spawns a Claude CLI process with a prompt that instructs it to use the Task tool with the appropriate specialized agent.

3. **Specialized Processing**: Claude uses its internal Task tool to launch the specialized agent, which has domain-specific knowledge and capabilities.

4. **Results Collection**: The agent completes the task and returns results, which are captured by the orchestrator.

## Usage Examples

### Manual Agent Selection

```bash
# Submit a task to a specific specialized agent
./orchestrate submit "Design a data warehouse schema" --agent data-architect-governance

# Submit a backend task
./orchestrate submit "Implement JWT authentication" --agent backend-systems-engineer

# Submit a frontend task  
./orchestrate submit "Build responsive navigation component" --agent frontend-ui-engineer
```

### Automatic Agent Selection with Decomposition

```bash
# Submit a high-level task - system automatically assigns specialized agents
./orchestrate submit "Build a real-time analytics dashboard" --decompose

# This might decompose into:
# 1. [data-architect-governance] Design data model
# 2. [data-pipeline-engineer] Build data pipeline
# 3. [backend-systems-engineer] Create API endpoints
# 4. [frontend-ui-engineer] Build dashboard UI
# 5. [data-science-analyst] Implement analytics
```

### Interactive Planning with Specialized Agents

```bash
# Start interactive planning - system will automatically assign specialized agents
./orchestrate plan "Build a complete e-commerce platform"

# During planning, you can discuss which agents should handle which tasks
```

## Implementation Details

### Agent Spawner

The `AgentSpawner` supports two modes for specialized agents:

**API Mode (Recommended):**
```python
# Direct API calls with specialized agent types
spawner.spawn_agent(
    agent_type="backend-systems-engineer",
    task_id="auth-001", 
    task_description="Implement JWT authentication"
)
```

**CLI Mode:**
```python
# CLI spawning with Task tool invocation
prompt = """Use the Task tool to launch a backend-systems-engineer agent with the following task:
Implement JWT authentication for the user API
IMPORTANT: Use subagent_type='backend-systems-engineer'
"""
```

### Task Decomposer

The `TaskDecomposer` intelligently assigns tasks to specialized agents based on keywords and patterns:

- API/backend tasks → `backend-systems-engineer`
- UI/frontend tasks → `frontend-ui-engineer`  
- Data pipeline tasks → `data-pipeline-engineer`
- ML tasks → `ml-systems-architect` or `data-science-analyst`
- AWS/cloud tasks → `aws-cloud-architect`
- Requirements tasks → `specifications-engineer`

## Benefits

1. **Domain Expertise**: Each agent has specialized knowledge in its domain
2. **Better Results**: Tasks are handled by agents optimized for that type of work
3. **Parallel Execution**: Different specialized agents can work on different parts simultaneously
4. **Automatic Routing**: System can automatically choose the best agent for each task

## Configuration

Configure specialized agents in your `.env` file:

```bash
# Agent Orchestrator Configuration
USE_API_MODE=true                       # Enables specialized agent types
ANTHROPIC_API_KEY=your-api-key          # Required for API mode
MAX_AGENTS=3                           # Number of parallel agents
```

Manual agent selection in CLI:
```bash
# Force specific agent type
./orchestrate submit "Build API" --agent backend-systems-engineer

# Let system choose automatically  
./orchestrate submit "Build API" --decompose
```

## Best Practices

1. **Use Interactive Planning**: Start with `./orchestrate plan "goal"` for complex projects
2. **Leverage Auto-decomposition**: Use `--decompose` for intelligent agent assignment  
3. **Be Specific**: Clear task descriptions help the system choose the right agent
4. **Monitor Progress**: Use `./orchestrate status` to track which agents are working
5. **Review Context**: Agents share context automatically for coordinated work

## Quick Start with Specialized Agents

```bash
# Setup (first time)
./quickstart.sh

# Interactive planning (recommended)
./orchestrate plan "Build a blog platform with authentication"

# Direct submission with auto-decomposition
./orchestrate submit "Create a data pipeline" --decompose
./orchestrate run --max-agents 5

# Check which agents are working
./orchestrate agents
```

## Troubleshooting

### API Mode Issues (Recommended)
```bash
# Check API key configuration
grep ANTHROPIC_API_KEY .env

# Verify API mode is enabled
grep USE_API_MODE .env
```

### CLI Mode Issues  
```bash
# Verify Claude CLI is installed
which claude

# Test Claude CLI access
claude --version

# Check permissions
claude --dangerously-skip-permissions -p "Hello"
```

### General Issues
```bash
# Check system status
./orchestrate status

# View agent logs
ls /tmp/agent_orchestrator/

# Clean up and retry
./orchestrate cleanup
```