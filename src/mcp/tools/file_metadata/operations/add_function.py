"""Add function operation for file metadata"""

import logging
from typing import Any, Dict, List, Optional
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class AddFunctionOperation(BaseMetadataOperation):
    """Add function/method definition to file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add function or method definition to file metadata

        Required arguments:
            path: str - File path relative to workspace
            name: str - Function/method name

        Optional arguments:
            description: str - Function description
            docstring: str - Function docstring
            parameters: list - List of parameter definitions
            returns: dict - Return type information
            operations: list - List of operations for function body
            class_name: str - If provided, adds as method to this class
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path", "name"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        name = arguments["name"]
        description = arguments.get("description", "")
        docstring = arguments.get("docstring", "")
        parameters = arguments.get("parameters", [])
        returns = arguments.get("returns")
        operations = arguments.get("operations", [])
        class_name = arguments.get("class_name")

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Prepare function entry
            function_entry = {
                "name": name,
                "description": description,
                "docstring": docstring,
                "parameters": parameters if isinstance(parameters, list) else [],
                "operations": operations if isinstance(operations, list) else []
            }

            if returns:
                function_entry["returns"] = returns

            if class_name:
                # Add as method to existing class
                classes = metadata.get("classes", [])
                target_class = None
                for cls in classes:
                    if cls["name"] == class_name:
                        target_class = cls
                        break

                if not target_class:
                    return {
                        "success": False,
                        "error": f"Class '{class_name}' not found in {path}"
                    }

                # Check if method already exists
                existing_methods = target_class.get("methods", [])
                for method in existing_methods:
                    if method["name"] == name:
                        return {
                            "success": False,
                            "error": f"Method '{name}' already exists in class '{class_name}'"
                        }

                # Add method to class
                target_class["methods"].append(function_entry)
                method_info = f"method '{name}' to class '{class_name}'"

            else:
                # Add as standalone function
                functions = metadata.get("functions", [])
                for func in functions:
                    if func["name"] == name:
                        return {
                            "success": False,
                            "error": f"Function '{name}' already exists in {path}"
                        }

                metadata["functions"].append(function_entry)
                method_info = f"function '{name}'"

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ Added {method_info}",
                    "path": path,
                    "function": function_entry
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to add function to {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to add function: {str(e)}"
            }