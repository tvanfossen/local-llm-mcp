# File: ~/Projects/local-llm-mcp/schemas/agent_schemas.py
"""
Standardized JSON schemas for agent communications
Ensures consistent structure across all agent interactions
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

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
    context: Optional[str] = Field(None, description="Additional context for the task")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Task-specific parameters")
    expected_output: Optional[str] = Field(None, description="Description of expected output format")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Request timestamp")

class FileContent(BaseModel):
    """File content structure"""
    filename: str = Field(..., description="Name of the file")
    content: str = Field(..., description="Complete file content")
    language: Optional[str] = Field(None, description="Programming language or file type")
    encoding: str = Field(default="utf-8", description="File encoding")
    line_count: Optional[int] = Field(None, description="Number of lines in file")

class AgentResponse(BaseModel):
    """Standardized response format from agents"""
    status: ResponseStatus = Field(..., description="Response status")
    message: str = Field(..., description="Human-readable message")
    file_content: Optional[FileContent] = Field(None, description="File content if applicable")
    changes_made: List[str] = Field(default_factory=list, description="List of changes made")
    warnings: List[str] = Field(default_factory=list, description="Any warnings or notes")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used in generation")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentState(BaseModel):
    """Agent's current state in JSON format"""
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    managed_file: str = Field(..., description="Single file managed by this agent")
    system_prompt: str = Field(..., description="Agent's system prompt")
    context: str = Field(default="", description="Current context/understanding")
    last_task: Optional[TaskType] = Field(None, description="Last task performed")
    last_activity: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_interactions: int = Field(default=0, description="Total number of interactions")
    success_rate: float = Field(default=1.0, description="Success rate of tasks (0.0-1.0)")

class ConversationEntry(BaseModel):
    """Single conversation entry with standardized format"""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request: AgentRequest = Field(..., description="Original request")
    response: AgentResponse = Field(..., description="Agent response")
    session_id: Optional[str] = Field(None, description="Session identifier")

class AgentCapabilities(BaseModel):
    """Define what an agent can do"""
    supported_tasks: List[TaskType] = Field(default_factory=list)
    file_extensions: List[str] = Field(default_factory=list, description="File extensions this agent handles")
    programming_languages: List[str] = Field(default_factory=list)
    specializations: List[str] = Field(default_factory=list, description="Areas of expertise")
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
    context: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> AgentRequest:
    """Helper function to create standardized requests"""
    return AgentRequest(
        task_type=task_type,
        instruction=instruction,
        context=context,
        parameters=parameters or {}
    )

def create_success_response(
    message: str,
    file_content: Optional[FileContent] = None,
    changes_made: List[str] = None,
    tokens_used: Optional[int] = None,
    processing_time: Optional[float] = None
) -> AgentResponse:
    """Helper function to create success responses"""
    return AgentResponse(
        status=ResponseStatus.SUCCESS,
        message=message,
        file_content=file_content,
        changes_made=changes_made or [],
        tokens_used=tokens_used,
        processing_time=processing_time
    )

def create_error_response(
    message: str,
    warnings: List[str] = None
) -> AgentResponse:
    """Helper function to create error responses"""
    return AgentResponse(
        status=ResponseStatus.ERROR,
        message=message,
        warnings=warnings or []
    )

# Example usage and validation functions
def validate_agent_request(request_data: Dict[str, Any]) -> AgentRequest:
    """Validate and parse agent request"""
    return AgentRequest.model_validate(request_data)

def validate_agent_response(response_data: Dict[str, Any]) -> AgentResponse:
    """Validate and parse agent response"""
    return AgentResponse.model_validate(response_data)