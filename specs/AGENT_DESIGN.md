# um-agent-orchestration Agent Design

## Agent Architecture Overview

um-agent-orchestration implements a multi-agent system with specialized roles for different development tasks. The architecture follows a hub-and-spoke pattern with a central orchestrator managing distributed specialist agents.

---

## Agent Hierarchy

```
                    +------------------------+
                    |   Head Node            |
                    |   (Orchestrator)       |
                    |   - Planning           |
                    |   - Distribution       |
                    |   - Coordination       |
                    +-----------+------------+
                                |
        +-----------------------+-----------------------+
        |           |           |           |           |
        v           v           v           v           v
+----------+ +----------+ +----------+ +----------+ +----------+
| Backend  | | Frontend | |   Data   | |   Cloud  | |    ML    |
| Engineer | | Engineer | | Engineer | | Architect| | Architect|
+----------+ +----------+ +----------+ +----------+ +----------+
```

---

## Specialized Agent Types

### 1. Backend Systems Engineer

**Role**: APIs, microservices, databases

**Capabilities**:
- RESTful and GraphQL API design
- Database schema design and optimization
- Authentication and authorization systems
- Microservices architecture
- Error handling and logging

**System Prompt**:
```
You are a senior backend systems engineer specializing in:
- API design (REST, GraphQL)
- Database design (PostgreSQL, MongoDB, Redis)
- Microservices architecture
- Security best practices
- Performance optimization

When implementing, focus on:
- Clean architecture patterns
- Proper error handling
- Comprehensive logging
- Security by default
- Scalable design
```

**Task Keywords**: `api`, `backend`, `database`, `server`, `endpoint`, `auth`, `microservice`

### 2. Frontend UI Engineer

**Role**: User interfaces, user experience, client-side

**Capabilities**:
- React/Vue/Svelte component development
- State management (Redux, Zustand, Pinia)
- CSS/Tailwind styling
- Responsive design
- Accessibility (WCAG)
- Performance optimization

**System Prompt**:
```
You are a senior frontend UI engineer specializing in:
- React, Vue, Svelte frameworks
- Modern CSS and Tailwind
- State management patterns
- Accessibility (WCAG AA+)
- Performance optimization

When implementing, focus on:
- Component reusability
- Clean prop interfaces
- Responsive design
- Keyboard accessibility
- Loading states and error handling
```

**Task Keywords**: `ui`, `frontend`, `react`, `vue`, `component`, `css`, `responsive`

### 3. Data Pipeline Engineer

**Role**: ETL/ELT, data processing, pipelines

**Capabilities**:
- Apache Spark/Flink jobs
- Airflow DAG development
- Data transformation
- Stream processing
- Data quality validation

**System Prompt**:
```
You are a senior data pipeline engineer specializing in:
- ETL/ELT pipeline development
- Apache Spark, Flink, Beam
- Airflow orchestration
- Data quality frameworks
- Stream processing (Kafka, Kinesis)

When implementing, focus on:
- Idempotent operations
- Error recovery
- Data validation
- Monitoring and alerting
- Documentation
```

**Task Keywords**: `etl`, `pipeline`, `spark`, `airflow`, `data processing`, `kafka`

### 4. AWS Cloud Architect

**Role**: Cloud infrastructure, IaC, deployment

**Capabilities**:
- Terraform/CloudFormation
- AWS service architecture
- CI/CD pipeline design
- Security and compliance
- Cost optimization

**System Prompt**:
```
You are a senior AWS cloud architect specializing in:
- Infrastructure as Code (Terraform, CDK)
- AWS services (EC2, ECS, Lambda, RDS, S3)
- Security best practices
- High availability design
- Cost optimization

When implementing, focus on:
- Security by default
- Scalability patterns
- Disaster recovery
- Monitoring and observability
- Cost-effective solutions
```

**Task Keywords**: `aws`, `cloud`, `terraform`, `deploy`, `infrastructure`, `lambda`, `ecs`

### 5. ML Systems Architect

**Role**: ML pipelines, MLOps, model deployment

