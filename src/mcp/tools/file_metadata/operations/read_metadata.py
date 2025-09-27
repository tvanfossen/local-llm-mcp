"""Read metadata operation for file metadata"""

import json
import logging
from typing import Any, Dict
from .base import BaseMetadataOperation

logger = logging.getLogger(__name__)


class ReadMetadataOperation(BaseMetadataOperation):
    """Read and return file metadata"""

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read JSON metadata file

        Required arguments:
            path: str - File path relative to workspace

        Optional arguments:
            section: str - Specific section to return (imports, classes, functions, etc.)
        """
        # Validate required arguments
        is_valid, error_msg = self._validate_required_args(arguments, ["path"])
        if not is_valid:
            return {"success": False, "error": error_msg}

        path = arguments["path"]
        section = arguments.get("section")

        try:
            # Ensure path is relative to workspace root
            if path.startswith('/'):
                path = path[1:]

            meta_file = self.workspace_root / ".meta" / f"{path}.json"

            if not meta_file.exists():
                return {
                    "success": False,
                    "error": f"Metadata file not found: {meta_file}"
                }

            with open(meta_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse JSON
            try:
                metadata_obj = json.loads(content)

                # Return specific section if requested
                if section:
                    if section in metadata_obj:
                        return {
                            "success": True,
                            "section": section,
                            "data": metadata_obj[section],
                            "path": str(meta_file)
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Section '{section}' not found in metadata"
                        }

                # Return full metadata
                return {
                    "success": True,
                    "content": content,
                    "data": metadata_obj,
                    "path": str(meta_file),
                    "size": len(content)
                }

            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON in metadata file: {str(e)}"
                }

        except Exception as e:
            logger.error(f"Failed to read metadata file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to read metadata: {str(e)}"
            }