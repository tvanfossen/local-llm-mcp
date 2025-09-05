# File: ~/Projects/local-llm-mcp/api/mcp_tools.py
"""MCP Tool Executor and Definitions

Responsibilities:
- Define all available MCP tools with schemas
- Execute tool calls and delegate to handlers
- Format responses for MCP consumption
- Coordinate between authentication and tool handlers
"""

import logging
from typing import Any

from api.mcp_tool_handlers import MCPToolHandlers
from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager

logger = logging.getLogger(__name__)


class MCPToolExecutor:
    """Executes MCP tools and formats responses"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager, authenticator):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.authenticator = authenticator
        self.handlers = MCPToolHandlers(agent_registry, llm_manager)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all MCP tool definitions"""
        return [
            {
                "name": "create_agent",
                "description": "Create a new agent to handle a specific file (ONE AGENT PER FILE ONLY)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Human-readable agent name"},
                        "description": {"type": "string", "description": "What this agent does"},
                        "system_prompt": {"type": "string", "description": "LLM system prompt"},
                        "managed_file": {"type": "string", "description": "Single file this agent manages"},
                        "initial_context": {"type": "string", "description": "Initial context (optional)"},
                    },
                    "required": ["name", "description", "system_prompt", "managed_file"],
                },
            },
            {
                "name": "list_agents",
                "description": "List all active agents and their managed files",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_agent_info",
                "description": "Get detailed information about a specific agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID to query"}},
                    "required": ["agent_id"],
                },
            },
            {
                "name": "delete_agent",
                "description": "Delete an agent and free up its managed file",
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID to delete"}},
                    "required": ["agent_id"],
                },
            },
            {
                "name": "chat_with_agent",
                "description": "Send a message to a specific agent in their context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID to chat with"},
                        "message": {"type": "string", "description": "Message to send to the agent"},
                        "task_type": {
                            "type": "string",
                            "enum": ["create", "update", "analyze", "refactor", "debug", "document", "test"],
                            "default": "update",
                        },
                        "context": {"type": "string", "description": "Additional context (optional)"},
                    },
                    "required": ["agent_id", "message"],
                },
            },
            {
                "name": "get_agent_file",
                "description": "Get the current content of a file managed by an agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID"}},
                    "required": ["agent_id"],
                },
            },
            {
                "name": "system_status",
                "description": "Get system status including model and agent information",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    async def execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute tool and return MCP-formatted result"""
        tool_handlers = {
            "create_agent": self.handlers.create_agent,
            "list_agents": self.handlers.list_agents,
            "get_agent_info": self.handlers.get_agent_info,
            "chat_with_agent": self.handlers.chat_with_agent,
            "get_agent_file": self.handlers.get_agent_file,
            "delete_agent": self.handlers.delete_agent,
            "system_status": lambda args: self.handlers.system_status(args, self.authenticator),
        }

        handler = tool_handlers.get(tool_name)
        if handler:
            return await handler(args)

        return self._create_error("Unknown tool", f"Tool '{tool_name}' not found")

    def _create_error(self, title: str, message: str) -> dict[str, Any]:
        """Create error tool response"""
        return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}
