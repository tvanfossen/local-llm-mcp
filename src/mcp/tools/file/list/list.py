"""List Files MCP Tool

Responsibilities:
- List files and directories with workspace safety checks
- Support filtering by patterns and file types
- Provide detailed file information
- Return standardized MCP response format
"""

import logging
from pathlib import Path
from typing import Any
import fnmatch
import datetime

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


async def list_files(args: dict[str, Any] = None) -> dict[str, Any]:
    """List files and directories in a path"""
    try:
        if args is None:
            args = {}
            
        directory_path = args.get("directory_path", ".")
        pattern = args.get("pattern")
        include_hidden = args.get("include_hidden", False)
        recursive = args.get("recursive", False)
        max_depth = args.get("max_depth", 3)
        show_details = args.get("show_details", True)
        file_types = args.get("file_types", [])  # e.g., [".py", ".js", ".md"]
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(directory_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if directory exists
        if not resolved_path.exists():
            return _create_error("Directory Not Found", f"Directory does not exist: {directory_path}")
        
        if not resolved_path.is_dir():
            return _create_error("Invalid Directory", f"Path is not a directory: {directory_path}")
        
        # Get file listing
        files_info = _get_files_listing(
            resolved_path, pattern, include_hidden, recursive, max_depth, file_types
        )
        
        if not files_info:
            return _create_success(f"📁 **Directory:** `{resolved_path}`\n\nNo files found matching criteria.")
        
        # Format listing
        formatted_listing = _format_files_listing(resolved_path, files_info, show_details)
        
        return _create_success(formatted_listing)
        
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        return _handle_exception(e, "List Files")


def _resolve_and_validate_path(directory_path: str, workspace_root: Path) -> Path | dict[str, Any]:
    """Resolve path and validate it's within workspace"""
    try:
        path = Path(directory_path)
        
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
                f"Directory access denied: {directory_path} is outside workspace ({workspace_root})"
            )
        
        return resolved_path
        
    except Exception as e:
        return _create_error("Path Error", f"Invalid directory path: {directory_path} - {str(e)}")


def _get_files_listing(
    directory: Path, 
    pattern: str = None, 
    include_hidden: bool = False,
    recursive: bool = False,
    max_depth: int = 3,
    file_types: list[str] = None
) -> list[dict]:
    """Get list of files with filtering"""
    files_info = []
    
    try:
        if recursive:
            # Use glob pattern for recursive listing
            glob_pattern = "**/*" if include_hidden else "*"
            items = directory.glob(glob_pattern)
            
            # Filter by depth
            for item in items:
                try:
                    relative_parts = item.relative_to(directory).parts
                    if len(relative_parts) <= max_depth:
                        info = _get_file_info(item, directory)
                        if info and _matches_criteria(info, pattern, include_hidden, file_types):
                            files_info.append(info)
                except Exception:
                    continue
        else:
            # Non-recursive listing
            for item in directory.iterdir():
                try:
                    info = _get_file_info(item, directory)
                    if info and _matches_criteria(info, pattern, include_hidden, file_types):
                        files_info.append(info)
                except Exception:
                    continue
        
        # Sort by type (directories first) then by name
        files_info.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
        
    except Exception as e:
        logger.warning(f"Error listing directory {directory}: {e}")
    
    return files_info


def _get_file_info(path: Path, base_directory: Path) -> dict | None:
    """Get information about a file or directory"""
    try:
        stat = path.stat()
        relative_path = path.relative_to(base_directory)
        
        return {
            'name': path.name,
            'path': str(path),
            'relative_path': str(relative_path),
            'is_directory': path.is_dir(),
            'is_file': path.is_file(),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'created': stat.st_ctime,
            'permissions': oct(stat.st_mode)[-3:],
            'extension': path.suffix.lower() if path.is_file() else None,
            'is_hidden': path.name.startswith('.')
        }
    except Exception:
        return None


def _matches_criteria(
    file_info: dict, 
    pattern: str = None, 
    include_hidden: bool = False,
    file_types: list[str] = None
) -> bool:
    """Check if file matches filtering criteria"""
    # Hidden files filter
    if not include_hidden and file_info['is_hidden']:
        return False
    
    # Pattern filter
    if pattern:
        if not fnmatch.fnmatch(file_info['name'], pattern):
            return False
    
    # File type filter
    if file_types and file_info['is_file']:
        if file_info['extension'] not in file_types:
            return False
    
    return True


