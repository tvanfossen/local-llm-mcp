"""Write File MCP Tool

Responsibilities:
- Write content to files with workspace safety checks
- Support both absolute and relative paths
- Create directories as needed
- Handle file overwriting with confirmation
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


async def write_file(args: dict[str, Any]) -> dict[str, Any]:
    """Write content to file with workspace safety checks"""
    try:
        file_path = args.get("file_path")
        content = args.get("content", "")
        overwrite = args.get("overwrite", False)
        create_dirs = args.get("create_dirs", True)
        encoding = args.get("encoding", "utf-8")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(file_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if file exists and handle overwrite
        file_exists = resolved_path.exists()
        if file_exists and not overwrite:
            return _create_error(
                "File Exists", 
                f"File already exists: {file_path}. Use 'overwrite: true' to replace it."
            )
        
        # Check if path is a directory
        if resolved_path.exists() and resolved_path.is_dir():
            return _create_error("Invalid Target", f"Path is a directory, not a file: {file_path}")
        
        # Create parent directories if needed
        if create_dirs and resolved_path.parent != resolved_path:
            try:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return _create_error("Directory Creation Failed", f"Cannot create parent directories: {str(e)}")
        
        # Write content to file
        try:
            resolved_path.write_text(content, encoding=encoding)
        except Exception as e:
            return _create_error("Write Failed", f"Cannot write to file: {str(e)}")
        
        # Format success response
        file_size = resolved_path.stat().st_size
        line_count = len(content.splitlines())
        action = "overwritten" if file_exists else "created"
        
        success_msg = (
            f"✅ **File {action.title()} Successfully**\n\n"
            f"📄 **File:** `{resolved_path.name}`\n"
            f"📁 **Path:** `{resolved_path}`\n"
            f"📊 **Size:** {file_size:,} bytes | **Lines:** {line_count:,}\n"
            f"📝 **Action:** File {action}\n"
            f"🔤 **Encoding:** {encoding}"
        )
        
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        return _handle_exception(e, "Write File")


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


async def append_to_file(args: dict[str, Any]) -> dict[str, Any]:
    """Append content to an existing file"""
    try:
        file_path = args.get("file_path")
        content = args.get("content", "")
        newline = args.get("newline", True)
        encoding = args.get("encoding", "utf-8")
        
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
            return _create_error("Invalid Target", f"Path is a directory, not a file: {file_path}")
        
        # Get original file size
        original_size = resolved_path.stat().st_size
        
        # Prepare content to append
        append_content = content
        if newline and not content.endswith('\n'):
            append_content += '\n'
        
        # Append to file
        try:
            with resolved_path.open('a', encoding=encoding) as f:
                f.write(append_content)
        except Exception as e:
            return _create_error("Append Failed", f"Cannot append to file: {str(e)}")
        
        # Get new file size
        new_size = resolved_path.stat().st_size
        added_bytes = new_size - original_size
        added_lines = len(content.splitlines())
        
        success_msg = (
            f"✅ **Content Appended Successfully**\n\n"
            f"📄 **File:** `{resolved_path.name}`\n"
            f"📁 **Path:** `{resolved_path}`\n"
            f"📊 **Added:** {added_bytes:,} bytes | **Lines:** {added_lines:,}\n"
            f"📈 **Total Size:** {new_size:,} bytes\n"
            f"🔤 **Encoding:** {encoding}"
        )
        
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to append to file: {e}")
        return _handle_exception(e, "Append to File")


async def create_file(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new empty file or file with initial content"""
    try:
        file_path = args.get("file_path")
        content = args.get("content", "")
        template = args.get("template")
        encoding = args.get("encoding", "utf-8")
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(file_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if file already exists
        if resolved_path.exists():
            return _create_error("File Exists", f"File already exists: {file_path}")
        
        # Apply template if specified
        if template:
            content = _apply_template(template, resolved_path)
        
        # Create parent directories
        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return _create_error("Directory Creation Failed", f"Cannot create parent directories: {str(e)}")
        
        # Create file
        try:
            resolved_path.write_text(content, encoding=encoding)
        except Exception as e:
            return _create_error("Creation Failed", f"Cannot create file: {str(e)}")
        
        # Format success response
        file_size = resolved_path.stat().st_size
        line_count = len(content.splitlines())
        
        success_msg = (
            f"✅ **File Created Successfully**\n\n"
            f"📄 **File:** `{resolved_path.name}`\n"
            f"📁 **Path:** `{resolved_path}`\n"
            f"📊 **Size:** {file_size:,} bytes | **Lines:** {line_count:,}\n"
            f"🔤 **Encoding:** {encoding}"
        )
        
        if template:
            success_msg += f"\n🎯 **Template:** {template}"
        
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to create file: {e}")
        return _handle_exception(e, "Create File")


def _apply_template(template: str, file_path: Path) -> str:
    """Apply file template based on type"""
    templates = {
        "python": f'''#!/usr/bin/env python3
"""
{file_path.stem} - Module description

Created: {_get_current_timestamp()}
"""


def main():
    """Main function"""
    pass


if __name__ == "__main__":
    main()
''',
        "javascript": f'''/**
 * {file_path.stem} - Module description
 * 
 * Created: {_get_current_timestamp()}
 */


function main() {{
    // Main function
}}


if (require.main === module) {{
    main();
}}


module.exports = {{ main }};
''',
        "html": f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_path.stem}</title>
</head>
<body>
    <h1>{file_path.stem}</h1>
    <!-- Content goes here -->
</body>
</html>
''',
        "markdown": f'''# {file_path.stem}

## Description

Brief description of the document.

## Contents

- Item 1
- Item 2
- Item 3

## Created

{_get_current_timestamp()}
''',
        "readme": f'''# {file_path.parent.name}

## Description

Brief description of the project.

## Installation

```bash
# Installation instructions
```

## Usage

```bash
# Usage examples
```

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
''',
    }
    
    return templates.get(template.lower(), "")


def _get_current_timestamp() -> str:
    """Get current timestamp for templates"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")