# File: ~/Projects/local-llm-mcp/schemas/agent_schemas.py
"""Standardized JSON schemas for agent communications
Ensures consistent structure across all agent interactions
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Standardized task types"""

    CREATE = "create"
    UPDATE = "update"
    ANALYZE = "analyze"
    REFACTOR = "refactor"
    DEBUG = "debug"
    DOCUMENT = "document"
    TEST = "test"


class ResponseStatus(str, Enum):
    """Response status codes"""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class FileOperation(str, Enum):
    """File operation types"""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    BACKUP = "backup"


class AgentRequest(BaseModel):
    """Standardized request format for agents"""

    task_type: TaskType = Field(..., description="Type of task to perform")
    instruction: str = Field(..., description="Detailed instruction for the agent")
    context: str | None = Field(None, description="Additional context for the task")
    parameters: dict[str, Any] | None = Field(default_factory=dict, description="Task-specific parameters")
    expected_output: str | None = Field(None, description="Description of expected output format")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Request timestamp")


class FileContent(BaseModel):
    """File content structure"""

    filename: str = Field(..., description="Name of the file")
    content: str = Field(..., description="Complete file content")
    language: str | None = Field(None, description="Programming language or file type")
    encoding: str = Field(default="utf-8", description="File encoding")
    line_count: int | None = Field(None, description="Number of lines in file")


class AgentResponse(BaseModel):
    """Standardized response format from agents"""

    status: ResponseStatus = Field(..., description="Response status")
    message: str = Field(..., description="Human-readable message")
    file_content: FileContent | None = Field(None, description="File content if applicable")
    changes_made: list[str] = Field(default_factory=list, description="List of changes made")
    warnings: list[str] = Field(default_factory=list, description="Any warnings or notes")
    tokens_used: int | None = Field(None, description="Number of tokens used in generation")
    processing_time: float | None = Field(None, description="Processing time in seconds")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class AgentState(BaseModel):
    """Agent's current state in JSON format"""

    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    managed_file: str = Field(..., description="Single file managed by this agent")
    system_prompt: str = Field(..., description="Agent's system prompt")
    context: str = Field(default="", description="Current context/understanding")
    last_task: TaskType | None = Field(None, description="Last task performed")
    last_activity: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_interactions: int = Field(default=0, description="Total number of interactions")
    success_rate: float = Field(default=1.0, description="Success rate of tasks (0.0-1.0)")


class ConversationEntry(BaseModel):
    """Single conversation entry with standardized format"""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request: AgentRequest = Field(..., description="Original request")
    response: AgentResponse = Field(..., description="Agent response")
    session_id: str | None = Field(None, description="Session identifier")


class AgentCapabilities(BaseModel):
    """Define what an agent can do"""

    supported_tasks: list[TaskType] = Field(default_factory=list)
    file_extensions: list[str] = Field(default_factory=list, description="File extensions this agent handles")
    programming_languages: list[str] = Field(default_factory=list)
    specializations: list[str] = Field(default_factory=list, description="Areas of expertise")
    max_file_size: int = Field(default=100000, description="Maximum file size in characters")


class SystemMetrics(BaseModel):
    """System performance metrics"""

    total_agents: int = Field(..., description="Number of active agents")
    total_files_managed: int = Field(..., description="Number of files under management")
    average_response_time: float = Field(..., description="Average response time in seconds")
    total_tokens_used: int = Field(default=0, description="Total tokens used across all agents")
    uptime_seconds: float = Field(..., description="System uptime")
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def create_standard_request(
    task_type: TaskType,
    instruction: str,
    context: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> AgentRequest:
    """Helper function to create standardized requests"""
    return AgentRequest(
        task_type=task_type,
        instruction=instruction,
        context=context,
        parameters=parameters or {},
    )


def create_success_response(
    message: str,
    file_content: FileContent | None = None,
    changes_made: list[str] = None,
    tokens_used: int | None = None,
    processing_time: float | None = None,
) -> AgentResponse:
    """Helper function to create success responses"""
    return AgentResponse(
        status=ResponseStatus.SUCCESS,
        message=message,
        file_content=file_content,
        changes_made=changes_made or [],
        tokens_used=tokens_used,
        processing_time=processing_time,
    )


def create_error_response(
    message: str,
    warnings: list[str] = None,
) -> AgentResponse:
    """Helper function to create error responses"""
    return AgentResponse(
        status=ResponseStatus.ERROR,
        message=message,
        warnings=warnings or [],
    )


# Example usage and validation functions
def validate_agent_request(request_data: dict[str, Any]) -> AgentRequest:
    """Validate and parse agent request"""
    return AgentRequest.model_validate(request_data)


def validate_agent_response(response_data: dict[str, Any]) -> AgentResponse:
    """Validate and parse agent response"""
    return AgentResponse.model_validate(response_data)
