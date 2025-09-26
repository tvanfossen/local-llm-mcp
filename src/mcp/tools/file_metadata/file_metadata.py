"""File Metadata Tool - JSON metadata file management

Responsibilities:
- Create and update JSON metadata files in .meta/ directory
- Store structured file representations for code generation
- Small, focused tool calls to reduce context usage
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    SCHEMA_VALIDATION_AVAILABLE = True
except ImportError:
    SCHEMA_VALIDATION_AVAILABLE = False

from src.core.utils.utils import create_mcp_response, handle_exception

logger = logging.getLogger(__name__)


class FileMetadataOperations:
    """File metadata operations handler"""

    def __init__(self, workspace_root: str = "/workspace"):
        """Initialize with workspace root"""
        self.workspace_root = Path(workspace_root)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON schema for metadata validation"""
        try:
            schema_path = Path("/app/schema/python_metadata.json")
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"Schema file not found at {schema_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            return {}

    def _validate_metadata(self, metadata_obj: Dict[str, Any]) -> tuple[bool, str]:
        """Validate metadata against schema"""
        if not SCHEMA_VALIDATION_AVAILABLE:
            logger.warning("jsonschema not available, skipping validation")
            return True, ""

        if not self.schema:
            logger.warning("No schema loaded, skipping validation")
            return True, ""

        try:
            validate(instance=metadata_obj, schema=self.schema)
            return True, ""
        except ValidationError as e:
            error_msg = f"Schema validation failed: {e.message}"
            if e.path:
                error_msg += f" at path: {' -> '.join(str(p) for p in e.path)}"
            return False, error_msg
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def create_metadata(self, path: str, json_content: str) -> Dict[str, Any]:
        """Create or update JSON metadata file"""
        try:
            # Ensure path is relative to workspace root
            if path.startswith('/'):
                path = path[1:]

            # Create .meta directory structure
            meta_dir = self.workspace_root / ".meta"
            meta_file = meta_dir / f"{path}.json"

            # Ensure parent directories exist
            meta_file.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"📝 Creating metadata file: {meta_file}")

            # Parse and validate JSON content
            try:
                metadata_obj = json.loads(json_content) if isinstance(json_content, str) else json_content

                # Validate against schema before processing
                is_valid, validation_error = self._validate_metadata(metadata_obj)
                if not is_valid:
                    return {
                        "success": False,
                        "error": f"Metadata validation failed: {validation_error}"
                    }

                # Add metadata header
                if isinstance(metadata_obj, dict):
                    metadata_obj["_metadata"] = {
                        "generated_for": path,
                        "format": "json",
                        "description": f"Generated JSON metadata for {path}"
                    }

                # Write formatted JSON
                final_json = json.dumps(metadata_obj, indent=2, ensure_ascii=False)

            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON content: {str(e)}"
                }

            with open(meta_file, 'w', encoding='utf-8') as f:
                f.write(final_json)

            return {
                "success": True,
                "message": f"Metadata file created: {meta_file}",
                "path": str(meta_file),
                "size": len(final_json)
            }

        except Exception as e:
            logger.error(f"Failed to create metadata file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to create metadata: {str(e)}"
            }

    def read_metadata(self, path: str) -> Dict[str, Any]:
        """Read JSON metadata file"""
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

            # Parse and validate JSON
            try:
                metadata_obj = json.loads(content)
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
            for json_file in meta_dir.rglob("*.json"):
                relative_path = json_file.relative_to(meta_dir)
                # Remove .json extension to get original file path
                original_path = str(relative_path)[:-5]

                metadata_files.append({
                    "original_path": original_path,
                    "metadata_path": str(json_file),
                    "size": json_file.stat().st_size
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
            json_content = arguments.get("json_content")

            if not path:
                return create_mcp_response(False, "path parameter required")
            if not json_content:
                return create_mcp_response(False, "json_content parameter required")

            result = _file_metadata_operations.create_metadata(path, json_content)

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