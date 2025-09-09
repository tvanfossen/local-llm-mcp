"""Generate From Template MCP Tool

Responsibilities:
- Generate code from Jinja2 templates
- Support template variables and configuration
- Integrate with existing template_generator.py
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


async def generate_from_template(args: dict[str, Any]) -> dict[str, Any]:
    """Generate code from a template"""
    try:
        template_name = args.get("template_name")
        output_path = args.get("output_path")
        variables = args.get("variables", {})
        template_type = args.get("template_type", "function")
        overwrite = args.get("overwrite", False)
        
        if not template_name:
            return _create_error("Missing Parameter", "Template name is required")
        
        if not output_path:
            return _create_error("Missing Parameter", "Output path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve template and output paths
        templates_dir = workspace_root / "templates"
        if not templates_dir.exists():
            return _create_error("Templates Not Found", f"Templates directory does not exist: {templates_dir}")
        
        # Resolve output path
        output_file = _resolve_output_path(output_path, workspace_root)
        if isinstance(output_file, dict):  # Error response
            return output_file
        
        # Initialize Jinja2 environment
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False  # We want raw code output
        )
        
        # Generate from template
        result = await _generate_template_content(
            env, template_name, template_type, variables, output_file, overwrite
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate from template: {e}")
        return _handle_exception(e, "Generate From Template")


async def generate_function_scaffold(args: dict[str, Any]) -> dict[str, Any]:
    """Generate a complete function scaffold with multiple files"""
    try:
        function_path = args.get("function_path")
        variables = args.get("variables", {})
        
        if not function_path:
            return _create_error("Missing Parameter", "Function path is required (e.g., 'src/domain/category/function')")
        
        # Validate function path format
        path_parts = Path(function_path).parts
        if len(path_parts) < 4 or path_parts[0] != "src":
            return _create_error("Invalid Path", "Function path must be in format: src/domain/category/function")
        
        domain = path_parts[1]
        category = path_parts[2]
        function_name = path_parts[3]
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Create target directory
        target_dir = workspace_root / function_path
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare template context
        from datetime import datetime
        context = {
            "function_name": function_name,
            "domain": domain,
            "category": category,
            "function_path": function_path,
            "generation_date": datetime.now().isoformat(),
            **variables,
        }
        
        # Initialize Jinja2 environment
        templates_dir = workspace_root / "templates"
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False
        )
        
        # Generate all scaffold files
        scaffold_files = [
            ("function/function.py.j2", f"{function_name}.py"),
            ("function/test_function.py.j2", f"test_{function_name}.py"),
            ("function/README_function.md.j2", f"README_{domain}_{category}_{function_name}.md"),
            ("function/schema_function.json.j2", f"schema_{function_name}.json"),
        ]
        
        generated_files = []
        errors = []
        
        for template_name, output_filename in scaffold_files:
            output_path = target_dir / output_filename
            try:
                template = env.get_template(template_name)
                content = template.render(context)
                
                if not output_path.exists():
                    output_path.write_text(content)
                    generated_files.append(str(output_path))
                else:
                    generated_files.append(f"{output_path} (already exists)")
                    
            except Exception as e:
                errors.append(f"Failed to generate {output_filename}: {str(e)}")
        
        # Format response
        if errors and not generated_files:
            return _create_error("Generation Failed", "\n".join(errors))
        
        success_msg = _format_scaffold_success(function_name, domain, category, target_dir, generated_files, errors)
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to generate function scaffold: {e}")
        return _handle_exception(e, "Generate Function Scaffold")


def _resolve_output_path(output_path: str, workspace_root: Path) -> Path | dict[str, Any]:
    """Resolve and validate output path"""
    try:
        path = Path(output_path)
        
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
                f"Output path is outside workspace: {output_path}"
            )
        
        return resolved_path
        
    except Exception as e:
        return _create_error("Path Error", f"Invalid output path: {output_path} - {str(e)}")


async def _generate_template_content(
    env: Environment, 
    template_name: str, 
    template_type: str,
    variables: dict,
    output_file: Path,
    overwrite: bool
) -> dict[str, Any]:
    """Generate content from template"""
    try:
        # Construct full template path
        if template_type == "function":
            full_template_name = f"function/{template_name}"
        else:
            full_template_name = template_name
        
        # Check if template exists
        try:
            template = env.get_template(full_template_name)
        except TemplateError as e:
            return _create_error("Template Not Found", f"Template '{full_template_name}' not found: {str(e)}")
        
        # Check if output file exists
        if output_file.exists() and not overwrite:
            return _create_error("File Exists", f"Output file already exists: {output_file}. Use 'overwrite: true' to replace.")
        
        # Render template
        try:
            content = template.render(variables)
        except TemplateError as e:
            return _create_error("Template Render Error", f"Failed to render template: {str(e)}")
        
        # Create parent directories
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        output_file.write_text(content)
        
        # Format success response
        file_size = output_file.stat().st_size
        line_count = len(content.splitlines())
        
        success_msg = (
            f"✅ **Template Generated Successfully**\n\n"
            f"📄 **Template:** `{full_template_name}`\n"
            f"📁 **Output:** `{output_file}`\n"
            f"📊 **Size:** {file_size:,} bytes | **Lines:** {line_count:,}\n"
            f"🔧 **Variables:** {len(variables)} provided"
        )
        
        if variables:
            var_list = "\n".join([f"   • {k}: {v}" for k, v in list(variables.items())[:5]])
            if len(variables) > 5:
                var_list += f"\n   • ... and {len(variables) - 5} more"
            success_msg += f"\n\n**Variables Used:**\n{var_list}"
        
        return _create_success(success_msg)
        
    except Exception as e:
        return _create_error("Generation Error", f"Failed to generate template: {str(e)}")


def _format_scaffold_success(
    function_name: str, 
    domain: str, 
    category: str, 
    target_dir: Path, 
    generated_files: list[str], 
    errors: list[str]
) -> str:
    """Format success message for scaffold generation"""
    success_msg = (
        f"✅ **Function Scaffold Generated**\n\n"
        f"🎯 **Function:** `{function_name}`\n"
        f"🏠 **Domain:** `{domain}`\n"
        f"📂 **Category:** `{category}`\n"
        f"📍 **Location:** `{target_dir}`\n\n"
        f"📄 **Generated Files:** ({len(generated_files)})"
    )
    
    for file_path in generated_files:
        success_msg += f"\n   • {file_path}"
    
    if errors:
        success_msg += f"\n\n⚠️ **Warnings:** ({len(errors)})"
        for error in errors:
            success_msg += f"\n   • {error}"
    
    return success_msg


async def render_template_preview(args: dict[str, Any]) -> dict[str, Any]:
    """Preview template rendering without saving to file"""
    try:
        template_name = args.get("template_name")
        variables = args.get("variables", {})
        template_type = args.get("template_type", "function")
        max_lines = args.get("max_lines", 50)
        
        if not template_name:
            return _create_error("Missing Parameter", "Template name is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Initialize Jinja2 environment
        templates_dir = workspace_root / "templates"
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False
        )
        
        # Construct full template path
        if template_type == "function":
            full_template_name = f"function/{template_name}"
        else:
            full_template_name = template_name
        
        # Render template
        try:
            template = env.get_template(full_template_name)
            content = template.render(variables)
        except TemplateError as e:
            return _create_error("Template Error", f"Failed to render template: {str(e)}")
        
        # Truncate if too long
        lines = content.splitlines()
        if len(lines) > max_lines:
            preview_lines = lines[:max_lines]
            truncated = True
        else:
            preview_lines = lines
            truncated = False
        
        preview_content = "\n".join(preview_lines)
        
        # Format response
        preview_msg = (
            f"👁️ **Template Preview**\n\n"
            f"📄 **Template:** `{full_template_name}`\n"
            f"📊 **Total Lines:** {len(lines)}"
        )
        
        if truncated:
            preview_msg += f" (showing first {max_lines})"
        
        preview_msg += f"\n🔧 **Variables:** {len(variables)} provided\n\n"
        preview_msg += f"```\n{preview_content}\n```"
        
        if truncated:
            preview_msg += f"\n\n*... {len(lines) - max_lines} more lines truncated*"
        
        return _create_success(preview_msg)
        
    except Exception as e:
        logger.error(f"Failed to preview template: {e}")
        return _handle_exception(e, "Template Preview")