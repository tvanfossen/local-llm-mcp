"""Complete file operation for file metadata"""

import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class CompleteFileOperation(BaseMetadataOperation):
    """Mark file as complete and finalize metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Mark file as complete in metadata

        Required arguments:
            path: str - File path relative to workspace

        Optional arguments:
            final_description: str - Final file description update
            complexity: str - File complexity level (low, medium, high)
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        final_description = arguments.get("final_description")
        complexity = arguments.get("complexity")

        try:
            # Load existing metadata
            metadata, meta_file = self._load_or_create_metadata(path)

            # Update file info if final description provided
            if final_description:
                metadata["file_info"]["description"] = final_description

            # Update complexity if provided
            if complexity and complexity in ["low", "medium", "high"]:
                metadata["metadata"]["complexity"] = complexity

            # Mark as complete
            metadata["metadata"]["status"] = "complete"
            metadata["metadata"]["completed_at"] = "auto-generated"

            # Calculate some basic stats
            stats = {
                "imports_count": len(metadata.get("imports", [])),
                "classes_count": len(metadata.get("classes", [])),
                "functions_count": len(metadata.get("functions", [])),
                "constants_count": len(metadata.get("constants", [])),
                "variables_count": len(metadata.get("variables", []))
            }

            # Add method counts from classes
            methods_count = 0
            for cls in metadata.get("classes", []):
                methods_count += len(cls.get("methods", []))
            stats["methods_count"] = methods_count

            metadata["metadata"]["stats"] = stats

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ File marked as complete: {path}",
                    "path": path,
                    "stats": stats
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to complete file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to complete file: {str(e)}"
            }