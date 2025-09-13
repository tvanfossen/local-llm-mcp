"""Core Utilities - Shared utility functions

Responsibilities:
- Path validation and security checks
- Response formatting for MCP tools
- File size formatting
- Common error handling
- Workspace path resolution
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


# Path Utilities


def validate_path(path: Union[str, Path], workspace_root: Optional[Path] = None) -> Path:
    """Validate and resolve path within workspace

    Args:
        path: Path to validate (string or Path object)
        workspace_root: Root directory for workspace (defaults to cwd)

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is outside workspace
    """
    workspace_root = workspace_root or Path.cwd()
    workspace_root = workspace_root.resolve()

    target = Path(path)
    if not target.is_absolute():
        target = workspace_root / target

    target = target.resolve()

    # Security check - must be within workspace
    try:
        target.relative_to(workspace_root)
    except ValueError:
        raise ValueError(f"Path outside workspace: {path}")

    return target


def get_workspace_root() -> Path:
    """Get the workspace root directory

    Returns:
        Path to workspace root
    """
    # Check for explicit workspace marker
    current = Path.cwd()

    # Look for .git directory as workspace root indicator
    while current != current.parent:
        if (current / ".git").exists():
            return current
        if (current / ".mcp-workspace").exists():
            return current
        current = current.parent

    # Default to current directory
    return Path.cwd()


# Response Formatting


def create_response(success: bool, data: Any = None, error: str = None) -> dict:
    """Create standardized response for internal operations

    Args:
        success: Whether operation succeeded
        data: Response data if successful
        error: Error message if failed

    Returns:
        Standardized response dict
    """
    if success:
        return {"success": True, "data": data, "error": None}
    else:
        return {"success": False, "data": None, "error": error or "Unknown error"}


def create_mcp_response(success: bool, message: str, is_json: bool = False) -> dict:
    """Create MCP-compliant tool response

    Args:
        success: Whether operation succeeded
        message: Response message or JSON data
        is_json: Whether message is JSON that should be pretty-printed

    Returns:
        MCP-compliant response dict
    """
    if success:
        if is_json:
            import json

            try:
                # Pretty print JSON data
                data = json.loads(message) if isinstance(message, str) else message
                text = json.dumps(data, indent=2)
            except:
                text = str(message)
        else:
            text = message

        return {"content": [{"type": "text", "text": text}], "isError": False}
    else:
        return {"content": [{"type": "text", "text": f"❌ **Error:** {message}"}], "isError": True}


def handle_exception(e: Exception, context: str) -> dict:
    """Handle exceptions with consistent error format

    Args:
        e: Exception that occurred
        context: Context where exception occurred (e.g., "File Read")

    Returns:
        MCP-compliant error response
    """
    logger.error(f"{context} error: {str(e)}", exc_info=True)

    return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}


# File Utilities


def format_file_size(size: int) -> str:
    """Format file size in human readable format

    Args:
        size: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if size == 0:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            if size == int(size):
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0

    return f"{size:.1f} TB"


def get_file_info(path: Path, base_dir: Optional[Path] = None) -> dict:
    """Get standardized file information

    Args:
        path: Path to file/directory
        base_dir: Base directory for relative path calculation

    Returns:
        Dict with file information
    """
    try:
        stat = path.stat()

        info = {
            "name": path.name,
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "is_hidden": path.name.startswith("."),
        }

        if base_dir:
            try:
                info["relative_path"] = str(path.relative_to(base_dir))
            except ValueError:
                info["relative_path"] = str(path)

        if path.is_file():
            info["extension"] = path.suffix

            # Add line count for text files
            try:
                content = path.read_text()
                info["lines"] = len(content.splitlines())
            except:
                pass

        return info

    except Exception as e:
        logger.warning(f"Could not get info for {path}: {e}")
        return {"name": path.name, "path": str(path), "type": "unknown", "error": str(e)}


def ensure_parent_dirs(path: Path) -> bool:
    """Ensure parent directories exist

    Args:
        path: Path whose parent directories should be created

    Returns:
        True if successful, False otherwise
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create parent directories for {path}: {e}")
        return False


# Validation Utilities


def validate_line_count(path: Path, max_lines: int = 300) -> dict:
    """Validate file line count against limit
    
    Args:
        path: Path to file
        max_lines: Maximum allowed lines
        
    Returns:
        Dict with validation result
    """
    try:
        if not path.exists():
            return {"valid": False, "error": f"File not found: {path}"}
        
        lines = len(path.read_text().splitlines())
        valid = lines <= max_lines
        
        return {
            "valid": valid,
            "lines": lines,
            "max_lines": max_lines,
            "error": None if valid else f"File has {lines} lines, exceeds limit of {max_lines}"
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def is_text_file(path: Path) -> bool:
    """Check if file appears to be text

    Args:
        path: Path to file

    Returns:
        True if file appears to be text
    """
    text_extensions = {
        ".py",
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".html",
        ".css",
        ".xml",
        ".csv",
        ".sql",
        ".rs",
        ".go",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
    }

    return path.suffix.lower() in text_extensions




# String Utilities


def truncate_string(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """Truncate string to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def build_prompt(context: str, task: str, request: str) -> str:
    """Build a structured prompt for LLM operations
    
    Args:
        context: Agent/system context
        task: Task type description
        request: User request
        
    Returns:
        Formatted prompt string
    """
    return f"""Context: {context}

Task: {task}
Request: {request}

Please provide a clear and helpful response based on the context and task requirements."""


def safe_json_loads(text: str, default=None) -> Any:
    """Safely parse JSON string with fallback
    
    Args:
        text: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    try:
        import json
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default or {}