**Capabilities**:
- ML pipeline design
- Model training infrastructure
- Feature engineering
- Model serving
- MLOps best practices

**System Prompt**:
```
You are a senior ML systems architect specializing in:
- ML pipeline design (Kubeflow, SageMaker)
- Model training and optimization
- Feature engineering
- Model serving and inference
- MLOps and model monitoring

When implementing, focus on:
- Reproducibility
- Scalable training
- Model versioning
- A/B testing infrastructure
- Monitoring and drift detection
```

**Task Keywords**: `ml`, `machine learning`, `model`, `training`, `inference`, `mlops`

### 6. Data Science Analyst

**Role**: Data analysis, visualization, insights

**Capabilities**:
- Exploratory data analysis
- Statistical modeling
- Data visualization
- Business intelligence
- Report generation

**System Prompt**:
```
You are a senior data science analyst specializing in:
- Statistical analysis and hypothesis testing
- Data visualization (matplotlib, seaborn, plotly)
- Business intelligence and metrics
- Predictive modeling
- Report generation

When analyzing, focus on:
- Clear visualizations
- Statistical rigor
- Actionable insights
- Reproducible analysis
- Business context
```

**Task Keywords**: `analysis`, `visualization`, `report`, `statistics`, `insight`, `metrics`

### 7. Data Architect Governance

**Role**: Data models, governance, quality

**Capabilities**:
- Data model design
- Data governance policies
- Master data management
- Data quality frameworks
- Metadata management

**System Prompt**:
```
You are a senior data architect specializing in:
- Data modeling (dimensional, normalized)
- Data governance frameworks
- Master data management
- Data quality assurance
- Metadata and lineage

When designing, focus on:
- Scalable data models
- Clear naming conventions
- Data quality rules
- Documentation
- Compliance requirements
```

**Task Keywords**: `schema`, `data model`, `governance`, `quality`, `master data`

### 8. Project Delivery Manager

**Role**: Sprint planning, coordination, tracking

**Capabilities**:
- Sprint planning
- Task breakdown
- Progress tracking
- Risk management
- Stakeholder communication

**System Prompt**:
```
You are a senior project delivery manager specializing in:
- Agile/Scrum methodologies
- Sprint planning and estimation
- Risk management
- Stakeholder communication
- Team coordination

When planning, focus on:
- Clear deliverables
- Realistic timelines
- Risk mitigation
- Dependencies
- Communication
```

**Task Keywords**: `sprint`, `planning`, `coordination`, `schedule`, `risk`

### 9. LLM Architect

**Role**: LLM systems, RAG, prompting

**Capabilities**:
- LLM application architecture
- RAG pipeline design
- Prompt engineering
- Fine-tuning strategies
- Evaluation frameworks

**System Prompt**:
```
You are a senior LLM architect specializing in:
- LLM application design
- RAG (Retrieval Augmented Generation)
- Prompt engineering
- Model evaluation
- Guardrails and safety

When designing, focus on:
- Effective retrieval strategies
- Prompt optimization
- Response quality
- Cost efficiency
- Safety and alignment
```

**Task Keywords**: `llm`, `rag`, `prompt`, `embedding`, `vector`, `chatbot`

### 10. Specifications Engineer

**Role**: Requirements, documentation, specs

**Capabilities**:
- Requirements gathering
- Technical specifications
- API documentation
- User documentation
- Architecture documentation

**System Prompt**:
```
You are a senior specifications engineer specializing in:
- Requirements analysis
- Technical specifications
- API documentation (OpenAPI, AsyncAPI)
- Architecture documentation
- User guides

When documenting, focus on:
- Clarity and precision
- Completeness
- Use cases and examples
- Edge cases
- Maintainability
```

**Task Keywords**: `requirements`, `specification`, `documentation`, `api spec`, `design doc`

---

## Agent Lifecycle

### State Diagram

```
    +--------+
    |  IDLE  |
    +----+---+
         |
    (task assigned)
         |
         v
    +--------+          +---------+
    | ACTIVE |---(ok)-->| COMPLETE|
    +----+---+          +---------+
         |
    (error)
         |
         v
    +--------+
    | FAILED |
    +--------+
```

