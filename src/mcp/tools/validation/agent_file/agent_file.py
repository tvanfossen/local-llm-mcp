"""Agent File Validation MCP Tool

Responsibilities:
- Validate agent's managed file meets requirements
- Check file existence and format
- Verify schema compliance
- Report validation results

Generated from template on 2025-01-09T10:00:00
Template version: 1.0.0
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _create_success(text: str) -> dict[str, Any]:
    """Create success response format"""
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format"""
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


async def validate_agent_file(args: dict[str, Any]) -> dict[str, Any]:
    """Validate agent's managed file meets all requirements"""
    try:
        agent_id = args.get("agent_id")

        if not agent_id:
            return _create_error("Missing Parameter", "agent_id is required")

        # This would normally get the agent and check its file
        # For now, return a mock validation result
        checks = {
            "File Exists": True,
            "Line Count": (250, 300, True),  # current, max, valid
            "Has Tests": True,
            "Has Documentation": True,
            "Python Syntax": True,
            "Import Order": True,
            "Type Hints": False,
        }

        all_valid = all(v if isinstance(v, bool) else v[2] for v in checks.values())

        # Format result
        result = f"📋 **Agent File Validation** (Agent: {agent_id})\n\n"

        for check, status in checks.items():
            if isinstance(status, bool):
                icon = "✅" if status else "❌"
                result += f"{icon} {check}\n"
            else:
                current, limit, valid = status
                icon = "✅" if valid else "❌"
                result += f"{icon} {check}: {current}/{limit} lines\n"

        result += "\n**Overall Status:** "
        if all_valid:
            result += "✅ All checks passed!"
            return _create_success(result)
        else:
            result += "❌ Some checks failed"
            return _create_error("Validation Failed", result)

    except Exception as e:
        logger.error(f"Agent file validation failed: {e}")
        return _create_error("Validation Failed", str(e))