def _format_files_listing(directory: Path, files_info: list[dict], show_details: bool) -> str:
    """Format files listing for display"""
    # Header
    total_files = sum(1 for f in files_info if f['is_file'])
    total_dirs = sum(1 for f in files_info if f['is_directory'])
    total_size = sum(f['size'] for f in files_info if f['is_file'])
    
    header = (
        f"📁 **Directory:** `{directory}`\n\n"
        f"📊 **Summary:** {total_dirs} directories, {total_files} files "
        f"({_format_file_size(total_size)})\n\n"
    )
    
    if not show_details:
        # Simple listing
        items = []
        for file_info in files_info:
            icon = "📁" if file_info['is_directory'] else "📄"
            items.append(f"{icon} `{file_info['name']}`")
        
        return header + "\n".join(items)
    
    # Detailed listing
    items = []
    for file_info in files_info:
        item = _format_file_entry(file_info)
        items.append(item)
    
    return header + "\n".join(items)


def _format_file_entry(file_info: dict) -> str:
    """Format a single file entry"""
    if file_info['is_directory']:
        icon = "📁"
        size_info = ""
    else:
        icon = _get_file_icon(file_info['extension'])
        size_info = f" ({_format_file_size(file_info['size'])})"
    
    # Format timestamp
    modified_time = datetime.datetime.fromtimestamp(file_info['modified'])
    time_str = modified_time.strftime("%Y-%m-%d %H:%M")
    
    # Format permissions
    perms = file_info['permissions']
    
    return (
        f"{icon} **`{file_info['name']}`**{size_info}\n"
        f"   📅 {time_str} | 🔐 {perms} | 📍 `{file_info['relative_path']}`"
    )


def _get_file_icon(extension: str) -> str:
    """Get appropriate icon for file type"""
    if not extension:
        return "📄"
    
    icon_map = {
        '.py': '🐍',
        '.js': '🟨',
        '.ts': '🔷',
        '.html': '🌐',
        '.css': '🎨',
        '.md': '📝',
        '.txt': '📄',
        '.json': '📋',
        '.yaml': '⚙️',
        '.yml': '⚙️',
        '.xml': '📄',
        '.csv': '📊',
        '.pdf': '📕',
        '.doc': '📘',
        '.docx': '📘',
        '.xls': '📗',
        '.xlsx': '📗',
        '.ppt': '📙',
        '.pptx': '📙',
        '.zip': '🗜️',
        '.tar': '🗜️',
        '.gz': '🗜️',
        '.jpg': '🖼️',
        '.jpeg': '🖼️',
        '.png': '🖼️',
        '.gif': '🖼️',
        '.svg': '🖼️',
        '.mp3': '🎵',
        '.wav': '🎵',
        '.mp4': '🎬',
        '.avi': '🎬',
        '.mov': '🎬',
        '.log': '📋',
        '.sh': '⚡',
        '.bat': '⚡',
        '.exe': '⚙️',
        '.sql': '🗄️',
        '.db': '🗄️',
        '.sqlite': '🗄️'
    }
    
    return icon_map.get(extension, '📄')


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 bytes"
    
    size_names = ["bytes", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    if s.is_integer():
        s = int(s)
    
    return f"{s} {size_names[i]}"


async def find_files(args: dict[str, Any]) -> dict[str, Any]:
    """Find files by name or pattern across directories"""
    try:
        search_term = args.get("search_term")
        directory_path = args.get("directory_path", ".")
        case_sensitive = args.get("case_sensitive", False)
        max_results = args.get("max_results", 100)
        
        if not search_term:
            return _create_error("Missing Parameter", "Search term is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(directory_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if directory exists
        if not resolved_path.exists():
            return _create_error("Directory Not Found", f"Directory does not exist: {directory_path}")
        
        if not resolved_path.is_dir():
            return _create_error("Invalid Directory", f"Path is not a directory: {directory_path}")
        
        # Search for files
        matches = []
        search_pattern = search_term if case_sensitive else search_term.lower()
        
        try:
            for item in resolved_path.rglob("*"):
                if len(matches) >= max_results:
                    break
                
                try:
                    item_name = item.name if case_sensitive else item.name.lower()
                    
                    # Check if search term matches
                    if search_pattern in item_name or fnmatch.fnmatch(item_name, search_pattern):
                        file_info = _get_file_info(item, resolved_path)
                        if file_info:
                            matches.append(file_info)
                except Exception:
                    continue
        except Exception as e:
            return _create_error("Search Failed", f"Error during search: {str(e)}")
        
        if not matches:
            return _create_success(
                f"🔍 **Search Results**\n\n"
                f"Search term: `{search_term}`\n"
                f"Directory: `{resolved_path}`\n\n"
                f"No files found matching the search criteria."
            )
        
        # Format results
        result_text = (
            f"🔍 **Search Results**\n\n"
            f"Search term: `{search_term}`\n"
            f"Directory: `{resolved_path}`\n"
            f"Found: {len(matches)} matches"
        )
        
        if len(matches) >= max_results:
            result_text += f" (limited to {max_results})"
        
        result_text += "\n\n"
        
        # Add matches
        for file_info in matches:
            result_text += _format_file_entry(file_info) + "\n"
        
        return _create_success(result_text)
        
    except Exception as e:
        logger.error(f"Failed to find files: {e}")
        return _handle_exception(e, "Find Files")