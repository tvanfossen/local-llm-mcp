"""Add class operation for file metadata"""

import logging
from typing import Any, Dict, List, Optional
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class AddClassOperation(BaseMetadataOperation):
    """Add class definition to file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add class definition to file metadata

        Required arguments:
            path: str - File path relative to workspace
            name: str - Class name

        Optional arguments:
            description: str - Class description
            docstring: str - Class docstring
            base_classes: list - List of base class names for inheritance
            init_method: dict - __init__ method definition
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path", "name"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        name = arguments["name"]
        description = arguments.get("description", "")
        docstring = arguments.get("docstring", "")
        base_classes = arguments.get("base_classes", [])
        init_method = arguments.get("init_method")

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Check if class already exists
            existing_classes = metadata.get("classes", [])
            for existing_class in existing_classes:
                if existing_class["name"] == name:
                    return {
                        "success": False,
                        "error": f"Class '{name}' already exists in {path}"
                    }

            # Prepare class entry
            class_entry = {
                "name": name,
                "description": description,
                "docstring": docstring,
                "base_classes": base_classes if isinstance(base_classes, list) else [],
                "methods": []
            }

            # Add init method if provided
            if init_method:
                class_entry["init_method"] = init_method

            # Add new class
            metadata["classes"].append(class_entry)

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                inheritance_info = ""
                if base_classes:
                    inheritance_info = f" inheriting from {', '.join(base_classes)}"

                return {
                    "success": True,
                    "message": f"✅ Added class: {name}{inheritance_info}",
                    "path": path,
                    "class": class_entry
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to add class to {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to add class: {str(e)}"
            }