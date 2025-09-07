"""Agent Schemas - Data Models for Agent System

Responsibilities:
- Define agent data structures and types
- Provide serialization/deserialization
- Ensure type safety for agent operations
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskType(Enum):
    """Types of tasks an agent can perform"""

    FILE_EDIT = "file_edit"
    CODE_GENERATION = "code_generation"
    CONVERSATION = "conversation"
    SYSTEM_QUERY = "system_query"


class ResponseStatus(Enum):
    """Response status types"""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class AgentState:
    """Core agent state and metadata"""

    agent_id: str
    name: str
    description: str
    managed_files: List[str]
    created_at: str
    last_updated: str
    interaction_count: int
    success_rate: float
    total_tasks_completed: int
    recent_interactions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class AgentRequest:
    """Request structure for agent operations"""

    message: str
    task_type: TaskType
    agent_id: str
    context: Optional[Dict[str, Any]] = None
    files: Optional[List[str]] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AgentResponse:
    """Response structure from agent operations"""

    success: bool
    content: str
    agent_id: str
    task_type: TaskType
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
    files_modified: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["task_type"] = self.task_type.value
        return result


@dataclass
class ConversationEntry:
    """Individual conversation entry"""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


def create_standard_request(message: str, task_type: TaskType, agent_id: str) -> AgentRequest:
    """Create a standard agent request"""
    return AgentRequest(
        message=message, task_type=task_type, agent_id=agent_id, timestamp=datetime.now(timezone.utc).isoformat()
    )
