"""Add field operation for file metadata"""

import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class AddFieldOperation(BaseMetadataOperation):
    """Add field (attribute) to class definition in file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add field/attribute to class definition

        Required arguments:
            path: str - File path relative to workspace
            class_name: str - Target class name
            name: str - Field name

        Optional arguments:
            type: str - Field type annotation
            description: str - Field description
            default: str - Default value
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path", "class_name", "name"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        class_name = arguments["class_name"]
        name = arguments["name"]
        field_type = arguments.get("type", "")
        description = arguments.get("description", "")
        default = arguments.get("default", "")

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Find target class
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

            # Initialize attributes list if not exists
            if "attributes" not in target_class:
                target_class["attributes"] = []

            # Check if field already exists
            existing_attributes = target_class["attributes"]
            for attr in existing_attributes:
                if attr["name"] == name:
                    return {
                        "success": False,
                        "error": f"Field '{name}' already exists in class '{class_name}'"
                    }

            # Prepare field entry
            field_entry = {
                "name": name,
                "type": field_type,
                "description": description,
                "default": default
            }

            # Add new field
            target_class["attributes"].append(field_entry)

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                type_info = f": {field_type}" if field_type else ""
                default_info = f" = {default}" if default else ""
                return {
                    "success": True,
                    "message": f"✅ Added field to class '{class_name}': {name}{type_info}{default_info}",
                    "path": path,
                    "field": field_entry
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to add field to {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to add field: {str(e)}"
            }