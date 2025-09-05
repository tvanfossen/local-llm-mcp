# File: ~/Projects/local-llm-mcp/api/mcp_handler.py
"""MCP Protocol Handler with Authentication Integration

Responsibilities:
- Handle JSON-RPC 2.0 protocol requirements
- Implement MCP initialization handshake
- Handle tool definitions and validation
- Request/response mapping between MCP and internal systems
- Session management and state tracking
- Integration with authentication system
"""

import logging
import uuid
from typing import Any

from api.mcp_auth import MCPAuthenticator
from api.mcp_tools import MCPToolExecutor
from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from core.security import SecurityManager

logger = logging.getLogger(__name__)


class MCPSession:
    """MCP session state management"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.protocol_version = "2024-11-05"
        self.capabilities = {}
        self.client_info = {}
        self.initialized = False


class MCPHandler:
    """MCP protocol handler with authentication integration"""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_manager: LLMManager,
        security_manager: SecurityManager = None,
    ):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

        # Initialize authentication and tool execution
        self.authenticator = MCPAuthenticator(security_manager)
        self.tool_executor = MCPToolExecutor(agent_registry, llm_manager, self.authenticator)

        # Session management
        self.sessions: dict[str, MCPSession] = {}

        # MCP server info
        self.server_info = {
            "name": "local-llm-agents",
            "version": "1.0.0",
        }

        # Define server capabilities
        self.server_capabilities = {
            "tools": {"listChanged": True},
            "resources": {},
            "prompts": {},
        }

    async def handle_jsonrpc_request(
        self,
        request_data: dict[str, Any],
        session_id: str | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """Handle JSON-RPC 2.0 request with authentication"""
        try:
            # Validate authentication for tool calls
            method = request_data.get("method")
            auth_result = self.authenticator.validate_request_auth(method, auth_token)

            if not auth_result["valid"]:
                return self.authenticator.create_auth_error_response(request_data.get("id"), auth_result)

            # Process the request
            result = await self._process_jsonrpc_request(request_data, session_id, auth_result["session"])
            return result

        except Exception as e:
            logger.error(f"JSON-RPC request handling failed: {e}")
            return self._create_error_response(
                request_data.get("id"),
                -32603,
                "Internal error",
                str(e),
            )

    async def _process_jsonrpc_request(
        self,
        request_data: dict[str, Any],
        session_id: str | None,
        auth_session: dict | None,
    ) -> dict[str, Any]:
        """Process JSON-RPC request with validation"""
        if not self._validate_jsonrpc_request(request_data):
            return self._create_error_response(
                None,
                -32600,
                "Invalid Request",
                "Invalid JSON-RPC 2.0 format",
            )

        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        logger.info(f"Handling JSON-RPC method: {method}")

        # Handle notifications (no response required)
        if request_id is None:
            await self._handle_notification(method, params, session_id)
            return None

        # Dispatch to appropriate handler
        return await self._dispatch_request_method(method, request_id, params, session_id, auth_session)

    async def _dispatch_request_method(
        self,
        method: str,
        request_id: Any,
        params: dict[str, Any],
        session_id: str | None,
        auth_session: dict | None,
    ) -> dict[str, Any]:
        """Dispatch request to appropriate method handler"""
        method_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        handler = method_handlers.get(method)
        if handler:
            if method == "tools/call":
                return await handler(request_id, params, session_id, auth_session)
            else:
                return await handler(request_id, params, session_id)

        return self._create_error_response(
            request_id,
            -32601,
            "Method not found",
            f"Unknown method: {method}",
        )

    def _validate_jsonrpc_request(self, request: dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 request format"""
        return (
            isinstance(request, dict)
            and request.get("jsonrpc") == "2.0"
            and "method" in request
            and isinstance(request["method"], str)
        )

    async def _handle_initialize(
        self, request_id: Any, params: dict[str, Any], session_id: str | None
    ) -> dict[str, Any]:
        """Handle MCP initialize request"""
        try:
            client_version = params.get("protocolVersion", "2024-11-05")
            client_capabilities = params.get("capabilities", {})
            client_info = params.get("clientInfo", {})

            if not session_id:
                session_id = str(uuid.uuid4())

            session = MCPSession(session_id)
            session.protocol_version = client_version
            session.capabilities = client_capabilities
            session.client_info = client_info

            self.sessions[session_id] = session

            logger.info(f"MCP session initialized: {session_id} for client: {client_info.get('name', 'unknown')}")

            response = self._create_success_response(
                request_id,
                {
                    "protocolVersion": session.protocol_version,
                    "serverInfo": self.server_info,
                    "capabilities": self.server_capabilities,
                },
            )

            response["_session_id"] = session_id
            return response

        except Exception as e:
            return self._create_error_response(request_id, -32603, "Initialization failed", str(e))

    async def _handle_tools_list(
        self, request_id: Any, params: dict[str, Any], session_id: str | None
    ) -> dict[str, Any]:
        """Handle tools/list request"""
        try:
            tools = self.tool_executor.get_tool_definitions()
            return self._create_success_response(request_id, {"tools": tools})
        except Exception as e:
            return self._create_error_response(request_id, -32603, "Failed to list tools", str(e))

    async def _handle_tools_call(
        self,
        request_id: Any,
        params: dict[str, Any],
        session_id: str | None,
        auth_session: dict | None,
    ) -> dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        if not tool_name:
            return self._create_error_response(request_id, -32602, "Invalid params", "Missing tool name")

        try:
            tool_args = params.get("arguments", {})

            # Log authenticated operation
            self.authenticator.log_authenticated_operation("tools/call", tool_name, auth_session)

            # Execute tool
            result = await self.tool_executor.execute_tool(tool_name, tool_args)

            return self._create_success_response(
                request_id,
                {
                    "content": result["content"],
                    "isError": result.get("isError", False),
                },
            )

        except Exception as e:
            return self._create_error_response(request_id, -32603, "Tool execution failed", str(e))

    async def _handle_notification(self, method: str, params: dict[str, Any], session_id: str | None):
        """Handle JSON-RPC notification (no response required)"""
        try:
            if method in ["notifications/initialized", "initialized"]:
                if session_id and session_id in self.sessions:
                    self.sessions[session_id].initialized = True
                    logger.info(f"MCP session {session_id} fully initialized")
            else:
                logger.info(f"Received notification: {method}")
        except Exception as e:
            logger.error(f"Notification handling failed: {e}")

    def _create_success_response(self, request_id: Any, result: Any) -> dict[str, Any]:
        """Create JSON-RPC 2.0 success response"""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _create_error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        """Create JSON-RPC 2.0 error response"""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def get_session(self, session_id: str) -> MCPSession | None:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def cleanup_session(self, session_id: str):
        """Clean up session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up MCP session: {session_id}")

    def get_security_status(self) -> dict[str, Any]:
        """Get security status for system reporting"""
        return self.authenticator.get_security_status()
