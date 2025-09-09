"""Read File MCP Tool

Responsibilities:
- Read file contents with workspace safety checks
- Support both absolute and relative paths
- Return content in markdown code blocks for readability
- Include line number information
- Return standardized MCP response format
"""

import logging
from pathlib import Path
from typing import Any

from src.core.config.manager.manager import ConfigManager

logger = logging.getLogger(__name__)


def _create_success(text: str) -> dict[str, Any]:
    """Create success response format"""
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format"""
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
    """Handle exceptions with consistent error format"""
    return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}


async def read_file(args: dict[str, Any]) -> dict[str, Any]:
    """Read file contents with workspace safety checks"""
    try:
        file_path = args.get("file_path")
        start_line = args.get("start_line", 1)
        end_line = args.get("end_line")
        show_line_numbers = args.get("show_line_numbers", True)
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(file_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if file exists
        if not resolved_path.exists():
            return _create_error("File Not Found", f"File does not exist: {file_path}")
        
        if resolved_path.is_dir():
            return _create_error("Invalid File", f"Path is a directory, not a file: {file_path}")
        
        # Read file content
        try:
            content = resolved_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with latin-1 encoding for binary files
            try:
                content = resolved_path.read_text(encoding='latin-1')
                content = f"[Binary file content - decoded with latin-1]\n{content}"
            except Exception:
                return _create_error("Read Error", f"Cannot read file as text: {file_path}")
        
        # Process line range if specified
        lines = content.splitlines()
        if start_line > len(lines):
            return _create_error("Invalid Line Range", f"Start line {start_line} exceeds file length ({len(lines)} lines)")
        
        # Adjust for 1-based indexing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line) if end_line else len(lines)
        
        if start_line > 1 or end_line:
            lines = lines[start_idx:end_idx]
            actual_start = start_line
        else:
            actual_start = 1
        
        # Format content with line numbers if requested
        formatted_content = _format_file_content(
            lines, resolved_path, show_line_numbers, actual_start
        )
        
        return _create_success(formatted_content)
        
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return _handle_exception(e, "Read File")


def _resolve_and_validate_path(file_path: str, workspace_root: Path) -> Path | dict[str, Any]:
    """Resolve path and validate it's within workspace"""
    try:
        path = Path(file_path)
        
        # Convert relative paths to absolute within workspace
        if not path.is_absolute():
            path = workspace_root / path
        
        # Resolve to handle . and .. components
        resolved_path = path.resolve()
        workspace_resolved = workspace_root.resolve()
        
        # Security check: ensure path is within workspace
        try:
            resolved_path.relative_to(workspace_resolved)
        except ValueError:
            return _create_error(
                "Security Error", 
                f"File access denied: {file_path} is outside workspace ({workspace_root})"
            )
        
        return resolved_path
        
    except Exception as e:
        return _create_error("Path Error", f"Invalid file path: {file_path} - {str(e)}")


def _format_file_content(lines: list[str], file_path: Path, show_line_numbers: bool, start_line: int) -> str:
    """Format file content for display"""
    # Get file info
    file_size = file_path.stat().st_size
    total_lines = len(lines)
    
    # Detect file type for syntax highlighting
    file_extension = file_path.suffix.lower()
    language = _get_language_from_extension(file_extension)
    
    # Build header
    header = f"📄 **File:** `{file_path.name}`\n"
    header += f"📁 **Path:** `{file_path}`\n"
    header += f"📊 **Size:** {file_size:,} bytes | **Lines:** {total_lines:,}"
    
    if start_line > 1:
        end_line = start_line + len(lines) - 1
        header += f" | **Range:** {start_line}-{end_line}"
    
    header += "\n\n"
    
    # Format content
    if show_line_numbers:
        # Calculate padding for line numbers
        max_line_num = start_line + len(lines) - 1
        padding = len(str(max_line_num))
        
        formatted_lines = []
        for i, line in enumerate(lines):
            line_num = start_line + i
            formatted_lines.append(f"{line_num:>{padding}} │ {line}")
        
        content_block = "\n".join(formatted_lines)
    else:
        content_block = "\n".join(lines)
    
    # Wrap in code block with language detection
    code_block = f"```{language}\n{content_block}\n```"
    
    return f"{header}{code_block}"


def _get_language_from_extension(extension: str) -> str:
    """Get language identifier for syntax highlighting"""
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'jsx',
        '.tsx': 'tsx',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.php': 'php',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.sql': 'sql',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.xml': 'xml',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.md': 'markdown',
        '.txt': 'text',
        '.log': 'text',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'zsh',
        '.fish': 'fish',
        '.ps1': 'powershell',
        '.dockerfile': 'dockerfile',
        '.r': 'r',
        '.R': 'r',
        '.m': 'matlab',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.clj': 'clojure',
        '.hs': 'haskell',
        '.elm': 'elm',
        '.ex': 'elixir',
        '.exs': 'elixir',
        '.erl': 'erlang',
        '.lua': 'lua',
        '.pl': 'perl',
        '.vim': 'vim',
    }
    
    return language_map.get(extension, 'text')


async def get_file_info(args: dict[str, Any]) -> dict[str, Any]:
    """Get file information without reading contents"""
    try:
        file_path = args.get("file_path")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(file_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if file exists
        if not resolved_path.exists():
            return _create_error("File Not Found", f"File does not exist: {file_path}")
        
        # Get file statistics
        stat = resolved_path.stat()
        
        # Format file info
        info = f"📄 **File Information**\n\n"
        info += f"📁 **Path:** `{resolved_path}`\n"
        info += f"📝 **Name:** `{resolved_path.name}`\n"
        info += f"📊 **Size:** {stat.st_size:,} bytes\n"
        info += f"🕐 **Modified:** {_format_timestamp(stat.st_mtime)}\n"
        info += f"🕑 **Created:** {_format_timestamp(stat.st_ctime)}\n"
        
        if resolved_path.is_file():
            # Count lines for text files
            try:
                content = resolved_path.read_text(encoding='utf-8')
                line_count = len(content.splitlines())
                info += f"📏 **Lines:** {line_count:,}\n"
            except (UnicodeDecodeError, Exception):
                info += f"📏 **Lines:** Cannot count (binary file)\n"
        
        info += f"🔐 **Permissions:** {oct(stat.st_mode)[-3:]}\n"
        info += f"🗂️ **Type:** {'File' if resolved_path.is_file() else 'Directory'}"
        
        return _create_success(info)
        
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        return _handle_exception(e, "Get File Info")


def _format_timestamp(timestamp: float) -> str:
    """Format timestamp for display"""
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")