# File: ~/Projects/local-llm-mcp/src/mcp/auth/manager/manager.py
"""MCP Authentication Integration Module

Responsibilities:
- Validate orchestrator session tokens for MCP requests
- Bridge SecurityManager with MCP protocol
- Handle authentication errors and responses
- Session validation and management for MCP operations
"""

import logging
from typing import Any

from src.core.security.manager.manager import SecurityManager

logger = logging.getLogger(__name__)


class MCPAuthenticator:
    """Handles authentication for MCP requests using SecurityManager"""

    def __init__(self, security_manager: SecurityManager | None = None):
        self.security_manager = security_manager

    async def authenticate_request(self, auth_token: str | None) -> dict[str, Any]:
        """Authenticate MCP request with token

        Returns:
            dict: {"authenticated": bool, "error": str | None, "user_context": dict | None}
        """
        # Check for development mode scenarios
        dev_result = self._check_dev_authentication(auth_token)
        if dev_result is not None:
            return dev_result

        # Validate the provided token
        valid, session = self.security_manager.validate_session(auth_token)

        if valid:
            logger.debug(f"MCP authentication successful for client: {session.get('client_name', 'unknown')}")
            return {"authenticated": True, "error": None, "session": session, "user_context": session}
        else:
            logger.warning("MCP authentication failed - invalid or expired token")
            return {
                "authenticated": False,
                "error": "Invalid or expired authentication token",
                "session": None,
                "user_context": None,
            }

    def _check_dev_authentication(self, auth_token: str | None) -> dict[str, Any] | None:
        """Check for development mode authentication scenarios"""
        # Development mode - if no security manager, allow all
        if not self.security_manager:
            logger.warning("No SecurityManager configured - allowing unauthenticated MCP request")
            return {"authenticated": True, "error": None, "user_context": {"source": "no_security_manager"}}

        # No token provided
        if not auth_token:
            logger.debug("No auth token provided, checking for active sessions")
            has_sessions = bool(self.security_manager.active_sessions)
            if has_sessions:
                logger.info("Active sessions found - allowing MCP request")
            return {
                "authenticated": has_sessions,
                "error": None if has_sessions else "No authentication token provided",
                "user_context": {"source": "active_session"} if has_sessions else None,
            }

        return None

    def validate_request_auth(self, method: str, auth_token: str | None) -> dict[str, Any]:
        """Validate authentication for MCP request

        Returns:
            dict: {"valid": bool, "error": str | None, "session": dict | None}
        """
        # Skip auth for initialization
        if method in ["initialize"]:
            return {"valid": True, "error": None, "session": None}

        # Check for development scenarios
        dev_result = self._check_validation_scenarios(auth_token)
        if dev_result is not None:
            return dev_result

        # Validate the token
        valid, session = self.security_manager.validate_session(auth_token)
        return {
            "valid": valid,
            "error": None if valid else "Invalid or expired authentication token",
            "session": session,
        }

    def _check_validation_scenarios(self, auth_token: str | None) -> dict[str, Any] | None:
        """Check for development mode validation scenarios"""
        # Development mode - if no security manager, allow all
        if not self.security_manager:
            logger.warning("No SecurityManager configured - allowing unauthenticated MCP request")
            return {"valid": True, "error": None, "session": {"source": "no_security_manager"}}

        # No token provided - check for active sessions
        if not auth_token:
            has_sessions = bool(self.security_manager.active_sessions)
            if has_sessions:
                logger.info("Active sessions found - allowing MCP request")
                return {"valid": True, "error": None, "session": {"source": "active_session"}}
            else:
                return {"valid": False, "error": "Authentication required", "session": None}

        return None

    def create_auth_error_response(self, request_id: Any, auth_result: dict[str, Any]) -> dict[str, Any]:
        """Create JSON-RPC error response for authentication failure"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32002,
                "message": "Authentication required",
                "data": auth_result.get("error", "Authentication failed"),
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
