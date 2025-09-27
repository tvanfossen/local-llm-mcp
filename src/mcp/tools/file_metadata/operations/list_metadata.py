"""List metadata operation for file metadata"""

import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class ListMetadataOperation(BaseMetadataOperation):
    """List all metadata files in workspace"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List all metadata files

        Optional arguments:
            filter_pattern: str - Pattern to filter file names
            include_stats: bool - Include file statistics (default: True)
        """
        filter_pattern = arguments.get("filter_pattern", "")
        include_stats = arguments.get("include_stats", True)

        try:
            meta_dir = self.workspace_root / ".meta"

            if not meta_dir.exists():
                return {
                    "success": True,
                    "files": [],
                    "count": 0,
                    "message": "No metadata directory found"
                }

            metadata_files = []
            for json_file in meta_dir.rglob("*.json"):
                relative_path = json_file.relative_to(meta_dir)
                # Remove .json extension to get original file path
                original_path = str(relative_path)[:-5]

                # Apply filter if provided
                if filter_pattern and filter_pattern not in original_path:
                    continue

                file_info = {
                    "original_path": original_path,
                    "metadata_path": str(json_file),
                    "size": json_file.stat().st_size
                }

                # Include basic stats if requested
                if include_stats:
                    try:
                        import json
                        with open(json_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)

                        file_info["stats"] = {
                            "imports": len(metadata.get("imports", [])),
                            "classes": len(metadata.get("classes", [])),
                            "functions": len(metadata.get("functions", [])),
                            "status": metadata.get("metadata", {}).get("status", "in_progress")
                        }
                    except Exception as e:
                        file_info["stats"] = {"error": f"Failed to read stats: {str(e)}"}

                metadata_files.append(file_info)

            return {
                "success": True,
                "files": metadata_files,
                "count": len(metadata_files),
                "filter_applied": filter_pattern if filter_pattern else None
            }

        except Exception as e:
            logger.error(f"Failed to list metadata files: {e}")
            return {
                "success": False,
                "error": f"Failed to list metadata: {str(e)}"
            }