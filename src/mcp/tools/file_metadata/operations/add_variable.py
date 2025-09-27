"""Add variable operation for file metadata"""

import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class AddVariableOperation(BaseMetadataOperation):
    """Add variable/constant definition to file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add variable or constant definition to file metadata

        Required arguments:
            path: str - File path relative to workspace
            name: str - Variable name
            value: str - Variable value

        Optional arguments:
            type: str - Variable type annotation
            description: str - Variable description
            is_constant: bool - Whether this is a constant (default: False)
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path", "name", "value"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        name = arguments["name"]
        value = arguments["value"]
        var_type = arguments.get("type", "")
        description = arguments.get("description", "")
        is_constant = arguments.get("is_constant", False)

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Prepare variable entry
            var_entry = {
                "name": name,
                "value": value,
                "type": var_type,
                "description": description
            }

            # Determine if adding to constants or variables
            target_collection = "constants" if is_constant else "variables"

            # Check if variable already exists
            existing_vars = metadata.get(target_collection, [])
            for var in existing_vars:
                if var["name"] == name:
                    return {
                        "success": False,
                        "error": f"{'Constant' if is_constant else 'Variable'} '{name}' already exists in {path}"
                    }

            # Add new variable
            metadata[target_collection].append(var_entry)

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                var_type_info = f": {var_type}" if var_type else ""
                return {
                    "success": True,
                    "message": f"✅ Added {'constant' if is_constant else 'variable'}: {name}{var_type_info} = {value}",
                    "path": path,
                    "variable": var_entry
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to add variable to {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to add variable: {str(e)}"
            }