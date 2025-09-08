"""Pre-commit MCP Tool

Responsibilities:
- Run pre-commit hooks for validation
- Format pre-commit results
- Handle specific hook selection
- Provide validation feedback

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


async def run_pre_commit(args: dict[str, Any] = None) -> dict[str, Any]:
    """Run pre-commit hooks for validation"""
    try:
        hook = args.get("hook") if args else None
        all_files = args.get("all_files", False) if args else False

        cmd = ["pre-commit", "run"]

        if hook:
            cmd.append(hook)

        if all_files:
            cmd.append("--all-files")
        else:
            # Run on staged files only
            cmd.append("--files")
            # Get staged files
            staged_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, cwd=Path.cwd()
            )
            if staged_result.stdout:
                cmd.extend(staged_result.stdout.strip().split("\n"))
            else:
                return _create_success("✅ **Pre-commit:** No staged files to check")

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        return _process_precommit_result(result, hook, all_files)
    except FileNotFoundError:
        return _create_error("Pre-commit Not Installed", "Install with: pip install pre-commit")
    except Exception as e:
        logger.error(f"Pre-commit failed: {e}")
        return _create_error("Pre-commit Failed", str(e))


def _process_precommit_result(result, hook: str, all_files: bool) -> dict[str, Any]:
    """Process pre-commit result"""
    output = result.stdout + result.stderr

    if result.returncode == 0:
        scope = "all files" if all_files else "staged files"
        hook_name = hook if hook else "all hooks"
        return _create_success(
            f"✅ **Pre-commit Passed**\n🔍 Checked: {hook_name} on {scope}\nAll validation checks passed!"
        )
    else:
        # Parse failures
        failures = []
        for line in output.split("\n"):
            if "Failed" in line or "ERROR" in line:
                failures.append(line.strip())

        summary = "❌ **Pre-commit Validation Failed**\n\n"
        if failures:
            summary += "**Failures:**\n"
            for failure in failures[:5]:  # Limit to 5
                summary += f"• {failure}\n"

        # Include output (truncated)
        if len(output) > 800:
            output = output[:800] + "\n... [output truncated]"

        return _create_error("Validation Failed", summary + f"\n```\n{output}\n```")
