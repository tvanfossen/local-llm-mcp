"""List Templates MCP Tool

Responsibilities:
- List available Jinja2 templates
- Show template details and metadata
- Support filtering by template type
- Return standardized MCP response format
"""

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

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


async def list_templates(args: dict[str, Any] = None) -> dict[str, Any]:
    """List all available templates"""
    try:
        if args is None:
            args = {}
            
        template_type = args.get("template_type")
        show_details = args.get("show_details", True)
        include_content = args.get("include_content", False)
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Check if templates directory exists
        templates_dir = workspace_root / "templates"
        if not templates_dir.exists():
            return _create_error("Templates Not Found", f"Templates directory does not exist: {templates_dir}")
        
        # Scan for templates
        templates_info = _scan_templates(templates_dir, template_type, include_content)
        
        if not templates_info:
            filter_msg = f" of type '{template_type}'" if template_type else ""
            return _create_success(f"📄 **Templates Directory:** `{templates_dir}`\n\nNo templates found{filter_msg}.")
        
        # Format listing
        formatted_listing = _format_templates_listing(templates_dir, templates_info, show_details)
        
        return _create_success(formatted_listing)
        
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return _handle_exception(e, "List Templates")


def _scan_templates(templates_dir: Path, template_type: str = None, include_content: bool = False) -> list[dict]:
    """Scan templates directory for all templates"""
    templates_info = []
    
    try:
        # Find all .j2 files
        for template_file in templates_dir.rglob("*.j2"):
            try:
                relative_path = template_file.relative_to(templates_dir)
                template_name = str(relative_path)
                
                # Extract template type from path
                path_parts = relative_path.parts
                detected_type = path_parts[0] if path_parts else "unknown"
                
                # Filter by type if specified
                if template_type and detected_type != template_type:
                    continue
                
                # Get template info
                template_info = _get_template_info(template_file, template_name, detected_type, include_content)
                if template_info:
                    templates_info.append(template_info)
                    
            except Exception as e:
                logger.warning(f"Error processing template {template_file}: {e}")
                continue
        
        # Sort by type then name
        templates_info.sort(key=lambda x: (x['type'], x['name']))
        
    except Exception as e:
        logger.error(f"Error scanning templates directory: {e}")
    
    return templates_info


def _get_template_info(template_file: Path, template_name: str, template_type: str, include_content: bool) -> dict | None:
    """Get information about a template file"""
    try:
        stat = template_file.stat()
        
        # Read template content to extract metadata
        content = template_file.read_text(encoding='utf-8')
        metadata = _extract_template_metadata(content)
        
        # Detect variables used in template
        variables = _extract_template_variables(content)
        
        info = {
            'name': template_name,
            'type': template_type,
            'file_path': str(template_file),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'line_count': len(content.splitlines()),
            'variables': variables,
            'metadata': metadata,
            'description': metadata.get('description', 'No description available')
        }
        
        if include_content:
            info['content'] = content
        
        return info
        
    except Exception as e:
        logger.warning(f"Error getting template info for {template_file}: {e}")
        return None


def _extract_template_metadata(content: str) -> dict:
    """Extract metadata from template comments"""
    metadata = {}
    
    # Look for metadata in comments at the top of the file
    lines = content.splitlines()
    in_metadata = False
    
    for line in lines:
        line = line.strip()
        
        # Check for metadata block markers
        if line.startswith("{#") and "metadata" in line.lower():
            in_metadata = True
            continue
        elif line.startswith("#}") and in_metadata:
            break
        elif in_metadata:
            # Parse key-value pairs
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().strip("{#").strip()
                value = value.strip().strip("#}")
                metadata[key] = value
        
        # Also look for simple description comments
        elif line.startswith("{#") and line.endswith("#}"):
            comment = line[2:-2].strip()
            if "description" not in metadata and len(comment) > 10:
                metadata['description'] = comment
    
    return metadata


def _extract_template_variables(content: str) -> list[str]:
    """Extract variables used in the template"""
    import re
    
    # Find all Jinja2 variable references {{ variable_name }}
    variable_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}'
    variables = set()
    
    for match in re.finditer(variable_pattern, content):
        var_name = match.group(1)
        # Only include simple variable names, not complex expressions
        if '(' not in var_name and '[' not in var_name and '|' not in var_name:
            variables.add(var_name.split('.')[0])  # Get root variable name
    
    return sorted(list(variables))


