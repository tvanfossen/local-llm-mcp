"""MCP Tools Executor - Execute MCP Tool Calls

Responsibilities:
- Execute MCP tool calls
- Handle tool validation and dispatch
- Provide tool definitions and metadata
- Coordinate with git tools and other handlers
"""

import logging
from typing import Any

from src.mcp.tools.git.commit.commit import git_commit
from src.mcp.tools.git.diff.diff import git_diff
from src.mcp.tools.git.status.status import git_status

logger = logging.getLogger(__name__)


class MCPToolExecutor:
    """Executes MCP tool calls with validation"""

    def __init__(self, agent_registry, llm_manager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.available_tools = self._build_tool_registry()

    def _build_tool_registry(self) -> dict[str, Any]:
        """Build registry of available tools"""
        return {
            "git_status": {"name": "git_status", "description": "Check git repository status", "function": git_status},
            "git_commit": {"name": "git_commit", "description": "Create git commit", "function": git_commit},
            "git_diff": {"name": "git_diff", "description": "Show git diff", "function": git_diff},
        }

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools"""
        return [
            {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            }
            for tool_info in self.available_tools.values()
        ]

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], user_context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Execute a tool with given arguments"""
        if tool_name not in self.available_tools:
            return {"error": f"Tool not found: {tool_name}"}

        try:
            tool_function = self.available_tools[tool_name]["function"]
            result = await tool_function(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}
