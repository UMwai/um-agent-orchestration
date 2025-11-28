"""
API-based Agent Execution
Uses Claude API for actual agent work instead of CLI processes
"""

import os
import json
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import anthropic
from pathlib import Path


class AgentType(Enum):
    CLAUDE = "claude"
    BACKEND = "backend-systems-engineer"
    FRONTEND = "frontend-ui-engineer"
    DATA_PIPELINE = "data-pipeline-engineer"
    DATA_SCIENTIST = "data-science-analyst"
    SPECS = "specifications-engineer"
    PROJECT_MANAGER = "project-delivery-manager"

    # For non-Claude agents
    CODEX = "codex"
    GENERIC = "generic"


@dataclass
class AgentTask:
    """Represents a task for an agent"""

    task_id: str
    description: str
    agent_type: AgentType
    context: Dict[str, Any] = None
    status: str = "pending"
    result: str = None
    error: str = None
    started_at: float = 0
    completed_at: float = 0


class AgentAPI:
    """Manages API-based agent execution"""

    def __init__(self, api_key: str = None, base_dir: str = "/tmp/agent_orchestrator"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Claude client if API key available
        self.client = None
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        self.tasks: Dict[str, AgentTask] = {}

    def execute_task(self, task: AgentTask) -> str:
        """Execute a task using the appropriate agent"""
        task.started_at = time.time()
        task.status = "in_progress"

        try:
            # Route to appropriate execution method
            if task.agent_type == AgentType.CODEX:
                result = self._execute_codex_task(task)
            elif self.client:
                result = self._execute_claude_task(task)
            else:
                result = self._execute_mock_task(task)

            task.result = result
            task.status = "completed"
            task.completed_at = time.time()

            # Save result to file
            self._save_result(task)

            return result

        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            task.completed_at = time.time()
            raise

    def _execute_claude_task(self, task: AgentTask) -> str:
        """Execute task using Claude API"""
        # Build the prompt based on agent type
        prompt = self._build_agent_prompt(task)

        try:
            # Call Claude API
            message = self.client.messages.create(
                model="claude-3-sonnet-20241022",
                max_tokens=4000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text response
            result = message.content[0].text if message.content else "No response"
            return result

        except Exception as e:
            print(f"Claude API error: {e}")
            # Fallback to mock execution
            return self._execute_mock_task(task)

    def _build_agent_prompt(self, task: AgentTask) -> str:
        """Build specialized prompt based on agent type"""
        base_prompt = f"Task: {task.description}"

        # Add context if available
        if task.context:
            base_prompt += f"\n\nContext:\n{json.dumps(task.context, indent=2)}"

        # Add agent-specific instructions
        agent_prompts = {
            AgentType.BACKEND: """
You are a backend systems engineer. Focus on:
- API design and implementation
- Database schema and queries
- Authentication and authorization
- Performance and scalability
- Error handling and logging

Please provide a detailed implementation plan or solution.""",
            AgentType.FRONTEND: """
You are a frontend UI engineer. Focus on:
- Component architecture
- User experience and accessibility
- State management
- Responsive design
- Performance optimization

Please provide a detailed implementation plan or solution.""",
            AgentType.DATA_PIPELINE: """
You are a data pipeline engineer. Focus on:
- ETL/ELT design
- Data quality and validation
- Scalability and performance
- Error handling and recovery
- Monitoring and alerting

Please provide a detailed implementation plan or solution.""",
            AgentType.SPECS: """
You are a specifications engineer. Focus on:
- Clear requirements definition
- Acceptance criteria
- Technical specifications
- Edge cases and error scenarios
- Testing requirements

Please provide detailed specifications.""",
            AgentType.PROJECT_MANAGER: """
You are a project delivery manager. Focus on:
- Task breakdown and dependencies
- Timeline and milestones
- Risk assessment
- Resource allocation
- Success metrics

Please provide a project plan.""",
        }

        agent_instruction = agent_prompts.get(
            task.agent_type,
            "You are an AI assistant. Please complete the task to the best of your ability.",
        )

        return f"{agent_instruction}\n\n{base_prompt}"

    def _execute_codex_task(self, task: AgentTask) -> str:
        """Execute task using Codex/OpenAI API (placeholder)"""
        # This would integrate with OpenAI API if available
        # For now, return mock response
        return self._execute_mock_task(task)

    def _execute_mock_task(self, task: AgentTask) -> str:
        """Execute task in mock/demo mode"""
        responses = {
            AgentType.BACKEND: f"""
DEMO MODE - Backend Implementation Plan for: {task.description}

1. API Design:
   - RESTful endpoints following best practices
   - Input validation and sanitization
   - Proper HTTP status codes

2. Database Schema:
   - Normalized tables with proper indices
   - Migration scripts for version control
   
3. Authentication:
   - JWT-based authentication
   - Role-based access control
   
4. Implementation:
   - Service layer for business logic
   - Repository pattern for data access
   - Comprehensive error handling

5. Testing:
   - Unit tests for all services
   - Integration tests for API endpoints
   - Performance testing for critical paths
""",
            AgentType.FRONTEND: f"""
DEMO MODE - Frontend Implementation Plan for: {task.description}

1. Component Architecture:
   - Modular, reusable components
   - Clear separation of concerns
   - Props validation

2. State Management:
   - Context API for global state
   - Local state for component-specific data
   - Optimistic UI updates

3. UI/UX Design:
   - Responsive layout using CSS Grid/Flexbox
   - Accessibility standards (WCAG 2.1)
   - Loading states and error boundaries

4. Performance:
   - Code splitting and lazy loading
   - Memoization for expensive operations
   - Image optimization

5. Testing:
   - Component unit tests
   - Integration tests for user flows
   - Visual regression testing
""",
            AgentType.DATA_PIPELINE: f"""
DEMO MODE - Data Pipeline Design for: {task.description}

1. Data Ingestion:
   - Batch and streaming ingestion support
   - Schema validation on input
   - Error handling and dead letter queues

2. Transformation:
   - Idempotent transformations
   - Data quality checks
   - Incremental processing

3. Storage:
   - Partitioned data lake structure
   - Optimized file formats (Parquet/ORC)
   - Data retention policies

4. Orchestration:
   - DAG-based workflow
   - Retry logic with exponential backoff
   - Alerting on failures

5. Monitoring:
   - Data quality metrics
   - Pipeline performance metrics
   - Cost optimization tracking
""",
            AgentType.SPECS: f"""
DEMO MODE - Specifications for: {task.description}

## Functional Requirements
1. The system SHALL provide the requested functionality
2. The system SHALL handle expected load and scale appropriately
3. The system SHALL maintain data integrity and consistency

## Non-Functional Requirements
1. Performance: Response time < 200ms for 95th percentile
2. Availability: 99.9% uptime SLA
3. Security: Industry-standard encryption and authentication

## Acceptance Criteria
- [ ] All functional requirements are met
- [ ] Performance benchmarks achieved
- [ ] Security audit passed
- [ ] Documentation complete

## Test Cases
1. Happy path scenarios
2. Edge cases and error conditions
3. Performance under load
4. Security vulnerability testing
""",
        }

        return responses.get(
            task.agent_type,
            f"DEMO MODE - Generic response for: {task.description}\n\nTask would be processed by {task.agent_type.value} agent.",
        )

    def _save_result(self, task: AgentTask):
        """Save task result to file"""
        task_dir = self.base_dir / f"task_{task.task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        # Save result
        result_file = task_dir / "result.txt"
        with open(result_file, "w") as f:
            f.write(task.result or task.error or "No output")

        # Save metadata
        metadata_file = task_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(
                {
                    "task_id": task.task_id,
                    "description": task.description,
                    "agent_type": task.agent_type.value,
                    "status": task.status,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "duration": task.completed_at - task.started_at
                    if task.completed_at
                    else None,
                    "context": task.context,
                },
                f,
                indent=2,
            )

    def get_task_result(self, task_id: str) -> Optional[str]:
        """Get result for a completed task"""
        task_dir = self.base_dir / f"task_{task_id}"
        result_file = task_dir / "result.txt"

        if result_file.exists():
            with open(result_file, "r") as f:
                return f.read()

        return None


if __name__ == "__main__":
    # Test the API
    api = AgentAPI()

    # Create a test task
    task = AgentTask(
        task_id="test-001",
        description="Design a REST API for user management",
        agent_type=AgentType.BACKEND,
        context={
            "requirements": [
                "user registration",
                "authentication",
                "profile management",
            ]
        },
    )

    print(f"Executing task: {task.description}")
    result = api.execute_task(task)
    print(f"\nResult:\n{result}")