def _format_templates_listing(templates_dir: Path, templates_info: list[dict], show_details: bool) -> str:
    """Format templates listing for display"""
    # Group by type
    by_type = {}
    for template in templates_info:
        template_type = template['type']
        if template_type not in by_type:
            by_type[template_type] = []
        by_type[template_type].append(template)
    
    # Header
    total_templates = len(templates_info)
    total_types = len(by_type)
    
    header = (
        f"📄 **Templates Directory:** `{templates_dir}`\n\n"
        f"📊 **Summary:** {total_templates} templates across {total_types} types\n\n"
    )
    
    # List by type
    sections = []
    for template_type in sorted(by_type.keys()):
        templates = by_type[template_type]
        section = f"## 📂 {template_type.title()} Templates ({len(templates)})\n"
        
        for template in templates:
            if show_details:
                section += _format_template_entry_detailed(template)
            else:
                section += _format_template_entry_simple(template)
        
        sections.append(section)
    
    return header + "\n".join(sections)


def _format_template_entry_simple(template: dict) -> str:
    """Format a simple template entry"""
    return f"📄 **`{template['name']}`** - {template['description']}\n"


def _format_template_entry_detailed(template: dict) -> str:
    """Format a detailed template entry"""
    # Format timestamp
    import datetime
    modified_time = datetime.datetime.fromtimestamp(template['modified'])
    time_str = modified_time.strftime("%Y-%m-%d %H:%M")
    
    # Format file size
    size_str = _format_file_size(template['size'])
    
    entry = (
        f"📄 **`{template['name']}`**\n"
        f"   📝 {template['description']}\n"
        f"   📊 {size_str} | 📏 {template['line_count']} lines | 📅 {time_str}\n"
    )
    
    # Add variables if any
    if template['variables']:
        variables_str = ", ".join(template['variables'][:5])
        if len(template['variables']) > 5:
            variables_str += f" (+{len(template['variables']) - 5} more)"
        entry += f"   🔧 Variables: {variables_str}\n"
    
    return entry + "\n"


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 bytes"
    
    size_names = ["bytes", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 1)
    
    if s.is_integer():
        s = int(s)
    
    return f"{s} {size_names[i]}"


async def get_template_details(args: dict[str, Any]) -> dict[str, Any]:
    """Get detailed information about a specific template"""
    try:
        template_name = args.get("template_name")
        include_content = args.get("include_content", False)
        
        if not template_name:
            return _create_error("Missing Parameter", "Template name is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Find template file
        templates_dir = workspace_root / "templates"
        template_file = templates_dir / template_name
        
        if not template_file.exists():
            return _create_error("Template Not Found", f"Template does not exist: {template_name}")
        
        if not template_file.is_file():
            return _create_error("Invalid Template", f"Path is not a file: {template_name}")
        
        # Get template info
        template_type = template_file.parent.name if template_file.parent != templates_dir else "root"
        template_info = _get_template_info(template_file, template_name, template_type, include_content)
        
        if not template_info:
            return _create_error("Read Error", f"Cannot read template: {template_name}")
        
        # Format detailed information
        details = _format_template_details(template_info)
        
        return _create_success(details)
        
    except Exception as e:
        logger.error(f"Failed to get template details: {e}")
        return _handle_exception(e, "Get Template Details")


def _format_template_details(template: dict) -> str:
    """Format detailed template information"""
    import datetime
    
    modified_time = datetime.datetime.fromtimestamp(template['modified'])
    time_str = modified_time.strftime("%Y-%m-%d %H:%M:%S")
    size_str = _format_file_size(template['size'])
    
    details = (
        f"📄 **Template Details**\n\n"
        f"📝 **Name:** `{template['name']}`\n"
        f"📂 **Type:** {template['type']}\n"
        f"📁 **Path:** `{template['file_path']}`\n"
        f"📊 **Size:** {size_str} | **Lines:** {template['line_count']}\n"
        f"📅 **Modified:** {time_str}\n"
        f"📖 **Description:** {template['description']}\n"
    )
    
    # Add variables information
    if template['variables']:
        variables_list = "\n".join([f"   • {var}" for var in template['variables']])
        details += f"\n🔧 **Variables:** ({len(template['variables'])})\n{variables_list}\n"
    else:
        details += f"\n🔧 **Variables:** None\n"
    
    # Add metadata if available
    if template['metadata']:
        metadata_items = []
        for key, value in template['metadata'].items():
            if key != 'description':  # Already shown above
                metadata_items.append(f"   • {key}: {value}")
        
        if metadata_items:
            details += f"\n📋 **Metadata:**\n" + "\n".join(metadata_items) + "\n"
    
    # Add content if requested
    if 'content' in template:
        content = template['content']
        if len(content) > 1000:
            content = content[:1000] + "\n... (truncated)"
        details += f"\n📄 **Content:**\n```jinja2\n{content}\n```"
    
    return details