"""File Metadata Tool - Router for incremental metadata operations

Responsibilities:
- Route operations to specialized handlers
- Support incremental file building with small operations
- Automatic dependency tracking integration
"""

import logging
from typing import Any, Dict

from src.core.utils.utils import create_mcp_response, handle_exception
from .operations import (
    CreateFileOperation,
    AddImportOperation,
    AddVariableOperation,
    AddClassOperation,
    AddFunctionOperation,
    AddFieldOperation,
    CompleteFileOperation,
    ReadMetadataOperation,
    ListMetadataOperation
)
from .registry import DependencyTracker

logger = logging.getLogger(__name__)


class FileMetadataRouter:
    """Router for file metadata operations"""

    def __init__(self, workspace_root: str = "/workspace"):
        """Initialize router with workspace root"""
        self.workspace_root = workspace_root
        self.dependency_tracker = DependencyTracker(workspace_root)

        # Initialize operation handlers
        self.operations = {
            "create_file": CreateFileOperation(workspace_root),
            "add_import": AddImportOperation(workspace_root),
            "add_variable": AddVariableOperation(workspace_root),
            "add_class": AddClassOperation(workspace_root),
            "add_function": AddFunctionOperation(workspace_root),
            "add_field": AddFieldOperation(workspace_root),
            "complete_file": CompleteFileOperation(workspace_root),
            "read": ReadMetadataOperation(workspace_root),
            "list": ListMetadataOperation(workspace_root)
        }

    async def route_operation(self, action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route operation to appropriate handler"""
        if action not in self.operations:
            return {
                "success": False,
                "error": f"Unknown action '{action}'. Available: {', '.join(self.operations.keys())}"
            }

        try:
            # Execute operation
            result = await self.operations[action].execute(arguments)

            # Update dependency registry if operation succeeded and modifies metadata
            if result.get("success") and action in ["create_file", "add_import", "add_class", "add_function", "complete_file"]:
                path = arguments.get("path")
                if path:
                    await self._update_dependency_registry(path)

            return result

        except Exception as e:
            logger.error(f"Failed to execute {action}: {e}")
            return {
                "success": False,
                "error": f"Failed to execute {action}: {str(e)}"
            }

    async def _update_dependency_registry(self, path: str) -> None:
        """Update dependency registry from metadata file"""
        try:
            # Read current metadata
            read_op = self.operations["read"]
            result = await read_op.execute({"path": path})

            if result.get("success") and "data" in result:
                self.dependency_tracker.update_from_metadata(path, result["data"])

        except Exception as e:
            logger.warning(f"Failed to update dependency registry for {path}: {e}")


# Global router instance for MCP tool integration
_file_metadata_router = FileMetadataRouter()


async def file_metadata_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """File metadata tool handler - routes to incremental operations"""
    try:
        action = arguments.get("action")

        if not action:
            available_actions = list(_file_metadata_router.operations.keys())
            return create_mcp_response(False, f"action parameter required. Available: {', '.join(available_actions)}")

        # Route to appropriate operation
        result = await _file_metadata_router.route_operation(action, arguments)

        if result["success"]:
            message = result.get("message", "Operation completed successfully")
            return create_mcp_response(True, message)
        else:
            error = result.get("error", "Unknown error occurred")
            return create_mcp_response(False, f"❌ **Error:** {error}")

    except Exception as e:
        return handle_exception(e, "File Metadata Tool")