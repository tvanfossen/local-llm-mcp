"""Create file operation for file metadata"""

import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class CreateFileOperation(BaseMetadataOperation):
    """Create initial file structure in metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create initial file metadata structure

        Required arguments:
            path: str - File path relative to workspace
            description: str - File description

        Optional arguments:
            author: str - File author (default: "Local LLM Agent")
            version: str - File version (default: "1.0.0")
            file_type: str - Type of file (default: "python_module")
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        description = arguments.get("description", "")
        author = arguments.get("author", "Local LLM Agent")
        version = arguments.get("version", "1.0.0")
        file_type = arguments.get("file_type", "python_module")

        try:
            # Create new metadata structure
            metadata, meta_file = self._load_or_create_metadata(path)

            # Update file info
            metadata["file_info"].update({
                "description": description,
                "author": author,
                "version": version
            })

            # Update metadata type
            metadata["metadata"]["file_type"] = file_type

            # Save metadata
            result = self._save_metadata(metadata, meta_file)

            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ File structure created for {path}",
                    "path": path,
                    "metadata_path": str(meta_file)
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Failed to create file structure for {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to create file structure: {str(e)}"
            }