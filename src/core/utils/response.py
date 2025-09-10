"""MCP Response Utilities

Centralized functions for creating standardized MCP response formats.
Replaces the duplicate _create_success, _create_error, and _handle_exception
functions scattered throughout the codebase.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def create_success(text: str) -> dict[str, Any]:
    """Create success response format
    
    Args:
        text: Success message text
        
    Returns:
        Standardized MCP success response dictionary
    """
    return {"content": [{"type": "text", "text": text}], "isError": False}


def create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format
    
    Args:
        title: Error title/category
        message: Detailed error message
        
    Returns:
        Standardized MCP error response dictionary
    """
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


def handle_exception(e: Exception, context: str) -> dict[str, Any]:
    """Handle exceptions with consistent error format
    
    Args:
        e: The exception that occurred
        context: Context description for the error
        
    Returns:
        Standardized MCP error response dictionary
    """
    logger.error(f"{context} error: {e}")
    return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}


def create_success_with_data(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create successful MCP response with optional JSON data
    
    Args:
        message: Success message text
        data: Optional dictionary data to include as JSON
        
    Returns:
        Standardized MCP success response with optional data
    """
    content = [{"type": "text", "text": message}]
    if data:
        content.append({"type": "text", "text": f"```json\n{json.dumps(data, indent=2)}\n```"})
    return {"content": content, "isError": False}