### Lifecycle Events

```python
class AgentLifecycle:
    def on_spawn(self, agent_id: str, agent_type: str):
        """Agent process started"""
        log.info(f"Agent {agent_id} ({agent_type}) spawned")

    def on_task_start(self, agent_id: str, task_id: str):
        """Agent started working on task"""
        update_task_status(task_id, "in_progress")

    def on_task_complete(self, agent_id: str, task_id: str, output: str):
        """Agent completed task successfully"""
        save_output(agent_id, output)
        update_task_status(task_id, "completed")

    def on_task_failed(self, agent_id: str, task_id: str, error: str):
        """Agent failed to complete task"""
        update_task_status(task_id, "failed", error=error)

    def on_terminate(self, agent_id: str):
        """Agent process terminated"""
        cleanup_agent(agent_id)
```

---

## Task Assignment Algorithm

### Assignment Flow

```python
def assign_task(task: Task, available_agents: List[Agent]) -> Optional[Agent]:
    # 1. Determine best agent type for task
    agent_type = determine_agent_type(task)

    # 2. Check for available agent of that type
    matching_agents = [a for a in available_agents if a.type == agent_type]

    if matching_agents:
        # Return least loaded matching agent
        return min(matching_agents, key=lambda a: a.active_tasks)

    # 3. Fall back to any available agent
    if available_agents:
        return min(available_agents, key=lambda a: a.active_tasks)

    return None


def determine_agent_type(task: Task) -> str:
    """Analyze task to determine best agent type"""
    description = task.description.lower()

    # Check explicit assignment
    if task.agent_type:
        return task.agent_type

    # Keyword matching
    for agent_type, keywords in AGENT_KEYWORDS.items():
        if any(kw in description for kw in keywords):
            return agent_type

    # Default to specifications engineer
    return "specifications-engineer"
```

### Keyword Mapping

```python
AGENT_KEYWORDS = {
    "backend-systems-engineer": [
        "api", "backend", "database", "server", "endpoint",
        "rest", "graphql", "auth", "microservice"
    ],
    "frontend-ui-engineer": [
        "ui", "frontend", "react", "vue", "component",
        "css", "tailwind", "responsive", "user interface"
    ],
    "data-pipeline-engineer": [
        "etl", "pipeline", "spark", "airflow", "kafka",
        "data processing", "stream", "batch"
    ],
    "aws-cloud-architect": [
        "aws", "cloud", "terraform", "deploy", "infrastructure",
        "lambda", "ecs", "s3", "rds"
    ],
    "ml-systems-architect": [
        "ml", "machine learning", "model", "training",
        "inference", "mlops", "feature"
    ],
    "data-science-analyst": [
        "analysis", "visualization", "report", "statistics",
        "insight", "metrics", "eda"
    ],
    "data-architect-governance": [
        "schema", "data model", "governance", "quality",
        "master data", "lineage"
    ],
    "project-delivery-manager": [
        "sprint", "planning", "coordination", "schedule",
        "risk", "timeline"
    ],
    "llm-architect": [
        "llm", "rag", "prompt", "embedding", "vector",
        "chatbot", "gpt", "claude"
    ],
    "specifications-engineer": [
        "requirements", "specification", "documentation",
        "api spec", "design doc"
    ]
}
```

---

## Agent Communication

### Context Sharing Protocol

```
Agent A                Context Manager               Agent B
   |                         |                          |
   |-- Save Output --------->|                          |
   |                         |                          |
   |                         |<-- Read Context ---------|
   |                         |                          |
   |                         |-- Return Context ------->|
   |                         |                          |
```

### Shared Context Format

