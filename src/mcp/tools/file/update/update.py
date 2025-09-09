"""Update File MCP Tool

Responsibilities:
- Update specific lines or sections in files
- Support line-based replacements with line number information
- Handle insertions and deletions
- Return standardized MCP response format with detailed change info
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


async def update_file_lines(args: dict[str, Any]) -> dict[str, Any]:
    """Update specific lines in a file"""
    try:
        file_path = args.get("file_path")
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        new_content = args.get("new_content", "")
        encoding = args.get("encoding", "utf-8")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        if start_line is None:
            return _create_error("Missing Parameter", "Start line is required")
        
        # Default end_line to start_line for single line replacement
        if end_line is None:
            end_line = start_line
        
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
            return _create_error("Invalid Target", f"Path is a directory, not a file: {file_path}")
        
        # Read current content
        try:
            original_content = resolved_path.read_text(encoding=encoding)
            lines = original_content.splitlines()
        except Exception as e:
            return _create_error("Read Failed", f"Cannot read file: {str(e)}")
        
        # Validate line numbers
        if start_line < 1 or start_line > len(lines):
            return _create_error("Invalid Line Number", f"Start line {start_line} is out of range (1-{len(lines)})")
        
        if end_line < start_line or end_line > len(lines):
            return _create_error("Invalid Line Number", f"End line {end_line} is out of range ({start_line}-{len(lines)})")
        
        # Prepare replacement content
        new_lines = new_content.splitlines() if new_content else []
        
        # Perform replacement (convert to 0-based indexing)
        start_idx = start_line - 1
        end_idx = end_line
        
        # Store original lines for change tracking
        original_lines = lines[start_idx:end_idx]
        
        # Replace lines
        updated_lines = lines[:start_idx] + new_lines + lines[end_idx:]
        
        # Write updated content
        try:
            updated_content = "\n".join(updated_lines)
            if original_content.endswith("\n"):
                updated_content += "\n"
            resolved_path.write_text(updated_content, encoding=encoding)
        except Exception as e:
            return _create_error("Write Failed", f"Cannot write to file: {str(e)}")
        
        # Format change summary
        change_summary = _format_change_summary(
            resolved_path, original_lines, new_lines, start_line, end_line
        )
        
        return _create_success(change_summary)
        
    except Exception as e:
        logger.error(f"Failed to update file lines: {e}")
        return _handle_exception(e, "Update File Lines")


async def replace_text(args: dict[str, Any]) -> dict[str, Any]:
    """Replace text patterns in a file"""
    try:
        file_path = args.get("file_path")
        search_text = args.get("search_text")
        replace_text = args.get("replace_text", "")
        replace_all = args.get("replace_all", False)
        case_sensitive = args.get("case_sensitive", True)
        encoding = args.get("encoding", "utf-8")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        if not search_text:
            return _create_error("Missing Parameter", "Search text is required")
        
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
            return _create_error("Invalid Target", f"Path is a directory, not a file: {file_path}")
        
        # Read current content
        try:
            original_content = resolved_path.read_text(encoding=encoding)
        except Exception as e:
            return _create_error("Read Failed", f"Cannot read file: {str(e)}")
        
        # Perform replacement
        if case_sensitive:
            if replace_all:
                updated_content = original_content.replace(search_text, replace_text)
                replacement_count = original_content.count(search_text)
            else:
                updated_content = original_content.replace(search_text, replace_text, 1)
                replacement_count = 1 if search_text in original_content else 0
        else:
            # Case-insensitive replacement
            import re
            pattern = re.escape(search_text)
            flags = re.IGNORECASE
            
            if replace_all:
                updated_content = re.sub(pattern, replace_text, original_content, flags=flags)
                replacement_count = len(re.findall(pattern, original_content, flags=flags))
            else:
                updated_content = re.sub(pattern, replace_text, original_content, count=1, flags=flags)
                replacement_count = 1 if re.search(pattern, original_content, flags=flags) else 0
        
        if replacement_count == 0:
            return _create_error("No Matches", f"Text not found: '{search_text}'")
        
        # Write updated content
        try:
            resolved_path.write_text(updated_content, encoding=encoding)
        except Exception as e:
            return _create_error("Write Failed", f"Cannot write to file: {str(e)}")
        
        # Format success response
        success_msg = (
            f"✅ **Text Replaced Successfully**\n\n"
            f"📄 **File:** `{resolved_path.name}`\n"
            f"📁 **Path:** `{resolved_path}`\n"
            f"🔍 **Search:** `{search_text}`\n"
            f"🔄 **Replace:** `{replace_text}`\n"
            f"📊 **Replacements:** {replacement_count}\n"
            f"⚙️ **Options:** {'All matches' if replace_all else 'First match'}, "
            f"{'Case sensitive' if case_sensitive else 'Case insensitive'}"
        )
        
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to replace text: {e}")
        return _handle_exception(e, "Replace Text")


async def insert_lines(args: dict[str, Any]) -> dict[str, Any]:
    """Insert lines at a specific position in a file"""
    try:
        file_path = args.get("file_path")
        line_number = args.get("line_number")
        content = args.get("content", "")
        encoding = args.get("encoding", "utf-8")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        if line_number is None:
            return _create_error("Missing Parameter", "Line number is required")
        
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
            return _create_error("Invalid Target", f"Path is a directory, not a file: {file_path}")
        
        # Read current content
        try:
            original_content = resolved_path.read_text(encoding=encoding)
            lines = original_content.splitlines()
        except Exception as e:
            return _create_error("Read Failed", f"Cannot read file: {str(e)}")
        
        # Validate line number (allow inserting at end + 1)
        if line_number < 1 or line_number > len(lines) + 1:
            return _create_error("Invalid Line Number", f"Line number {line_number} is out of range (1-{len(lines) + 1})")
        
        # Prepare content to insert
        new_lines = content.splitlines() if content else [""]
        
        # Insert lines (convert to 0-based indexing)
        insert_idx = line_number - 1
        updated_lines = lines[:insert_idx] + new_lines + lines[insert_idx:]
        
        # Write updated content
        try:
            updated_content = "\n".join(updated_lines)
            if original_content.endswith("\n") or not original_content:
                updated_content += "\n"
            resolved_path.write_text(updated_content, encoding=encoding)
        except Exception as e:
            return _create_error("Write Failed", f"Cannot write to file: {str(e)}")
        
        # Format success response
        lines_added = len(new_lines)
        success_msg = (
            f"✅ **Lines Inserted Successfully**\n\n"
            f"📄 **File:** `{resolved_path.name}`\n"
            f"📁 **Path:** `{resolved_path}`\n"
            f"📍 **Position:** Line {line_number}\n"
            f"📊 **Lines Added:** {lines_added}\n"
            f"📏 **New Total Lines:** {len(updated_lines)}"
        )
        
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to insert lines: {e}")
        return _handle_exception(e, "Insert Lines")


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


def _format_change_summary(resolved_path: Path, original_lines: list[str], new_lines: list[str], start_line: int, end_line: int) -> str:
    """Format a summary of changes made to the file"""
    lines_removed = len(original_lines)
    lines_added = len(new_lines)
    net_change = lines_added - lines_removed
    
    # Calculate file statistics
    try:
        updated_content = resolved_path.read_text(encoding='utf-8')
        total_lines = len(updated_content.splitlines())
        file_size = resolved_path.stat().st_size
    except Exception:
        total_lines = "Unknown"
        file_size = 0
    
    # Build change description
    if start_line == end_line and lines_removed == 1:
        change_desc = f"Updated line {start_line}"
    else:
        change_desc = f"Updated lines {start_line}-{end_line}"
    
    # Format change summary
    summary = (
        f"✅ **File Updated Successfully**\n\n"
        f"📄 **File:** `{resolved_path.name}`\n"
        f"📁 **Path:** `{resolved_path}`\n"
        f"🔄 **Change:** {change_desc}\n"
        f"📊 **Lines:** -{lines_removed}, +{lines_added} (net: {net_change:+d})\n"
        f"📏 **Total Lines:** {total_lines}\n"
        f"💾 **File Size:** {file_size:,} bytes"
    )
    
    # Add change preview if reasonable size
    if lines_removed <= 5 and lines_added <= 5:
        summary += "\n\n**Change Preview:**"
        
        if original_lines:
            summary += "\n```diff\n"
            for line in original_lines:
                summary += f"- {line}\n"
            for line in new_lines:
                summary += f"+ {line}\n"
            summary += "```"
        else:
            summary += f"\n```\n{chr(10).join(new_lines)}\n```"
    
    return summary