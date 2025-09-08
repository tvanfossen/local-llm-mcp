"""Git Log MCP Tool

Responsibilities:
- Show git commit history
- Filter by file path or date range
- Format log output for display
- Provide commit details

Generated from template on 2025-01-09T10:00:00
Template version: 1.0.0
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

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


async def git_log(args: dict[str, Any] = None) -> dict[str, Any]:
    """Show git commit history"""
    try:
        limit = args.get("limit", 10) if args else 10
        file_path = args.get("file_path") if args else None

        cmd = ["git", "log", f"-{limit}", "--oneline"]
        if file_path:
            cmd.extend(["--", file_path])

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return _process_git_log_result(result, limit, file_path)
    except Exception as e:
        return _handle_exception(e, "Git Log")


def _process_git_log_result(result, limit: int, file_path: str) -> dict[str, Any]:
    """Process git log command result"""
    if result.returncode != 0:
        return _create_error("Git Log Failed", f"Git error: {result.stderr}")

    log_output = result.stdout.strip()
    if not log_output:
        target = f" for {file_path}" if file_path else ""
        return _create_success(f"📜 **Git Log:** No commits found{target}")

    return _create_success(_format_git_log(log_output, limit, file_path))


def _format_git_log(log_output: str, limit: int, file_path: str) -> str:
    """Format git log output"""
    target = f" for {file_path}" if file_path else ""
    header = f"📜 **Git Log** (last {limit} commits{target}):\n\n"
    
    lines = log_output.split("\n")
    formatted_lines = []
    
    for line in lines:
        if line:
            # Parse format: "hash message"
            parts = line.split(" ", 1)
            if len(parts) == 2:
                hash_part = parts[0][:8]
                message = parts[1]
                formatted_lines.append(f"• `{hash_part}` - {message}")
            else:
                formatted_lines.append(f"• {line}")
    
    return header + "\n".join(formatted_lines)