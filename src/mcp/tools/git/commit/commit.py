"""Git Commit MCP Tool

Responsibilities:
- Create git commits with messages
- Add files to git staging area
- Handle git commit operations
- Provide commit success/failure feedback
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

from src.core.utils import create_success, create_error, handle_exception

logger = logging.getLogger(__name__)




async def git_commit(args: dict[str, Any]) -> dict[str, Any]:
    """Create git commit with message"""
    try:
        message = args.get("message")
        if not message:
            return create_error("Missing Parameter", "commit message is required")

        files = args.get("files", [])
        add_result = _add_files_to_git(files)
        return add_result if add_result else _create_git_commit(message, files)
    except Exception as e:
        return handle_exception(e, "Git Commit")


def _add_files_to_git(files: list) -> dict[str, Any] | None:
    """Add files to git staging area"""
    if files:
        for file_path in files:
            result = subprocess.run(["git", "add", file_path], capture_output=True, text=True, cwd=Path.cwd())
            if result.returncode != 0:
                return create_error("Git Add Failed", f"Failed to add {file_path}: {result.stderr}")
    else:
        result = subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=Path.cwd())
        if result.returncode != 0:
            return create_error("Git Add Failed", f"Failed to add files: {result.stderr}")
    return None


def _create_git_commit(message: str, files: list) -> dict[str, Any]:
    """Create git commit"""
    result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=Path.cwd())

    if result.returncode != 0:
        error_msg = result.stderr or result.stdout
        if "nothing to commit" in error_msg:
            return create_success("✅ **Git Commit:** Nothing to commit, working directory clean")
        return create_error("Git Commit Failed", f"Commit error: {error_msg}")

    commit_hash = _extract_commit_hash(result.stdout.strip())

    files_info = f" ({len(files)} files)" if files else " (all staged files)"
    return create_success(f"✅ **Git Commit Successful**\n📝 Message: {message}\n🔑 Hash: {commit_hash}{files_info}")


def _extract_commit_hash(output: str) -> str:
    """Extract commit hash from git commit output"""
    lines = output.split("\n")
    for line in lines:
        if line.startswith("[") and "]" in line:
            # Extract hash from format like "[main abc1234]"
            bracket_content = line[line.find("[") + 1 : line.find("]")]
            parts = bracket_content.split()
            if len(parts) > 1:
                return parts[1][:8]  # Return first 8 chars of hash
    return "unknown"
