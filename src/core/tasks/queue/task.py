"""Generic Task Base Classes

Provides base classes for different types of tasks that can be queued and executed.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(Enum):
    """Task status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Base class for all tasks"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    priority: int = 0  # Higher number = higher priority

    @classmethod
    def create(cls, task_type: str, priority: int = 0, **kwargs):
        """Create a new task with generated ID and timestamp"""
        return cls(
            task_id=str(uuid.uuid4())[:8],
            task_type=task_type,
            status=TaskStatus.QUEUED,
            created_at=datetime.now(timezone.utc).isoformat(),
            priority=priority,
            **kwargs
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
        }


@dataclass
class AgentTask(Task):
    """Task for agent operations - maintains backward compatibility"""
    agent_id: str = ""
    request: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, agent_id: str, request: dict[str, Any], priority: int = 0):
        """Create a new agent task"""
        return super().create(
            task_type="agent_operation",
            agent_id=agent_id,
            request=request,
            priority=priority
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with agent-specific fields"""
        base_dict = super().to_dict()
        base_dict.update({
            "agent_id": self.agent_id,
            "request": self.request,
        })
        return base_dict


@dataclass
class ToolCallTask(Task):
    """Task for MCP tool operations"""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    agent_id: Optional[str] = None  # Add agent_id field

    def __init__(self, **kwargs):
        tool_args = kwargs.pop('tool_args', {})
        tool_name = kwargs.pop('tool_name', '')
        parent_task_id = kwargs.pop('parent_task_id', None)
        agent_id = kwargs.pop('agent_id', None)
        
        # Ensure task_type is always tool_call
        kwargs['task_type'] = "tool_call"
        
        super().__init__(**kwargs)
        
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.parent_task_id = parent_task_id
        self.agent_id = agent_id

    @classmethod
    def create(cls, tool_name: str, tool_args: dict[str, Any],
               parent_task_id: Optional[str] = None, priority: int = 1):
        """Create a new tool call task"""
        return cls(
            task_id=str(uuid.uuid4())[:8],
            status=TaskStatus.QUEUED,
            created_at=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            tool_args=tool_args,
            parent_task_id=parent_task_id,
            priority=priority
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with tool-specific fields"""
        base_dict = super().to_dict()
        base_dict.update({
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "parent_task_id": self.parent_task_id,
        })
        return base_dict
    
    def __hash__(self):
        return hash(self.task_id)
        
    def __eq__(self, other):
        if not isinstance(other, ToolCallTask):
            return NotImplemented
        return self.task_id == other.task_id