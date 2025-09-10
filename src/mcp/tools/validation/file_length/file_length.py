"""File Length Validation MCP Tool

Responsibilities:
- Validate file line counts against limits
- Check schema compliance for file sizes
- Report violations with details
- Support batch file validation

Generated from template on 2025-01-09T10:00:00
Template version: 1.0.0
"""

import logging
from pathlib import Path
from typing import Any

from src.core.utils import create_success, create_error

logger = logging.getLogger(__name__)




async def validate_file_length(args: dict[str, Any]) -> dict[str, Any]:
    """Validate file line counts against schema limits"""
    try:
        file_paths = args.get("file_paths", [])
        max_lines = args.get("max_lines", 300)

        if not file_paths:
            return create_error("No Files", "No file paths provided")

        violations = []
        valid_files = []

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                violations.append(f"• {file_path}: File not found")
                continue

            try:
                with open(path) as f:
                    line_count = len(f.readlines())

                if line_count > max_lines:
                    violations.append(
                        f"• {file_path}: {line_count} lines (exceeds {max_lines} limit by {line_count - max_lines})"
                    )
                else:
                    valid_files.append(f"• {file_path}: {line_count} lines ✅")
            except Exception as e:
                violations.append(f"• {file_path}: Error reading file - {e}")

        # Format result
        if not violations:
            result = f"✅ **All Files Valid** (max {max_lines} lines)\n\n"
            result += "**Validated Files:**\n"
            result += "\n".join(valid_files)
            return create_success(result)
        else:
            result = "❌ **File Length Violations Found**\n\n"
            result += "**Violations:**\n"
            result += "\n".join(violations)

            if valid_files:
                result += "\n\n**Valid Files:**\n"
                result += "\n".join(valid_files)

            return create_error("Length Violations", result)

    except Exception as e:
        logger.error(f"File length validation failed: {e}")
        return create_error("Validation Failed", str(e))
