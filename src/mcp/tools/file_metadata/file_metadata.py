"""File Metadata Tool - XML metadata file management

Responsibilities:
- Create and update XML metadata files in .meta/ directory
- Store structured file representations for code generation
- Small, focused tool calls to reduce context usage
"""

import logging
from pathlib import Path
from typing import Any, Dict

from src.core.utils.utils import create_mcp_response, handle_exception

logger = logging.getLogger(__name__)


class FileMetadataOperations:
    """File metadata operations handler"""

    def __init__(self, workspace_root: str = "/workspace"):
        """Initialize with workspace root"""
        self.workspace_root = Path(workspace_root)

    def create_metadata(self, path: str, xml_content: str) -> Dict[str, Any]:
        """Create or update XML metadata file"""
        try:
            # Ensure path is relative to workspace root
            if path.startswith('/'):
                path = path[1:]

            # Create .meta directory structure
            meta_dir = self.workspace_root / ".meta"
            meta_file = meta_dir / f"{path}.xml"

            # Ensure parent directories exist
            meta_file.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"📝 Creating metadata file: {meta_file}")

            # Write XML content with proper header
            final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated XML metadata for {path} -->
{xml_content.strip()}"""

            with open(meta_file, 'w', encoding='utf-8') as f:
                f.write(final_xml)

            return {
                "success": True,
                "message": f"Metadata file created: {meta_file}",
                "path": str(meta_file),
                "size": len(final_xml)
            }

        except Exception as e:
            logger.error(f"Failed to create metadata file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to create metadata: {str(e)}"
            }

    def read_metadata(self, path: str) -> Dict[str, Any]:
        """Read XML metadata file"""
        try:
            # Ensure path is relative to workspace root
            if path.startswith('/'):
                path = path[1:]

            meta_file = self.workspace_root / ".meta" / f"{path}.xml"

            if not meta_file.exists():
                return {
                    "success": False,
                    "error": f"Metadata file not found: {meta_file}"
                }

            with open(meta_file, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                "success": True,
                "content": content,
                "path": str(meta_file),
                "size": len(content)
            }

        except Exception as e:
            logger.error(f"Failed to read metadata file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to read metadata: {str(e)}"
            }

    def list_metadata(self) -> Dict[str, Any]:
        """List all metadata files"""
        try:
            meta_dir = self.workspace_root / ".meta"

            if not meta_dir.exists():
                return {
                    "success": True,
                    "files": [],
                    "count": 0
                }

            metadata_files = []
            for xml_file in meta_dir.rglob("*.xml"):
                relative_path = xml_file.relative_to(meta_dir)
                # Remove .xml extension to get original file path
                original_path = str(relative_path)[:-4]

                metadata_files.append({
                    "original_path": original_path,
                    "metadata_path": str(xml_file),
                    "size": xml_file.stat().st_size
                })

            return {
                "success": True,
                "files": metadata_files,
                "count": len(metadata_files)
            }

        except Exception as e:
            logger.error(f"Failed to list metadata files: {e}")
            return {
                "success": False,
                "error": f"Failed to list metadata: {str(e)}"
            }


# Global instance for MCP tool integration
_file_metadata_operations = FileMetadataOperations()


async def file_metadata_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """File metadata tool handler"""
    try:
        action = arguments.get("action")

        if not action:
            return create_mcp_response(False, "action parameter required. Available: create, read, list")

        if action == "create":
            path = arguments.get("path")
            xml_content = arguments.get("xml_content")

            if not path:
                return create_mcp_response(False, "path parameter required")
            if not xml_content:
                return create_mcp_response(False, "xml_content parameter required")

            result = _file_metadata_operations.create_metadata(path, xml_content)

            if result["success"]:
                return create_mcp_response(True, f"✅ {result['message']}")
            else:
                return create_mcp_response(False, f"❌ {result['error']}")

        elif action == "read":
            path = arguments.get("path")

            if not path:
                return create_mcp_response(False, "path parameter required")

            result = _file_metadata_operations.read_metadata(path)

            if result["success"]:
                return create_mcp_response(True, f"📄 Metadata content:\n{result['content']}")
            else:
                return create_mcp_response(False, f"❌ {result['error']}")

        elif action == "list":
            result = _file_metadata_operations.list_metadata()

            if result["success"]:
                if result["count"] == 0:
                    return create_mcp_response(True, "📂 No metadata files found")

                files_list = "\n".join([
                    f"  {file['original_path']} → {file['metadata_path']} ({file['size']} bytes)"
                    for file in result["files"]
                ])
                return create_mcp_response(True, f"📂 Found {result['count']} metadata files:\n{files_list}")
            else:
                return create_mcp_response(False, f"❌ {result['error']}")

        else:
            return create_mcp_response(False, f"Unknown action '{action}'. Available: create, read, list")

    except Exception as e:
        return handle_exception(e, "File Metadata Tool")