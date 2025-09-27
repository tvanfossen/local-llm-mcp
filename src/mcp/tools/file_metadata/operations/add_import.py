"""Add import operation for file metadata"""

import logging
from typing import Any, Dict, List, Optional
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class AddImportOperation(BaseMetadataOperation):
    """Add import statements to file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add import statement to file metadata

        Required arguments:
            path: str - File path relative to workspace
            module: str - Module name to import

        Optional arguments:
            imported_items: str or list - Specific items to import (for 'from X import Y')
            alias: str - Alias for the import (for 'import X as Y')
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path", "module"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        module = arguments["module"]
        imported_items = arguments.get("imported_items")
        alias = arguments.get("alias")

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Prepare import entry
            import_entry = {"module": module}

            if imported_items:
                # Handle both string and list formats
                if isinstance(imported_items, list):
                    import_entry["imported_items"] = ", ".join(imported_items)
                else:
                    import_entry["imported_items"] = imported_items
            elif alias:
                import_entry["alias"] = alias

            # Check if import already exists
            existing_imports = metadata.get("imports", [])
            for existing_import in existing_imports:
                if existing_import["module"] == module:
                    if imported_items and existing_import.get("imported_items"):
                        # Merge imported items
                        existing_items = existing_import["imported_items"]
                        new_items = import_entry["imported_items"]
                        if new_items not in existing_items:
                            existing_import["imported_items"] = f"{existing_items}, {new_items}"
                        return self._save_metadata(metadata, meta_file)
                    elif alias and existing_import.get("alias") == alias:
                        # Import already exists with same alias
                        return {"success": True, "message": f"Import {module} as {alias} already exists"}
                    elif not imported_items and not alias and not existing_import.get("imported_items") and not existing_import.get("alias"):
                        # Simple import already exists
                        return {"success": True, "message": f"Import {module} already exists"}

            # Add new import
            metadata["imports"].append(import_entry)

            # Update dependencies in metadata
            if "dependencies" in metadata.get("metadata", {}):
                deps = metadata["metadata"]["dependencies"]
                if module not in deps:
                    deps.append(module)

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                import_desc = f"import {module}"
                if imported_items:
                    import_desc = f"from {module} import {import_entry['imported_items']}"
                elif alias:
                    import_desc = f"import {module} as {alias}"

                return {
                    "success": True,
                    "message": f"✅ Added import: {import_desc}",
                    "path": path,
                    "import": import_entry
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to add import to {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to add import: {str(e)}"
            }