"""Consolidated MCP Tool Executor - 4 Core Tools Only

Responsibilities:
- Execute 4 consolidated tool categories
- Route requests to appropriate tool handlers
- Maintain clean separation of concerns
- Use class-based design for maintainability
"""

import logging
from typing import Any, Dict

from src.core.utils.utils import create_mcp_response, handle_exception
from src.mcp.tools.agent_operations.agent_operations import agent_operations_tool
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
        """Build registry of 4 core consolidated tools"""
        return {
            # Core Tool 1: Local Model Operations
            "local_model": {
                "name": "local_model",
                "description": "Local LLM operations (status, generate, load, unload)",
                "function": local_model_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Model operation to perform",
                            "enum": ["status", "generate", "load", "unload"],
                        },
                        "prompt": {"type": "string", "description": "Prompt for generation"},
                        "max_tokens": {"type": "integer", "description": "Max tokens to generate", "default": 512},
                        "temperature": {"type": "number", "description": "Generation temperature", "default": 0.7},
                    },
                    "required": ["operation"],
                },
            },
            # Core Tool 2: Git Operations
            "git_operations": {
                "name": "git_operations",
                "description": "Unified git operations (status, diff, commit, log, branch, stash, remote)",
                "function": git_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Git operation to perform",
                            "enum": ["status", "diff", "commit", "log", "branch", "stash", "remote"],
                        },
                        "message": {"type": "string", "description": "Commit message (for commit operation)"},
                        "add_all": {"type": "boolean", "description": "Add all files (for commit)", "default": False},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "Files to commit"},
                        "staged": {
                            "type": "boolean",
                            "description": "Show staged changes (for diff)",
                            "default": False,
                        },
                        "file_path": {"type": "string", "description": "Specific file path"},
                        "limit": {"type": "integer", "description": "Number of log entries (for log)", "default": 10},
                        "action": {"type": "string", "description": "Action for branch/stash operations"},
                        "name": {"type": "string", "description": "Branch or stash name"},
                        "short": {"type": "boolean", "description": "Short status format", "default": False},
                    },
                    "required": ["operation"],
                },
            },
            # Core Tool 3: File Metadata Operations (XML metadata management)
            "file_metadata": {
                "name": "file_metadata",
                "description": "File metadata operations (create, read, list XML metadata files)",
                "function": file_metadata_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Metadata action to perform",
                            "enum": ["create", "read", "list"],
                        },
                        "path": {"type": "string", "description": "File path for metadata operations"},
                        "xml_content": {"type": "string", "description": "XML content for create action"},
                    },
                    "required": ["action"],
                },
            },
            # Core Tool 4: Workspace Operations (File I/O)
            "workspace": {
                "name": "workspace",
                "description": "Workspace operations (read, write, delete, list, search, create_dir, tree)",
                "function": workspace_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Workspace action to perform",
                            "enum": ["read", "write", "delete", "list", "search", "create_dir", "tree", "write_artifact", "write_structured", "generate_from_metadata"],
                        },
                        "path": {"type": "string", "description": "File or directory path"},
                        "content": {"type": "string", "description": "File content"},
                        "pattern": {"type": "string", "description": "Search/file pattern", "default": "*"},
                        "file_pattern": {"type": "string", "description": "File pattern for search", "default": "*.py"},
                        "recursive": {"type": "boolean", "description": "Recursive operation", "default": False},
                        "include_hidden": {"type": "boolean", "description": "Include hidden files", "default": False},
                        "overwrite": {"type": "boolean", "description": "Allow overwriting", "default": False},
                        "create_dirs": {"type": "boolean", "description": "Create parent dirs", "default": True},
                        "parents": {"type": "boolean", "description": "Create parent dirs", "default": True},
                        "confirm": {"type": "boolean", "description": "Confirm deletion", "default": False},
                        "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": True},
                        "max_depth": {"type": "integer", "description": "Maximum depth", "default": 3},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                        "json_artifact": {"type": "object", "description": "JSON artifact for code generation"},
                    },
                    "required": ["action"],
                },
            },
            # Core Tool 4: Validation Operations
            "validation": {
                "name": "validation",
                "description": "Testing and validation operations (tests, pre-commit, file-length, all)",
                "function": self._validation_handler,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Validation operation to perform",
                            "enum": ["tests", "pre-commit", "file-length", "all"],
                        },
                        "test_path": {"type": "string", "description": "Test path", "default": "src/"},
                        "coverage": {"type": "boolean", "description": "Run with coverage", "default": True},
                        "verbose": {"type": "boolean", "description": "Verbose output", "default": False},
                        "hook": {"type": "string", "description": "Specific pre-commit hook to run"},
                        "all_files": {"type": "boolean", "description": "Run on all files", "default": False},
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to validate",
                        },
                        "max_lines": {"type": "integer", "description": "Maximum lines", "default": 300},
                    },
                    "required": ["operation"],
                },
            },
            # Core Tool 5: Agent Operations
            "agent_operations": {
                "name": "agent_operations",
                "description": "Agent management operations (list, info, stats, chat, create)",
                "function": agent_operations_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Agent operation to perform",
                            "enum": ["list", "info", "stats", "chat", "create"],
                        },
                        "agent_id": {"type": "string", "description": "Agent ID (for info and chat operations)"},
                        "message": {"type": "string", "description": "Message to send to agent (for chat operation)"},
                        "task_type": {
                            "type": "string",
                            "description": "Type of task (conversation, file_edit, code_generation, system_query)",
                            "default": "conversation",
                        },
                        "name": {"type": "string", "description": "Agent name (for create operation)"},
                        "description": {"type": "string", "description": "Agent description (for create operation)"},
                        "specialized_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files the agent will manage (for create operation)",
                            "default": [],
                        },
                    },
                    "required": ["operation"],
                },
            },
        }

    async def _validation_handler(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle validation operations"""
        operation = args.get("operation")
        if not operation:
            return create_mcp_response(False, "operation parameter required")

        return await self.validation.execute(operation, args)

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
        if tool_name not in self.available_tools:
            return create_mcp_response(False, f"Unknown tool: {tool_name}")

        tool_info = self.available_tools[tool_name]
        tool_function = tool_info["function"]

        try:
            if args is None:
                args = {}
            return await tool_function(args)
        except Exception as e:
            return handle_exception(e, f"Tool {tool_name}")

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
