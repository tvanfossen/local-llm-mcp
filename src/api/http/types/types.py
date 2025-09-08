"""HTTP Types - Shared HTTP Types and Data Structures

Responsibilities:
- Define shared data structures for HTTP components
- Provide type definitions for route handlers
- Ensure consistent typing across HTTP modules
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class RouteHandlers:
    """Container for route handlers."""

    root_handler: callable
    health_handler: callable
    mcp_handler_wrapper: callable
    legacy_handler_wrapper: callable
    api_endpoints: Any  # Avoid circular import
    orchestrator_api: Any  # Avoid circular import
    websocket_endpoint: callable