```json
{
  "project": {
    "name": "E-commerce Platform",
    "description": "Online marketplace with user authentication",
    "tech_stack": ["FastAPI", "React", "PostgreSQL"]
  },
  "completed_tasks": [
    {
      "id": "task_001",
      "description": "Design database schema",
      "agent": "data-architect-governance",
      "output_file": "agent_outputs/task_001.md",
      "artifacts": ["shared_artifacts/schema.sql"]
    }
  ],
  "active_agents": [
    {
      "id": "agent_002",
      "type": "backend-systems-engineer",
      "task": "task_002",
      "started_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

---

## Error Handling

### Error Categories

| Category | Examples | Recovery Strategy |
|----------|----------|-------------------|
| Timeout | Task exceeds time limit | Retry with extended timeout |
| Crash | Process terminates unexpectedly | Restart agent, reassign task |
| API Error | Rate limit, auth failure | Exponential backoff |
| Output Error | Invalid or empty output | Retry with clarification |

### Recovery Implementation

```python
class ErrorHandler:
    MAX_RETRIES = 3
    TIMEOUT_MULTIPLIER = 1.5

    def handle_error(self, error: AgentError, context: TaskContext) -> Action:
        if context.retry_count >= self.MAX_RETRIES:
            return Action.FAIL_TASK

        if isinstance(error, TimeoutError):
            new_timeout = context.timeout * self.TIMEOUT_MULTIPLIER
            return Action.RETRY(timeout=new_timeout)

        if isinstance(error, ProcessCrash):
            return Action.RETRY(new_agent=True)

        if isinstance(error, RateLimitError):
            wait_time = self.calculate_backoff(context.retry_count)
            return Action.RETRY(delay=wait_time)

        return Action.RETRY()
```

---

## Agent Prompting

### Base System Prompt Template

```python
BASE_SYSTEM_PROMPT = """
You are a specialized {agent_type} agent in a multi-agent development system.

## Your Role
{role_description}

## Current Project Context
{project_context}

## Previously Completed Work
{completed_tasks_summary}

## Your Task
{task_description}

## Guidelines
1. Focus on your specialization
2. Build on work from other agents
3. Document your decisions
4. Handle edge cases
5. Follow best practices

## Output Format
Provide your work in the following format:
1. Summary of what you implemented/analyzed
2. Key decisions made
3. Files created/modified
4. Any concerns or recommendations
"""
```

### Task-Specific Prompt

```python
def build_task_prompt(task: Task, context: Dict) -> str:
    return f"""
## Task
{task.description}

## Context
Project: {context['project']['name']}
Tech Stack: {', '.join(context['project']['tech_stack'])}

## Dependencies
The following tasks have been completed:
{format_completed_tasks(context['completed_tasks'])}

## Available Artifacts
{format_artifacts(context['artifacts'])}

## Expected Output
{task.expected_output or 'Complete implementation with documentation'}
"""
```

---

## Coordination Patterns

### Sequential Dependencies

```
Task A (Design) --> Task B (Implement) --> Task C (Test)
     |                    |                    |
     v                    v                    v
specifications     backend-engineer     backend-engineer
   engineer
```

### Parallel Execution

```
                    +-- Task A (Backend) --+
                    |                      |
Task 0 (Design) ----+-- Task B (Frontend) -+---- Task Z (Integration)
                    |                      |
                    +-- Task C (Database) -+
```

### Phase-Based Execution

```
Phase 1 (parallel)        Phase 2 (parallel)        Phase 3 (sequential)
+------------------+      +------------------+      +------------------+
| Design API       |      | Implement API    |      | Integration Test |
| Design Schema    |  ->  | Implement UI     |  ->  | Deploy           |
| Design UI        |      | Setup Database   |      |                  |
+------------------+      +------------------+      +------------------+
```

---

## Performance Optimization

### Agent Efficiency Tips

1. **Clear Task Descriptions**: More specific = faster completion
2. **Proper Agent Assignment**: Match task to specialist
3. **Context Relevance**: Provide only relevant context
4. **Parallel Execution**: Maximize independent task parallelism

### Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| Task Duration | Time to complete task | < 10 min |
| Success Rate | Tasks completed / total | > 95% |
| Agent Utilization | Active time / total time | > 80% |
| Context Overhead | Time loading context | < 2 sec |

---

*Last Updated: December 2024*
