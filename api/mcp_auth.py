# File: ~/Projects/local-llm-mcp/api/mcp_auth.py
"""MCP Authentication Integration Module

Responsibilities:
- Validate orchestrator session tokens for MCP requests
- Bridge SecurityManager with MCP protocol
- Handle authentication errors and responses
- Session validation and management for MCP operations
"""

import logging
from typing import Any

from core.security import SecurityManager

logger = logging.getLogger(__name__)


class MCPAuthenticator:
    """Handles authentication for MCP requests using SecurityManager"""

    def __init__(self, security_manager: SecurityManager | None = None):
        self.security_manager = security_manager

    def validate_request_auth(self, method: str, auth_token: str | None) -> dict[str, Any]:
        """Validate authentication for MCP request

        Returns:
            dict: {"valid": bool, "error": str | None, "session": dict | None}
        """
        # Skip auth for initialization and tools listing
        if method in ["initialize", "tools/list"]:
            return {"valid": True, "error": None, "session": None}

        # If no security manager, allow all requests (development mode)
        if not self.security_manager:
            logger.warning("No SecurityManager configured - allowing unauthenticated MCP request")
            return {"valid": True, "error": None, "session": None}

        # Validate authentication token
        return self._validate_token(auth_token)

    def _validate_token(self, auth_token: str | None) -> dict[str, Any]:
        """Validate authentication token using SecurityManager"""
        if not auth_token:
            return {
                "valid": False,
                "error": "No authentication token provided",
                "session": None,
            }

        # Extract token from Bearer format
        token = auth_token[7:] if auth_token.startswith("Bearer ") else auth_token

        # Validate session using SecurityManager
        valid, session = self.security_manager.validate_session(token)

        if valid:
            logger.debug(f"MCP authentication successful for client: {session.get('client_name', 'unknown')}")
            return {"valid": True, "error": None, "session": session}
        else:
            logger.warning("MCP authentication failed - invalid or expired token")
            return {
                "valid": False,
                "error": "Invalid or expired authentication token",
                "session": None,
            }

    def create_auth_error_response(self, request_id: Any, auth_result: dict[str, Any]) -> dict[str, Any]:
        """Create JSON-RPC error response for authentication failure"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32002,
                "message": "Authentication required",
                "data": auth_result["error"],
            },
        }

    def get_security_status(self) -> dict[str, Any]:
        """Get security status for system information"""
        if not self.security_manager:
            return {
                "enabled": False,
                "status": "No SecurityManager configured (development mode)",
                "authorized_keys": 0,
                "active_sessions": 0,
            }

        security_status = self.security_manager.get_security_status()
        return {
            "enabled": True,
            "status": "SecurityManager active",
            "authorized_keys": security_status["authorized_keys_count"],
            "active_sessions": security_status["active_sessions"],
            "recent_deployments": security_status["recent_deployments"],
        }

    def log_authenticated_operation(self, method: str, tool_name: str | None, session: dict | None):
        """Log authenticated MCP operation for audit purposes"""
        if session:
            client_name = session.get("client_name", "unknown")
            logger.info(f"Authenticated MCP operation: {method} ({tool_name}) by {client_name}")
        else:
            logger.info(f"Unauthenticated MCP operation: {method} ({tool_name}) - development mode")
