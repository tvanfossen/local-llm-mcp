"""Git Status MCP Tool

Responsibilities:
- Check git repository status and changes
- Format git status output for display
- Handle git status command execution
- Provide detailed status information
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


async def git_status(args: dict[str, Any] = None) -> dict[str, Any]:
    """Check git repository status and changes"""
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=Path.cwd())
        return _process_git_status_result(result)
    except Exception as e:
        return _handle_exception(e, "Git Status")


def _process_git_status_result(result) -> dict[str, Any]:
    """Process git status command result"""
    if result.returncode != 0:
        return _create_error("Git Status Failed", f"Git error: {result.stderr}")

    status_output = result.stdout.strip()
    if not status_output:
        return _create_success("🌿 **Git Status:** Working directory clean")

    return _create_success(_format_git_status(status_output))


def _format_git_status(status_output: str) -> str:
    """Format git status output"""
    lines = status_output.split("\n")
    modified, staged, untracked = [], [], []

    for line in lines:
        if len(line) < 3:
            continue

        status_code = line[:2]
        file_path = line[3:]

        if status_code[0] != " ":  # Staged changes
            staged.append(file_path)
        elif status_code[1] == "M":  # Modified
            modified.append(file_path)
        elif status_code == "??":  # Untracked
            untracked.append(file_path)

    # Build formatted output
    sections = []

    if staged:
        sections.append(f"📦 **Staged Changes:** {len(staged)} files\n   " + "\n   ".join(staged))

    if modified:
        sections.append(f"🔧 **Modified Files:** {len(modified)} files\n   " + "\n   ".join(modified))

    if untracked:
        sections.append(f"❓ **Untracked Files:** {len(untracked)} files\n   " + "\n   ".join(untracked))

    return "📊 **Git Status:**\n\n" + "\n\n".join(sections)
