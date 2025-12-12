# Agent Orchestrator Documentation

## 📚 Example Categories

### [Web Application Development](examples/web-application-development.md)
- Full-stack e-commerce platform
- SaaS application with multi-tenancy
- Progressive Web App (PWA) conversion
- API gateway and microservices
- Real-world monitoring and best practices

### [Data Engineering Workflows](examples/data-engineering-workflows.md)
- Real-time data pipeline with Kafka and Spark
- ETL modernization with dbt and Airflow
- Data lake implementation with medallion architecture
- CDC pipeline with Debezium
- Feature store for ML
- Data quality frameworks

### [Machine Learning Projects](examples/machine-learning-projects.md)
- End-to-end ML system for production
- Computer vision pipeline with edge deployment
- NLP system for document processing
- Recommendation systems
- Time series forecasting
- A/B testing framework
- Complete MLOps pipeline

### [DevOps and Infrastructure](examples/devops-infrastructure.md)
- Kubernetes migration with zero downtime
- CI/CD pipeline with GitOps
- Infrastructure as Code with Terraform
- Disaster recovery implementation
- Monitoring and observability stack
- Security hardening and compliance
- Service mesh with Istio
- Cost optimization strategies

### [Overnight and Weekend Automation](examples/overnight-automation.md)
- Friday evening setup for weekend development
- Overnight data pipeline development
- Weekly sprint automation
- Continuous refactoring
- 24-hour hackathon mode
- Migration marathons
- Best practices for long-running sessions

## 🚀 Quick Start Examples

### Simple Task
```bash
# Add a single feature
./orchestrate submit "Add password reset functionality" --agent backend-systems-engineer
./orchestrate run
```

### Complex Project
```bash
# Plan and build entire application
./orchestrate plan "Build a social media analytics dashboard"
# Interactive planning session...
./orchestrate execute-plan social-analytics
./orchestrate run --max-agents 5
```

### Overnight Development
```bash
# Set up before leaving work
./orchestrate submit "Build complete REST API with 50 endpoints" --decompose
nohup ./orchestrate run --max-agents 4 > overnight.log 2>&1 &
```

### Multi-day / 24x7 Runs
Spawned CLI agents are considered stale after 24h by default. For multi‑day jobs you can raise or disable that limit, and control autonomous bash timeouts, via env vars:

```bash
# Disable auto-kill of long-running agents (or set a large number of hours)
export MAX_AGENT_RUNTIME_HOURS=0

# Allow longer BashTool commands in autonomous/daemon mode (0 disables)
export BASH_TOOL_TIMEOUT_SECONDS=3600

nohup ./orchestrate run --max-agents 4 > longrun.log 2>&1 &
```

## 🎯 Common Patterns

### Pattern 1: Interactive Planning
Best for complex projects requiring thoughtful decomposition.
```bash
./orchestrate plan "Your project description"
# Discuss, refine, approve
./orchestrate execute-plan
```

### Pattern 2: Auto-Decomposition
Best for well-defined tasks that can be automatically broken down.
```bash
./orchestrate submit "High-level task" --decompose
./orchestrate run
```

### Pattern 3: Specialist Assignment
Best when you know exactly which specialist should handle the task.
```bash
./orchestrate submit "Task description" --agent specialist-type
```

### Pattern 4: Parallel Execution
Best for independent tasks that can run simultaneously.
```bash
# Submit multiple tasks
for task in "${tasks[@]}"; do
  ./orchestrate submit "$task"
done
# Run with high parallelism
./orchestrate run --max-agents 6
```

## 📊 Monitoring and Control

### Status Checking
```bash
./orchestrate status          # Overall status
./orchestrate agents          # Active agents
./orchestrate task <id>       # Specific task details
```

### Progress Monitoring
```bash
# Real-time monitoring
watch -n 5 './orchestrate status'

# Continuous logging
./orchestrate run 2>&1 | tee -a orchestrator.log
```

### Error Handling
```bash
# Check for failures
./orchestrate status | grep "Failed"

# Kill stuck agent
./orchestrate kill <agent-id>

# Clean up old data
./orchestrate cleanup
```

## 💡 Tips and Tricks

### 1. Optimal Parallelism
- **2-3 agents**: Normal development
- **4-5 agents**: Large projects
- **6-8 agents**: Overnight/weekend runs

### 2. Priority Management
```bash
--priority high    # Critical tasks
--priority normal  # Regular features
--priority low     # Nice-to-haves
```

### 3. Context Preservation
Agents share context via `/tmp/agent_orchestrator/`. Tasks in the same project automatically share information.

### 4. Incremental Development
```bash
# Start small
./orchestrate submit "Create basic API" --decompose
./orchestrate run

# Then expand
./orchestrate submit "Add authentication" --decompose
./orchestrate submit "Add admin panel" --decompose
./orchestrate run
```

### 5. Testing Integration
Always include testing in your task descriptions:
```bash
./orchestrate submit "Build user service with unit tests and integration tests"
```

## 🔧 Troubleshooting

### Agent Stuck
```bash
./orchestrate agents           # Find stuck agent
./orchestrate kill <agent-id>  # Kill it
./orchestrate run              # Restart processing
```

### Database Issues
```bash
# Reset database if corrupted
mv tasks.db tasks.db.backup
./orchestrate status  # Will create new DB
```

### API Rate Limits
```bash
# Reduce parallelism
./orchestrate kill all
./orchestrate run --max-agents 2
```

## 📖 Additional Resources

- [README](../README.md) - Project overview and setup
- [examples/](../examples/) - Script examples
- [src/](../src/) - Source code for customization

## 🤝 Contributing

The orchestrator is designed to be simple and hackable. Feel free to:
- Add new agent types in `src/core/agent_spawner.py`
- Customize task decomposition in `src/core/task_decomposer.py`
- Extend CLI commands in `src/cli/orchestrate.py`

Keep it under 1000 lines total!
