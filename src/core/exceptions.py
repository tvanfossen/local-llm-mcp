"""Custom Exception Types for Agent System

Following AGENT_WORKPLAN requirements for explicit error handling.
"""


class AgentSystemError(Exception):
    """Base exception for agent system errors"""
    def __init__(self, message: str, error_type: str = None, context: dict = None):
        super().__init__(message)
        self.error_type = error_type or self.__class__.__name__
        self.context = context or {}


class AgentNotFound(AgentSystemError):
    """Raised when agent ID doesn't exist"""
    def __init__(self, agent_id: str):
        super().__init__(f"Agent {agent_id} not found", "agent_not_found", {"agent_id": agent_id})


class TaskQueueFull(AgentSystemError):
    """Raised when task queue at capacity"""
    def __init__(self, max_capacity: int):
        super().__init__(f"Task queue at maximum capacity: {max_capacity}", "task_queue_full", {"max_capacity": max_capacity})


class MaxDepthExceeded(AgentSystemError):
    """Raised when task nesting too deep"""
    def __init__(self, current_depth: int, max_depth: int):
        super().__init__(
            f"Maximum nesting depth {max_depth} exceeded (current: {current_depth})",
            "max_depth_exceeded",
            {"current_depth": current_depth, "max_depth": max_depth}
        )


class MetadataInvalid(AgentSystemError):
    """Raised when JSON metadata malformed"""
    def __init__(self, validation_error: str, metadata_path: str = None):
        super().__init__(
            f"Invalid metadata: {validation_error}",
            "metadata_invalid",
            {"validation_error": validation_error, "metadata_path": metadata_path}
        )


class ToolNotAvailable(AgentSystemError):
    """Raised when requested tool not registered"""
    def __init__(self, tool_name: str, available_tools: list = None):
        super().__init__(
            f"Tool '{tool_name}' not available",
            "tool_not_available",
            {"tool_name": tool_name, "available_tools": available_tools or []}
        )


class ModelNotLoaded(AgentSystemError):
    """Raised when LLM model not loaded"""
    def __init__(self, model_path: str = None):
        super().__init__(
            "Language model not loaded",
            "model_not_loaded",
            {"model_path": model_path}
        )


class ToolCallFailed(AgentSystemError):
    """Raised when tool execution fails"""
    def __init__(self, tool_name: str, error_details: str):
        super().__init__(
            f"Tool call failed: {tool_name} - {error_details}",
            "tool_call_failed",
            {"tool_name": tool_name, "error_details": error_details}
        )


class ValidationFailed(AgentSystemError):
    """Raised when code validation fails"""
    def __init__(self, validation_type: str, error_details: str, file_paths: list = None):
        super().__init__(
            f"Validation failed: {validation_type} - {error_details}",
            "validation_failed",
            {"validation_type": validation_type, "error_details": error_details, "file_paths": file_paths or []}
        )


class OperationNotImplemented(AgentSystemError):
    """Raised for operations that are not yet implemented"""
    def __init__(self, operation_name: str, component: str = None):
        super().__init__(
            f"Operation {operation_name} not implemented",
            "not_implemented",
            {"operation": operation_name, "component": component}
        )


def create_error_response(error: AgentSystemError) -> dict:
    """Create standardized error response format"""
    return {
        "success": False,
        "error": str(error),
        "error_type": error.error_type,
        "metadata": error.context
    }