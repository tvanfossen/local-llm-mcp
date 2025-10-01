"""Consolidated MCP Tool Executor - 5 Core Tools Only

Responsibilities:
- Execute 5 consolidated tool categories
- Route requests to appropriate tool handlers
- Maintain clean separation of concerns
- Use class-based design for maintainability
"""

import logging
from typing import Any, Dict

from src.core.utils.utils import create_mcp_response, handle_exception
from .schema_loader import ToolSchemaLoader
from src.mcp.tools.agent_operations.agent_operations import agent_operations_tool
from src.mcp.tools.code_generation.code_generation import code_generation_tool
from src.mcp.tools.file_metadata.file_metadata import file_metadata_tool
from src.mcp.tools.git_operations.git_operations import git_tool
from src.mcp.tools.local_model.local_model import local_model_tool
from src.mcp.tools.validation.validation import run_all_validations, run_pre_commit, run_tests, validate_file_length
from src.mcp.tools.workspace.workspace import workspace_tool

logger = logging.getLogger(__name__)


class ValidationOperations:
    """Consolidated validation and testing operations"""

    async def execute(self, operation: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute validation operation"""
        try:
            if operation == "tests":
                return await run_tests(args)
            elif operation == "pre-commit":
                return await run_pre_commit(args)
            elif operation == "file-length":
                return await validate_file_length(args)
            elif operation == "all":
                return await run_all_validations(args)
            else:
                return create_mcp_response(False, f"Unknown validation operation: {operation}")

        except Exception as e:
            return handle_exception(e, f"Validation {operation}")


class ConsolidatedToolExecutor:
    """Consolidated MCP tool executor with 4 core tools"""

    def __init__(self, agent_registry=None, llm_manager=None):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.schema_loader = ToolSchemaLoader()

        # Initialize tool handlers
        self.validation = ValidationOperations()

        # Initialize local model tool if LLM manager available
        if llm_manager:
            from src.mcp.tools.local_model.local_model import initialize_local_model_tool

            initialize_local_model_tool(llm_manager)

        # Initialize agent operations tool if agent registry available
        if agent_registry:
            from src.mcp.tools.agent_operations.agent_operations import initialize_agent_operations_tool

            initialize_agent_operations_tool(agent_registry)

        self.available_tools = self._build_tool_registry()

    def _build_tool_registry(self) -> dict[str, Any]:
        """Build registry of tools using dynamic schema loading"""
        logger.info("Building tool registry with dynamic schema loading...")

        # Define tool mappings (name -> function) - functions stay the same
        tool_functions = {
            "local_model": local_model_tool,
            "git_operations": git_tool,
            "file_metadata": file_metadata_tool,
            "workspace": workspace_tool,
            "validation": self._validation_handler,
            "agent_operations": agent_operations_tool,
            "code_generation": code_generation_tool,
        }

        # Load schemas dynamically from JSON files
        dynamic_schemas = self.schema_loader.get_all_tool_schemas()

        # Build registry combining dynamic schemas with static functions
        registry = {}

        for tool_name, tool_function in tool_functions.items():
            if tool_name in dynamic_schemas:
                # Use dynamic schema from JSON file
                schema_info = dynamic_schemas[tool_name]
                registry[tool_name] = {
                    "name": schema_info["name"],
                    "description": schema_info["description"],
                    "function": tool_function,
                    "inputSchema": schema_info["inputSchema"]
                }
                logger.debug(f"✅ Loaded dynamic schema for {tool_name}")
            else:
                # Fallback for tools without JSON schema files (should be rare)
                logger.warning(f"⚠️ No JSON schema found for {tool_name}, using minimal fallback")
                registry[tool_name] = {
                    "name": tool_name,
                    "description": f"Tool: {tool_name} (schema not found)",
                    "function": tool_function,
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }

        logger.info(f"✅ Built tool registry with {len(registry)} tools ({len(dynamic_schemas)} dynamic schemas)")
        return registry

    async def _validation_handler(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle validation operations"""
        action = args.get("action")
        if not action:
            return create_mcp_response(False, "action parameter required")

        return await self.validation.execute(action, args)


    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools with schemas"""
        return [
            {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": tool_info["inputSchema"],
            }
            for tool_info in self.available_tools.values()
        ]

    async def execute_tool(self, tool_name: str, args: dict[str, Any] = None) -> dict[str, Any]:
        """Execute a tool by name"""
        # COMPREHENSIVE TOOL EXECUTION LOGGING
        logger.info(f"🔧 TOOL EXECUTOR: Executing {tool_name}")
        logger.info(f"  📥 Arguments: {args}")

        if tool_name not in self.available_tools:
            error_result = create_mcp_response(False, f"Unknown tool: {tool_name}")
            logger.error(f"  ❌ Tool not found: {tool_name}")
            logger.error(f"  📤 Error result: {error_result}")
            return error_result

        tool_info = self.available_tools[tool_name]
        tool_function = tool_info["function"]
        logger.info(f"  ✅ Tool found: {tool_name}")

        try:
            if args is None:
                args = {}

            logger.info(f"  🚀 Executing {tool_name} with {len(args)} arguments...")
            result = await tool_function(args)

            logger.info(f"  ✅ Tool execution completed: {tool_name}")
            logger.info(f"  📤 Result success: {result.get('success', 'unknown')}")
            logger.info(f"  📤 Full result: {result}")

            return result
        except Exception as e:
            error_result = handle_exception(e, f"Tool {tool_name}")
            logger.error(f"  ❌ Tool execution failed: {tool_name}")
            logger.error(f"  💥 Exception: {e}")
            logger.error(f"  📤 Error result: {error_result}")
            return error_result

    async def list_tools(self) -> dict[str, Any]:
        """List all available tools"""
        try:
            available_tools = sorted(self.available_tools.keys())
            tools_info = []

            for tool_name in available_tools:
                tool_info = self.available_tools[tool_name]
                tools_info.append(f"**{tool_name}**: {tool_info['description']}")

            summary = f"## Available Tools ({len(available_tools)})\n\n" + "\n".join(tools_info)
            return create_mcp_response(True, summary)

        except Exception as e:
            return handle_exception(e, "List Tools")
