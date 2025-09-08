"""Git Diff MCP Tool

Responsibilities:
- Show git diff of changes
- Handle both staged and unstaged changes
- Support specific file diffs
- Format diff output for display
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


async def git_diff(args: dict[str, Any] = None) -> dict[str, Any]:
    """Show git diff of changes"""
    try:
        file_path = args.get("file_path") if args else None
        staged = args.get("staged", False) if args else False

        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        if file_path:
            cmd.append(file_path)

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return _process_git_diff_result(result, file_path, staged)
    except Exception as e:
        return _handle_exception(e, "Git Diff")


def _process_git_diff_result(result, file_path: str, staged: bool) -> dict[str, Any]:
    """Process git diff command result"""
    if result.returncode != 0:
        return _create_error("Git Diff Failed", f"Git error: {result.stderr}")

    diff_output = result.stdout.strip()
    if not diff_output:
        scope = "staged changes" if staged else "working directory"
        target = f" for {file_path}" if file_path else ""
        return _create_success(f"📋 **Git Diff:** No changes in {scope}{target}")

    return _create_success(_format_git_diff(diff_output, file_path, staged))


def _format_git_diff(diff_output: str, file_path: str, staged: bool) -> str:
    """Format git diff output"""
    scope = "staged changes" if staged else "working directory"
    target = f" for {file_path}" if file_path else ""

    # Truncate very long diffs
    if len(diff_output) > 2000:
        diff_output = diff_output[:2000] + "\n\n... [diff truncated]"

    return f"📋 **Git Diff** ({scope}{target}):\n\n```diff\n{diff_output}\n```"
