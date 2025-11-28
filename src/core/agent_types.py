"""
Agent type definitions and utilities
"""

from enum import Enum
from typing import List, Optional


class AgentType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    # Specialized agents
    DATA_PIPELINE = "data-pipeline-engineer"
    BACKEND_ENGINEER = "backend-systems-engineer"
    FRONTEND_ENGINEER = "frontend-ui-engineer"
    DATA_SCIENTIST = "data-science-analyst"
    AWS_ARCHITECT = "aws-cloud-architect"
    ML_ARCHITECT = "ml-systems-architect"
    PROJECT_MANAGER = "project-delivery-manager"
    DATA_ARCHITECT = "data-architect-governance"
    LLM_ARCHITECT = "llm-architect"
    SPECS_ENGINEER = "specifications-engineer"


class AgentCapabilities:
    """Agent capabilities and metadata"""

    CAPABILITIES = {
        AgentType.CLAUDE: {
            "icon": "🤔",
            "description": "General analysis and design",
            "categories": ["analysis", "planning", "documentation"],
        },
        AgentType.CODEX: {
            "icon": "💻",
            "description": "Code implementation",
            "categories": ["coding", "implementation"],
        },
        AgentType.DATA_PIPELINE: {
            "icon": "🔄",
            "description": "ETL/data pipeline tasks",
            "categories": ["data", "pipeline", "etl"],
        },
        AgentType.BACKEND_ENGINEER: {
            "icon": "⚙️",
            "description": "Backend APIs and services",
            "categories": ["backend", "api", "services"],
        },
        AgentType.FRONTEND_ENGINEER: {
            "icon": "🎨",
            "description": "UI/frontend development",
            "categories": ["frontend", "ui", "react", "vue"],
        },
        AgentType.DATA_SCIENTIST: {
            "icon": "📊",
            "description": "Data analysis and ML models",
            "categories": ["data", "ml", "analysis"],
        },
        AgentType.AWS_ARCHITECT: {
            "icon": "☁️",
            "description": "AWS infrastructure",
            "categories": ["aws", "cloud", "infrastructure"],
        },
        AgentType.ML_ARCHITECT: {
            "icon": "🤖",
            "description": "ML system design",
            "categories": ["ml", "architecture", "systems"],
        },
        AgentType.PROJECT_MANAGER: {
            "icon": "📅",
            "description": "Project coordination",
            "categories": ["planning", "coordination", "management"],
        },
        AgentType.DATA_ARCHITECT: {
            "icon": "🏗️",
            "description": "Data architecture",
            "categories": ["data", "architecture", "governance"],
        },
        AgentType.LLM_ARCHITECT: {
            "icon": "🧠",
            "description": "LLM system design",
            "categories": ["llm", "ai", "architecture"],
        },
        AgentType.SPECS_ENGINEER: {
            "icon": "📋",
            "description": "Requirements and specs",
            "categories": ["requirements", "specifications", "analysis"],
        },
    }

    @classmethod
    def get_icon(cls, agent_type: AgentType) -> str:
        """Get icon for agent type"""
        return cls.CAPABILITIES.get(agent_type, {}).get("icon", "📦")

    @classmethod
    def get_description(cls, agent_type: AgentType) -> str:
        """Get description for agent type"""
        return cls.CAPABILITIES.get(agent_type, {}).get("description", "Unknown agent")

    @classmethod
    def get_categories(cls, agent_type: AgentType) -> List[str]:
        """Get categories for agent type"""
        return cls.CAPABILITIES.get(agent_type, {}).get("categories", [])

    @classmethod
    def from_string(cls, agent_str: str) -> Optional[AgentType]:
        """Convert string to AgentType"""
        for agent_type in AgentType:
            if agent_type.value == agent_str:
                return agent_type
        return None

    @classmethod
    def get_specialized_agents(cls) -> List[AgentType]:
        """Get list of specialized agents (excluding generic ones)"""
        return [t for t in AgentType if t not in (AgentType.CLAUDE, AgentType.CODEX)]

    @classmethod
    def recommend_agent(cls, task_description: str) -> AgentType:
        """Recommend best agent type based on task description"""
        task_lower = task_description.lower()

        # Simple keyword-based recommendation
        keywords_map = {
            ("api", "backend", "server"): AgentType.BACKEND_ENGINEER,
            ("ui", "frontend", "react", "vue"): AgentType.FRONTEND_ENGINEER,
            ("data", "pipeline", "etl"): AgentType.DATA_PIPELINE,
            ("ml", "model", "machine learning"): AgentType.ML_ARCHITECT,
            ("aws", "cloud", "infrastructure"): AgentType.AWS_ARCHITECT,
            ("spec", "requirement", "analysis"): AgentType.SPECS_ENGINEER,
            ("llm", "chatbot", "ai"): AgentType.LLM_ARCHITECT,
        }

        for keywords, agent_type in keywords_map.items():
            if any(keyword in task_lower for keyword in keywords):
                return agent_type

        return AgentType.CLAUDE  # Default fallback
