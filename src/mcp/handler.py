# File: ~/Projects/local-llm-mcp/src/mcp/handler.py
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

from src.core.agents.registry.registry import AgentRegistry
from src.core.llm.manager.manager import LLMManager
from src.core.security.manager.manager import SecurityManager
from src.core.utils.utils import handle_exception, create_mcp_response
from src.mcp.auth.manager.manager import MCPAuthenticator
from src.mcp.tools.executor.executor import ConsolidatedToolExecutor

logger = logging.getLogger(__name__)


class MCPSession:
    """MCP session state management"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.capabilities = {}
        self.tools_available = []
        self.authenticated = False
        self.user_context = None

    def mark_initialized(self, capabilities: dict):
        """Mark session as initialized with capabilities"""
        self.initialized = True
        self.capabilities = capabilities

    def authenticate(self, user_context: dict):
        """Authenticate session with user context"""
        self.authenticated = True
        self.user_context = user_context

    def is_ready(self) -> bool:
        """Check if session is ready for tool execution"""
        return self.initialized and self.authenticated


class MCPHandler:
    """Main MCP protocol handler with authentication bridge"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager, security_manager: SecurityManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.security_manager = security_manager

        # Initialize components
        self.authenticator = MCPAuthenticator(security_manager)
        self.tool_executor = ConsolidatedToolExecutor(agent_registry, llm_manager)

        # Session management
        self.sessions: dict[str, MCPSession] = {}

    async def handle_jsonrpc_request(
        self, request: dict[str, Any], session_id: str = None, auth_token: str = None
    ) -> dict[str, Any]:
        """Handle JSON-RPC 2.0 request with authentication bridge"""
        try:
            # Validate JSON-RPC format
            if not self._validate_jsonrpc_format(request):
                return self._create_parse_error("Invalid JSON-RPC format")

            # Get or create session
            session = self._get_or_create_session(session_id)
            request_id = request.get("id")
            method = request.get("method")

            logger.info(f"MCP {method} request (session: {session.session_id})")

            # Route to appropriate handler
            if method == "initialize":
                return await self._handle_initialize(request, session)
            elif method == "tools/list":
                return await self._handle_tools_list(request, session, auth_token)
            elif method == "tools/call":
                return await self._handle_tools_call(request, session, auth_token)
            elif method == "notifications/initialized":
                return await self._handle_initialized_notification(request, session)
            else:
                return self._create_method_error(request_id, method)

        except Exception as e:
            logger.error(f"MCP handler error: {e}")
            # Use shared utility for consistent error handling
            error_response = handle_exception(e, "MCP Handler")
            return self._create_internal_error(request.get("id"), error_response.get("content", [{}])[0].get("text", str(e)))

    async def _handle_initialize(self, request: dict, session: MCPSession) -> dict:
        """Handle MCP initialize request"""
        request_id = request.get("id")

        # Mark session as initialized with simplified capabilities for 4-tool system
        capabilities = {
            "tools": {"listChanged": False},
            "consolidatedTools": {
                "count": 4,
                "tools": self.get_available_tools()
            }
        }
        session.mark_initialized(capabilities)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": capabilities,
                "serverInfo": {
                    "name": "Consolidated LLM MCP Server", 
                    "version": "2.0.0",
                    "description": "4-tool consolidated MCP system"
                },
                "_session_id": session.session_id,
            },
        }

    async def _handle_tools_list(self, request: dict, session: MCPSession, auth_token: str) -> dict:
        """Handle tools/list request with authentication"""
        request_id = request.get("id")

        # Authenticate request
        auth_result = await self.authenticator.authenticate_request(auth_token)
        if not auth_result["authenticated"]:
            return self._create_auth_error(request_id, auth_result["error"])

        # Mark session as authenticated
        session.authenticate(auth_result.get("user_context", {}))

        # Get available tools
        tools = await self.tool_executor.get_available_tools()

        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    async def _handle_tools_call(self, request: dict, session: MCPSession, auth_token: str) -> dict:
        """Handle tools/call request with authentication"""
        request_id = request.get("id")
        params = request.get("params", {})

        # Authenticate request
        auth_result = await self.authenticator.authenticate_request(auth_token)
        if not auth_result["authenticated"]:
            return self._create_auth_error(request_id, auth_result["error"])

        # Execute tool
        try:
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Execute using consolidated tool executor
            result = await self.tool_executor.execute_tool(tool_name, arguments)

            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return self._create_tool_error(request_id, str(e))

    async def _handle_initialized_notification(self, request: dict, session: MCPSession) -> None:
        """Handle initialized notification"""
        logger.info(f"MCP session {session.session_id} fully initialized")
        return None  # Notifications don't return responses

    def _get_or_create_session(self, session_id: str = None) -> MCPSession:
        """Get existing session or create new one"""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        new_session_id = session_id or str(uuid.uuid4())[:8]
        session = MCPSession(new_session_id)
        self.sessions[new_session_id] = session
        return session

    def _validate_jsonrpc_format(self, request: dict) -> bool:
        """Validate JSON-RPC 2.0 format"""
        return isinstance(request, dict) and request.get("jsonrpc") == "2.0" and "method" in request

    def _create_parse_error(self, message: str) -> dict:
        """Create JSON-RPC parse error"""
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error", "data": message}}

    def _create_method_error(self, request_id: Any, method: str) -> dict:
        """Create method not found error"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found", "data": f"Method '{method}' is not supported"},
        }

    def _create_auth_error(self, request_id: Any, message: str) -> dict:
        """Create authentication error"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32002, "message": "Authentication failed", "data": message},
        }

    def _create_tool_error(self, request_id: Any, message: str) -> dict:
        """Create tool execution error"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": "Tool execution failed", "data": message},
        }

    def _create_internal_error(self, request_id: Any, message: str) -> dict:
        """Create internal error"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": "Internal error", "data": message},
        }

    def get_session_stats(self) -> dict:
        """Get statistics about active sessions"""
        return {
            "total_sessions": len(self.sessions),
            "authenticated_sessions": sum(1 for s in self.sessions.values() if s.authenticated),
            "initialized_sessions": sum(1 for s in self.sessions.values() if s.initialized),
        }
    
    def cleanup_inactive_sessions(self, max_sessions: int = 100) -> int:
        """Clean up inactive sessions to maintain limits"""
        if len(self.sessions) <= max_sessions:
            return 0
        
        # Remove oldest sessions first (simple FIFO cleanup)
        sessions_to_remove = len(self.sessions) - max_sessions
        session_ids = list(self.sessions.keys())[:sessions_to_remove]
        
        for session_id in session_ids:
            del self.sessions[session_id]
        
        logger.info(f"Cleaned up {sessions_to_remove} inactive sessions")
        return sessions_to_remove
    
    def get_available_tools(self) -> list[str]:
        """Get list of available tool names for the consolidated system"""
        # Return the 4 core tools
        return ["local_model", "git_operations", "workspace", "validation"]
