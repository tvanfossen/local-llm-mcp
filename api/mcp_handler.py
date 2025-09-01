# File: ~/Projects/local-llm-mcp/api/mcp_handler.py
"""MCP Protocol Handler with proper JSON-RPC 2.0 implementation

Responsibilities:
- Handle JSON-RPC 2.0 protocol requirements
- Implement MCP initialization handshake
- Handle tool definitions and validation
- Request/response mapping between MCP and internal systems
- Session management and state tracking
"""

import logging
import uuid
from typing import Any

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import ResponseStatus, TaskType, create_standard_request

logger = logging.getLogger(__name__)


class MCPSession:
    """MCP session state management"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.protocol_version = "2024-11-05"  # Using stable version
        self.capabilities = {}
        self.client_info = {}
        self.initialized = False


class MCPHandler:
    """Proper MCP protocol handler implementing JSON-RPC 2.0 and MCP specification"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

        # Session management
        self.sessions: dict[str, MCPSession] = {}

        # MCP server info
        self.server_info = {
            "name": "local-llm-agents",
            "version": "1.0.0",
        }

        # Define server capabilities
        self.server_capabilities = {
            "tools": {
                "listChanged": True,
            },
            "resources": {},
            "prompts": {},
        }

        # Define available tools
        self.tools = self._define_tools()

    def _define_tools(self) -> list[dict[str, Any]]:
        """Define MCP tools available to clients - split into sections to reduce length"""
        tools = []

        # Core agent management tools
        tools.extend(self._define_agent_tools())

        # Agent interaction tools
        tools.extend(self._define_interaction_tools())

        # File management tools
        tools.extend(self._define_file_tools())

        # System and orchestration tools
        tools.extend(self._define_system_tools())

        return tools

    def _define_agent_tools(self) -> list[dict[str, Any]]:
        """Define agent management tools"""
        return [
            {
                "name": "create_agent",
                "description": "Create a new agent to handle a specific file (ONE AGENT PER FILE ONLY)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Human-readable agent name",
                        },
                        "description": {
                            "type": "string",
                            "description": "What this agent does and its responsibilities",
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "LLM system prompt for this agent",
                        },
                        "managed_file": {
                            "type": "string",
                            "description": "Single file this agent manages (e.g., 'schema.sql', 'app.py')",
                        },
                        "initial_context": {
                            "type": "string",
                            "description": "Initial context or state for the agent (optional)",
                        },
                    },
                    "required": ["name", "description", "system_prompt", "managed_file"],
                },
            },
            {
                "name": "list_agents",
                "description": "List all active agents and their managed files",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_agent_info",
                "description": "Get detailed information about a specific agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to query",
                        },
                    },
                    "required": ["agent_id"],
                },
            },
            {
                "name": "delete_agent",
                "description": "Delete an agent and free up its managed file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to delete",
                        },
                    },
                    "required": ["agent_id"],
                },
            },
        ]

    def _define_interaction_tools(self) -> list[dict[str, Any]]:
        """Define agent interaction tools"""
        return [
            {
                "name": "chat_with_agent",
                "description": "Send a message to a specific agent in their context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to chat with",
                        },
                        "message": {
                            "type": "string",
                            "description": "Message to send to the agent",
                        },
                        "task_type": {
                            "type": "string",
                            "enum": [
                                "create",
                                "update",
                                "analyze",
                                "refactor",
                                "debug",
                                "document",
                                "test",
                            ],
                            "default": "update",
                            "description": "Type of task to perform",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context for the task (optional)",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Additional parameters for the task (optional)",
                        },
                    },
                    "required": ["agent_id", "message"],
                },
            },
        ]

    def _define_file_tools(self) -> list[dict[str, Any]]:
        """Define file management tools"""
        return [
            {
                "name": "agent_update_file",
                "description": "Have an agent update its managed file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID",
                        },
                        "instruction": {
                            "type": "string",
                            "description": "Instructions for updating the file",
                        },
                        "current_content": {
                            "type": "string",
                            "description": "Current file content (optional, agent can read it)",
                        },
                    },
                    "required": ["agent_id", "instruction"],
                },
            },
            {
                "name": "get_agent_file",
                "description": "Get the current content of a file managed by an agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID",
                        },
                    },
                    "required": ["agent_id"],
                },
            },
            {
                "name": "agent_write_file",
                "description": "Have an agent write content to its managed file with validation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID that will write the file",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the agent's managed file",
                        },
                        "validation_required": {
                            "type": "boolean",
                            "default": False,
                            "description": "Whether to validate the file after writing",
                        },
                    },
                    "required": ["agent_id", "content"],
                },
            },
            {
                "name": "validate_agent_file",
                "description": "Validate a file managed by an agent (syntax, formatting, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID whose file to validate",
                        },
                        "validation_type": {
                            "type": "string",
                            "enum": ["syntax", "formatting", "structure", "all"],
                            "default": "syntax",
                            "description": "Type of validation to perform",
                        },
                    },
                    "required": ["agent_id"],
                },
            },
        ]

    def _define_system_tools(self) -> list[dict[str, Any]]:
        """Define system and orchestration tools"""
        return [
            {
                "name": "system_status",
                "description": "Get system status including model and agent information",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "orchestrate_agents",
                "description": "Coordinate multiple agents to work on related files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agent IDs to coordinate",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "Overall task description for coordination",
                        },
                        "wait_for_completion": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to wait for all agents to complete",
                        },
                    },
                    "required": ["agent_ids", "task_description"],
                },
            },
        ]

    async def handle_jsonrpc_request(
        self, request_data: dict[str, Any], session_id: str | None = None
    ) -> dict[str, Any]:
        """Handle JSON-RPC 2.0 request - fixed to use single return"""
        # Validate JSON-RPC 2.0 format
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

        try:
            # Handle notifications (no response required)
            if request_id is None:
                await self._handle_notification(method, params, session_id)
                return None

            # Dispatch to appropriate handler
            response = await self._dispatch_request_method(method, request_id, params, session_id)
            return response

        except Exception as e:
            logger.error(f"JSON-RPC request handling failed: {e}")
            return self._create_error_response(
                request_data.get("id"),
                -32603,
                "Internal error",
                str(e),
            )

    async def _dispatch_request_method(
        self, method: str, request_id: Any, params: dict[str, Any], session_id: str | None
    ) -> dict[str, Any]:
        """Dispatch request to appropriate method handler"""
        method_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        handler = method_handlers.get(method)
        if handler:
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
            # Extract client info
            client_version = params.get("protocolVersion", "2024-11-05")
            client_capabilities = params.get("capabilities", {})
            client_info = params.get("clientInfo", {})

            # Create or update session
            if not session_id:
                session_id = str(uuid.uuid4())

            session = MCPSession(session_id)
            session.protocol_version = client_version
            session.capabilities = client_capabilities
            session.client_info = client_info

            self.sessions[session_id] = session

            logger.info(
                f"MCP session initialized: {session_id} for client: {client_info.get('name', 'unknown')}"
            )

            # Return initialization response
            response = self._create_success_response(
                request_id,
                {
                    "protocolVersion": session.protocol_version,
                    "serverInfo": self.server_info,
                    "capabilities": self.server_capabilities,
                },
            )

            # Add session ID to response headers (for HTTP transport)
            response["_session_id"] = session_id

            return response

        except Exception as e:
            return self._create_error_response(
                request_id,
                -32603,
                "Initialization failed",
                str(e),
            )

    async def _handle_tools_list(
        self, request_id: Any, params: dict[str, Any], session_id: str | None
    ) -> dict[str, Any]:
        """Handle tools/list request - simplified"""
        # Validate session if provided
        session_error = self._validate_session_if_provided(session_id, request_id)
        if session_error:
            return session_error

        try:
            return self._create_success_response(
                request_id,
                {
                    "tools": self.tools,
                },
            )

        except Exception as e:
            return self._create_error_response(
                request_id,
                -32603,
                "Failed to list tools",
                str(e),
            )

    def _validate_session_if_provided(self, session_id: str | None, request_id: Any):
        """Validate session if provided - returns error or None"""
        if session_id and session_id not in self.sessions:
            return self._create_error_response(
                request_id,
                -32002,
                "Session not found",
                f"Session {session_id} not found",
            )
        return None

    async def _handle_tools_call(
        self, request_id: Any, params: dict[str, Any], session_id: str | None
    ) -> dict[str, Any]:
        """Handle tools/call request - simplified validation"""
        # Validate session and parameters
        validation_error = self._validate_tool_call_request(session_id, params, request_id)
        if validation_error:
            return validation_error

        try:
            tool_name = params["name"]
            tool_args = params.get("arguments", {})

            # Execute tool
            result = await self._execute_tool(tool_name, tool_args)

            return self._create_success_response(
                request_id,
                {
                    "content": result["content"],
                    "isError": result.get("isError", False),
                },
            )

        except Exception as e:
            return self._create_error_response(
                request_id,
                -32603,
                "Tool execution failed",
                str(e),
            )

    def _validate_tool_call_request(self, session_id, params, request_id):
        """Validate tool call request - returns error or None"""
        # Validate session if provided
        session_error = self._validate_session_if_provided(session_id, request_id)
        if session_error:
            return session_error

        # Validate required parameters
        tool_name = params.get("name")
        if not tool_name:
            return self._create_error_response(
                request_id,
                -32602,
                "Invalid params",
                "Missing tool name",
            )

        return None

    async def _handle_notification(
        self, method: str, params: dict[str, Any], session_id: str | None
    ):
        """Handle JSON-RPC notification (no response required)"""
        try:
            if method == "notifications/initialized" or method == "initialized":
                if session_id and session_id in self.sessions:
                    self.sessions[session_id].initialized = True
                    logger.info(f"MCP session {session_id} fully initialized")
                else:
                    logger.warning("Received initialized notification without valid session")
            else:
                logger.info(f"Received notification: {method}")

        except Exception as e:
            logger.error(f"Notification handling failed: {e}")

    def _create_success_response(self, request_id: Any, result: Any) -> dict[str, Any]:
        """Create JSON-RPC 2.0 success response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _create_error_response(
        self, request_id: Any, code: int, message: str, data: Any = None
    ) -> dict[str, Any]:
        """Create JSON-RPC 2.0 error response"""
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }

    def get_session(self, session_id: str) -> MCPSession | None:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def cleanup_session(self, session_id: str):
        """Clean up session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up MCP session: {session_id}")

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute tool and return MCP-formatted result"""
        # Use dictionary dispatch to eliminate multiple returns
        tool_handlers = {
            "create_agent": self._tool_create_agent,
            "list_agents": lambda args: self._tool_list_agents(),
            "get_agent_info": self._tool_get_agent_info,
            "chat_with_agent": self._tool_chat_with_agent,
            "agent_update_file": self._tool_agent_update_file,
            "get_agent_file": self._tool_get_agent_file,
            "delete_agent": self._tool_delete_agent,
            "system_status": lambda args: self._tool_system_status(),
            "agent_write_file": self._tool_agent_write_file,
            "validate_agent_file": self._tool_validate_agent_file,
            "orchestrate_agents": self._tool_orchestrate_agents,
        }

        handler = tool_handlers.get(tool_name)
        if handler:
            return await handler(args)

        # Default error response for unknown tools
        return self._create_tool_error(f"Unknown tool: {tool_name}")

    def _create_tool_error(self, message: str) -> dict[str, Any]:
        """Create standardized tool error response"""
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"❌ **Error:** {message}",
                }
            ],
            "isError": True,
        }

    def _create_tool_success(self, text: str) -> dict[str, Any]:
        """Create standardized tool success response"""
        return {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }

    async def _tool_create_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle create_agent tool call"""
        try:
            success, agent, error = self.agent_registry.create_agent(
                name=args["name"],
                description=args["description"],
                system_prompt=args["system_prompt"],
                managed_file=args["managed_file"],
                initial_context=args.get("initial_context", ""),
            )

            if success:
                text = (
                    f"✅ **Agent Created Successfully**\n\n"
                    f"**ID:** {agent.state.agent_id}\n"
                    f"**Name:** {agent.state.name}\n"
                    f"**Description:** {agent.state.description}\n"
                    f"**Managed File:** {agent.state.managed_file}\n\n"
                    f"**JSON Schema:** Enabled\n"
                    f"**Rule Enforced:** One agent per file"
                )
                return self._create_tool_success(text)

            return self._create_tool_error(f"Agent Creation Failed: {error}")

        except Exception as e:
            return self._create_tool_error(str(e))

    async def _tool_list_agents(self) -> dict[str, Any]:
        """Handle list_agents tool call"""
        try:
            agents = self.agent_registry.list_agents()

            if not agents:
                text = (
                    "📝 **No agents created yet.**\n\n"
                    "**Rule:** One agent per file, one file per agent.\n"
                    "Use `create_agent` to create your first agent."
                )
                return self._create_tool_success(text)

            # Build agent list
            agent_list = ["🤖 **Active Agents:**\n"]
            for agent in agents:
                agent_list.append(f"• **{agent.state.agent_id}** - {agent.state.name}")
                agent_list.append(f"  📄 File: `{agent.state.managed_file}`")
                agent_list.append(f"  📝 {agent.state.description}")
                agent_list.append(f"  🔢 Interactions: {agent.state.total_interactions}")
                agent_list.append(f"  📊 Success Rate: {agent.state.success_rate:.2f}")
                agent_list.append(f"  🕒 Last Active: {agent.state.last_activity}\n")

            # Add file ownership map
            file_map = self.agent_registry.get_file_ownership_map()
            if file_map:
                agent_list.append("\n**📂 File Ownership Map:**")
                for filename, agent_id in file_map.items():
                    agent_name = self.agent_registry.get_agent(agent_id).state.name
                    agent_list.append(f"• `{filename}` → {agent_name} ({agent_id})")

            return self._create_tool_success("\n".join(agent_list))

        except Exception as e:
            return self._create_tool_error(f"Failed to list agents: {e!s}")

    async def _tool_chat_with_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle chat_with_agent tool call - simplified validation"""
        try:
            # Validate prerequisites
            validation_result = self._validate_chat_prerequisites(args)
            if validation_result["error"]:
                return self._create_tool_error(validation_result["message"])

            agent = validation_result["agent"]

            # Process the chat request
            chat_result = await self._execute_agent_chat(agent, args)
            return chat_result

        except Exception as e:
            return self._create_tool_error(f"Chat failed: {e!s}")

    def _validate_chat_prerequisites(self, args: dict[str, Any]) -> dict:
        """Validate chat prerequisites - simplified validation"""
        agent_id = args.get("agent_id")
        message = args.get("message")

        # Single validation check point
        if not agent_id or not message:
            return {"error": True, "message": "Missing agent_id or message"}

        # Check agent and model
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            return {"error": True, "message": f"Agent {agent_id} not found"}

        if not self.llm_manager.model_loaded:
            return {"error": True, "message": "Model not loaded"}

        return {"error": False, "agent": agent}

    async def _execute_agent_chat(self, agent, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the actual agent chat - simplified complexity"""
        # Create standardized request
        agent_request = create_standard_request(
            task_type=TaskType(args.get("task_type", "update")),
            instruction=args["message"],
            context=args.get("context"),
            parameters=args.get("parameters", {}),
        )

        # Generate response
        prompt = agent.build_context_prompt(agent_request)
        agent_response, metrics = self.llm_manager.generate_response(prompt)

        # Handle file content and update agent state
        self._process_agent_response(agent, agent_request, agent_response)

        # Build response text
        result_text = self._build_chat_response_text(agent, agent_response, metrics)
        return self._create_tool_success(result_text)

    def _process_agent_response(self, agent, agent_request, agent_response):
        """Process agent response - consolidated file handling and state update"""
        # Handle file content if present
        if agent_response.file_content and agent_response.status == ResponseStatus.SUCCESS:
            self._handle_file_content_for_agent(agent, agent_response)

        # Update agent state
        agent.update_activity(agent_request.task_type)
        agent.update_success_rate(agent_response.status.value == "success")
        agent.add_conversation(agent_request, agent_response)
        self.agent_registry.save_registry()

    def _handle_file_content_for_agent(self, agent, agent_response):
        """Handle file content processing for agent"""
        try:
            if agent_response.file_content.filename == agent.state.managed_file:
                success = agent.write_managed_file(agent_response.file_content.content)
                if success:
                    logger.info(
                        f"✅ Agent {agent.state.agent_id} wrote file: {agent.state.managed_file}"
                    )
                    agent_response.changes_made.append("File written to disk")
                else:
                    logger.error(f"❌ Agent {agent.state.agent_id} failed to write file")
                    agent_response.warnings.append("File content generated but disk write failed")
            else:
                agent_response.warnings.append(
                    f"Filename mismatch: generated {agent_response.file_content.filename}, "
                    f"manages {agent.state.managed_file}"
                )
        except Exception as e:
            logger.error(f"File writing error for agent {agent.state.agent_id}: {e}")
            agent_response.warnings.append(f"File write failed: {e!s}")

    def _build_chat_response_text(self, agent, agent_response, metrics) -> str:
        """Build formatted chat response text"""
        result_text = f"🤖 **Agent {agent.state.name} ({agent.state.agent_id}):**\n\n"
        result_text += f"**Status:** {agent_response.status.value}\n"
        result_text += f"**Response:** {agent_response.message}\n\n"

        if agent_response.file_content:
            result_text += f"**File Updated:** `{agent_response.file_content.filename}`\n"

        if agent_response.changes_made:
            result_text += f"**Changes:** {', '.join(agent_response.changes_made)}\n"

        if agent_response.warnings:
            result_text += f"**⚠️ Warnings:** {', '.join(agent_response.warnings)}\n"

        result_text += f"\n*📊 Tokens: {agent_response.tokens_used} | ⏱️ Time: {agent_response.processing_time:.1f}s*"

        return result_text

    async def _tool_get_agent_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle get_agent_info tool call"""
        try:
            agent_id = args.get("agent_id")
            if not agent_id:
                return self._create_tool_error("Missing agent_id")

            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            # Build and return success response
            summary = agent.get_summary()
            info_text = self._build_agent_info_text(agent, summary)
            return self._create_tool_success(info_text)

        except Exception as e:
            return self._create_tool_error(f"Failed to get agent info: {e!s}")

    def _build_agent_info_text(self, agent, summary) -> str:
        """Build agent info text"""
        info_text = f"🤖 **Agent Information: {agent.state.name}**\n\n"
        info_text += f"**ID:** {agent.state.agent_id}\n"
        info_text += f"**Description:** {agent.state.description}\n"
        info_text += f"**Managed File:** `{agent.state.managed_file}`\n"
        info_text += f"**File Exists:** {'✅' if summary['file_exists'] else '❌'}\n"

        if summary["file_size"]:
            info_text += f"**File Size:** {summary['file_size']} bytes\n"

        info_text += f"**Total Interactions:** {summary['total_interactions']}\n"
        info_text += f"**Success Rate:** {summary['success_rate']:.2f}\n"
        info_text += f"**Conversation Entries:** {summary['conversation_entries']}\n"
        info_text += f"**Context Length:** {summary['context_length']} chars\n"
        info_text += f"**Created:** {agent.state.created_at}\n"
        info_text += f"**Last Active:** {agent.state.last_activity}\n"
        info_text += f"**Workspace:** `{agent.workspace_dir}`"

        return info_text

    async def _tool_get_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle get_agent_file tool call"""
        try:
            agent_id = args.get("agent_id")
            if not agent_id:
                return self._create_tool_error("Missing agent_id")

            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            return self._build_file_response(agent)

        except Exception as e:
            return self._create_tool_error(f"Failed to read file: {e!s}")

    def _build_file_response(self, agent) -> dict[str, Any]:
        """Build file response for get_agent_file"""
        file_content = agent.read_managed_file()
        filename = agent.state.managed_file

        if file_content is None:
            text = (
                f"📄 **File Status:** `{filename}`\n\n"
                f"Agent: {agent.state.name} ({agent.state.agent_id})\n"
                f"File does not exist yet.\n\n"
                f"*Use `agent_update_file` to create the file.*"
            )
            return self._create_tool_success(text)

        # Determine file language for syntax highlighting
        file_ext = filename.split(".")[-1].lower() if "." in filename else "text"
        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "html": "html",
            "css": "css",
            "sql": "sql",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "md": "markdown",
            "sh": "bash",
        }
        language = language_map.get(file_ext, file_ext)

        text = (
            f"📄 **File Content:** `{filename}`\n\n"
            f"**Agent:** {agent.state.name} ({agent.state.agent_id})\n"
            f"**Size:** {len(file_content)} characters\n\n"
            f"```{language}\n{file_content}\n```"
        )
        return self._create_tool_success(text)

    async def _tool_delete_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle delete_agent tool call"""
        try:
            agent_id = args.get("agent_id")
            if not agent_id:
                return self._create_tool_error("Missing agent_id")

            # Get agent info before deletion
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            agent_name = agent.state.name
            managed_file = agent.state.managed_file

            # Perform deletion
            success, error = self.agent_registry.delete_agent(agent_id)

            if success:
                success_text = (
                    f"✅ **Agent Deleted Successfully**\n\n"
                    f"**Deleted:** {agent_name} (ID: {agent_id})\n"
                    f"**File Released:** `{managed_file}`\n\n"
                    f"The file `{managed_file}` is now available for a new agent.\n"
                    f"Workspace preserved at `workspaces/{agent_id}/`"
                )
                return self._create_tool_success(success_text)

            return self._create_tool_error(f"Deletion failed: {error}")

        except Exception as e:
            return self._create_tool_error(str(e))

    async def _tool_system_status(self) -> dict[str, Any]:
        """Handle system_status tool call"""
        try:
            # Get model info
            model_info = self.llm_manager.get_model_info()
            performance = self.llm_manager.get_performance_summary()

            # Get agent registry stats
            registry_stats = self.agent_registry.get_registry_stats()

            # Build status report
            status_text = "🖥️ **System Status Report**\n\n"

            # Model status
            status_text += f"**🤖 Model Status:** {'✅ Loaded' if model_info['model_loaded'] else '❌ Not Loaded'}\n"
            if model_info["model_loaded"]:
                status_text += f"**Model Path:** `{model_info['model_path']}`\n"
                status_text += f"**GPU Layers:** {model_info['configuration']['gpu_layers']}\n"
                status_text += f"**Context Size:** {model_info['configuration']['context_size']}\n"
                status_text += (
                    f"**Performance:** {performance.get('avg_tokens_per_second', 0)} tokens/sec\n"
                )

            status_text += "\n**👥 Agent Registry:**\n"
            status_text += f"**Total Agents:** {registry_stats['total_agents']}\n"
            status_text += f"**Managed Files:** {registry_stats['managed_files']}\n"
            status_text += f"**Total Interactions:** {registry_stats['total_interactions']}\n"
            status_text += (
                f"**Average Success Rate:** {registry_stats['average_success_rate']:.2f}\n"
            )

            if registry_stats["most_active_agent"]:
                most_active = registry_stats["most_active_agent"]
                status_text += f"**Most Active Agent:** {most_active['name']} ({most_active['interactions']} interactions)\n"

            status_text += "\n**🔧 System Configuration:**\n"
            status_text += "**CUDA Optimized:** ✅ RTX 1080ti + CUDA 12.9\n"
            status_text += "**JSON Schema:** ✅ Enabled\n"
            status_text += "**File Ownership:** ✅ One agent per file enforced\n"

            return self._create_tool_success(status_text)

        except Exception as e:
            return self._create_tool_error(f"System status check failed: {e!s}")

    async def _tool_agent_update_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle agent_update_file tool call"""
        try:
            agent_id = args.get("agent_id")
            instruction = args.get("instruction")

            if not agent_id or not instruction:
                return self._create_tool_error("Missing agent_id or instruction")

            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            # Build file update instruction and use chat functionality
            file_update_message = self._build_file_update_message(agent, instruction, args)

            chat_result = await self._tool_chat_with_agent(
                {
                    "agent_id": agent_id,
                    "message": file_update_message,
                    "task_type": "update",
                    "parameters": {"file_operation": "update"},
                }
            )

            return chat_result

        except Exception as e:
            return self._create_tool_error(f"File update failed: {e!s}")

    def _build_file_update_message(self, agent, instruction: str, args: dict) -> str:
        """Build file update message"""
        current_content = args.get("current_content", "") or agent.read_managed_file() or ""

        file_update_message = f"Update your managed file `{agent.state.managed_file}` according to these instructions:\n\n{instruction}\n\n"

        if current_content:
            file_update_message += f"Current file content:\n```\n{current_content}\n```\n\n"

        file_update_message += (
            "Provide the complete updated file content in your JSON response under 'file_content'."
        )

        return file_update_message

    async def _tool_agent_write_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle agent_write_file tool call"""
        try:
            # Validate inputs
            agent_id = args.get("agent_id")
            content = args.get("content")
            validation_required = args.get("validation_required", False)

            if not agent_id or not content:
                return self._create_tool_error("Missing agent_id or content")

            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            # Write the content
            success = agent.write_managed_file(content)
            if not success:
                return self._create_tool_error(f"File write failed for agent {agent.state.name}")

            result_text = "✅ **File Written Successfully**\n\n"
            result_text += f"**Agent:** {agent.state.name} ({agent_id})\n"
            result_text += f"**File:** `{agent.state.managed_file}`\n"
            result_text += f"**Size:** {len(content)} characters\n"

            # Update agent activity
            from schemas.agent_schemas import TaskType

            agent.update_activity(TaskType.UPDATE)
            agent.update_success_rate(True)

            # Optional validation
            if validation_required:
                result_text += "\n**Validation:** Not implemented in this version\n"

            # Save agent state
            self.agent_registry.save_registry()
            return self._create_tool_success(result_text)

        except Exception as e:
            return self._create_tool_error(str(e))

    async def _tool_validate_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle validate_agent_file tool call"""
        try:
            agent_id = args.get("agent_id")
            if not agent_id:
                return self._create_tool_error("Missing agent_id")

            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return self._create_tool_error(f"Agent {agent_id} not found")

            file_content = agent.read_managed_file()
            if not file_content:
                return self._create_tool_error(f"File not found: `{agent.state.managed_file}`")

            validation_type = args.get("validation_type", "syntax")
            validation_result = await self._validate_file_content(
                agent, file_content, validation_type
            )

            result_text = "🔍 **File Validation Results**\n\n"
            result_text += f"**Agent:** {agent.state.name} ({agent_id})\n"
            result_text += f"**File:** `{agent.state.managed_file}`\n"
            result_text += f"**Validation Type:** {validation_type}\n"
            result_text += f"**Status:** {validation_result['status']}\n"

            if validation_result.get("errors"):
                result_text += f"**❌ Errors:** {', '.join(validation_result['errors'])}\n"

            if validation_result.get("warnings"):
                result_text += f"**⚠️ Warnings:** {', '.join(validation_result['warnings'])}\n"

            if validation_result.get("suggestions"):
                result_text += (
                    f"**💡 Suggestions:** {', '.join(validation_result['suggestions'])}\n"
                )

            is_error = validation_result["status"] == "failed"
            return (
                self._create_tool_error(result_text)
                if is_error
                else self._create_tool_success(result_text)
            )

        except Exception as e:
            return self._create_tool_error(f"Validation error: {e!s}")

    async def _tool_orchestrate_agents(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle orchestrate_agents tool call for coordinating multiple agents"""
        try:
            agent_ids = args.get("agent_ids", [])
            task_description = args.get("task_description", "")

            if not agent_ids or not task_description:
                return self._create_tool_error("Missing agent_ids or task_description")

            # Validate all agents exist
            agents = []
            for agent_id in agent_ids:
                agent = self.agent_registry.get_agent(agent_id)
                if not agent:
                    return self._create_tool_error(f"Agent {agent_id} not found")
                agents.append(agent)

            # Build orchestration response
            wait_for_completion = args.get("wait_for_completion", True)
            result_text = "🎭 **Agent Orchestration Started**\n\n"
            result_text += f"**Task:** {task_description}\n"
            result_text += f"**Agents:** {len(agents)} agents coordinated\n\n"

            # List participating agents
            for agent in agents:
                result_text += f"• **{agent.state.name}** ({agent.state.agent_id}) → `{agent.state.managed_file}`\n"

            result_text += f"\n**Coordination Mode:** {'Wait for completion' if wait_for_completion else 'Async execution'}\n"
            result_text += "**Status:** Ready for task execution\n\n"
            result_text += "**Next Steps:**\n"
            result_text += "1. Use `chat_with_agent` to send specific tasks to each agent\n"
            result_text += "2. Use `validate_agent_file` to check each agent's output\n"
            result_text += "3. Use `agent_write_file` for direct file operations if needed\n"

            return self._create_tool_success(result_text)

        except Exception as e:
            return self._create_tool_error(f"Orchestration error: {e!s}")

    async def _validate_file_content(
        self, agent, content: str, validation_type: str = "syntax"
    ) -> dict[str, Any]:
        """Validate file content - simplified to reduce complexity"""
        try:
            file_ext = agent.state.managed_file.split(".")[-1].lower()

            # Initialize results
            result = {
                "status": "passed",
                "errors": [],
                "warnings": [],
                "suggestions": [],
            }

            # Perform validation based on file type
            self._validate_by_file_type(file_ext, content, validation_type, result)

            # Perform general checks
            self._validate_general_content(content, validation_type, result)

            # Set final status
            if result["errors"]:
                result["status"] = "failed"
            elif result["warnings"]:
                result["status"] = "passed_with_warnings"

            return result

        except Exception as e:
            return {
                "status": "error",
                "errors": [f"Validation failed: {e!s}"],
                "warnings": [],
                "suggestions": [],
            }

    def _validate_by_file_type(
        self, file_ext: str, content: str, validation_type: str, result: dict
    ):
        """Validate content based on file type"""
        if file_ext == "py" and validation_type in ["syntax", "all"]:
            self._validate_python_syntax(content, result)
        elif file_ext == "json" and validation_type in ["syntax", "all"]:
            self._validate_json_syntax(content, result)

        if validation_type in ["structure", "all"] and file_ext in ["py", "js"]:
            self._validate_code_structure(file_ext, content, result)

    def _validate_python_syntax(self, content: str, result: dict):
        """Validate Python syntax"""
        try:
            import ast

            ast.parse(content)
        except SyntaxError as e:
            result["errors"].append(f"Python syntax error: {e!s}")

    def _validate_json_syntax(self, content: str, result: dict):
        """Validate JSON syntax"""
        try:
            import json

            json.loads(content)
        except json.JSONDecodeError as e:
            result["errors"].append(f"JSON syntax error: {e!s}")

    def _validate_code_structure(self, file_ext: str, content: str, result: dict):
        """Validate code structure"""
        if file_ext == "py":
            if "def " not in content and "class " not in content:
                result["suggestions"].append("Consider adding functions or classes")
            if content.count("import ") > 10:
                result["suggestions"].append("Consider organizing imports")

    def _validate_general_content(self, content: str, validation_type: str, result: dict):
        """Validate general content characteristics"""
        if validation_type in ["formatting", "all"]:
            if len(content.split("\n")) > 1000:
                result["warnings"].append("File is very large (>1000 lines)")
            if not content.strip():
                result["errors"].append("File is empty")
