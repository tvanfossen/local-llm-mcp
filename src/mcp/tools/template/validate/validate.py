"""Validate Template MCP Tool

Responsibilities:
- Validate Jinja2 template syntax and structure
- Check template variables and dependencies
- Validate generated code against schemas
- Return standardized MCP response format
"""

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, meta

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


async def validate_template(args: dict[str, Any]) -> dict[str, Any]:
    """Validate a template's syntax and structure"""
    try:
        template_name = args.get("template_name")
        test_variables = args.get("test_variables", {})
        check_syntax_only = args.get("check_syntax_only", False)
        
        if not template_name:
            return _create_error("Missing Parameter", "Template name is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Find template file
        templates_dir = workspace_root / "templates"
        template_file = templates_dir / template_name
        
        if not template_file.exists():
            return _create_error("Template Not Found", f"Template does not exist: {template_name}")
        
        # Initialize Jinja2 environment
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False
        )
        
        # Perform validation
        validation_result = _perform_template_validation(
            env, template_name, template_file, test_variables, check_syntax_only
        )
        
        # Format result
        if validation_result["is_valid"]:
            success_msg = _format_validation_success(validation_result)
            return _create_success(success_msg)
        else:
            error_msg = _format_validation_errors(validation_result)
            return _create_error("Validation Failed", error_msg)
        
    except Exception as e:
        logger.error(f"Failed to validate template: {e}")
        return _handle_exception(e, "Validate Template")


def _perform_template_validation(
    env: Environment, 
    template_name: str, 
    template_file: Path, 
    test_variables: dict,
    check_syntax_only: bool
) -> dict:
    """Perform comprehensive template validation"""
    validation_result = {
        "template_name": template_name,
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "syntax_valid": False,
        "variables_found": [],
        "missing_variables": [],
        "render_successful": False,
        "generated_content": None,
        "line_count": 0,
        "file_size": 0
    }
    
    try:
        # Get file stats
        stat = template_file.stat()
        validation_result["file_size"] = stat.st_size
        
        # Read template content
        content = template_file.read_text(encoding='utf-8')
        validation_result["line_count"] = len(content.splitlines())
        
        # 1. Syntax validation
        try:
            template = env.get_template(template_name)
            validation_result["syntax_valid"] = True
        except TemplateError as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Syntax error: {str(e)}")
            return validation_result
        
        # 2. Variable analysis
        try:
            # Parse template to find variables
            ast = env.parse(content)
            variables = meta.find_undeclared_variables(ast)
            validation_result["variables_found"] = sorted(list(variables))
            
            # Check for missing variables in test_variables
            missing_vars = variables - set(test_variables.keys())
            validation_result["missing_variables"] = sorted(list(missing_vars))
            
            if missing_vars:
                validation_result["warnings"].append(
                    f"Missing test variables: {', '.join(missing_vars)}"
                )
        except Exception as e:
            validation_result["warnings"].append(f"Variable analysis failed: {str(e)}")
        
        # 3. Render test (if not syntax-only)
        if not check_syntax_only:
            try:
                # Provide default values for missing variables
                render_variables = test_variables.copy()
                for var in validation_result["missing_variables"]:
                    render_variables[var] = f"[{var}]"  # Placeholder value
                
                generated_content = template.render(render_variables)
                validation_result["render_successful"] = True
                validation_result["generated_content"] = generated_content
                
                # Validate generated content
                content_validation = _validate_generated_content(generated_content)
                validation_result["warnings"].extend(content_validation["warnings"])
                
            except TemplateError as e:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Render error: {str(e)}")
        
        # 4. Template-specific validations
        template_warnings = _validate_template_best_practices(content)
        validation_result["warnings"].extend(template_warnings)
        
    except Exception as e:
        validation_result["is_valid"] = False
        validation_result["errors"].append(f"Validation error: {str(e)}")
    
    return validation_result


def _validate_generated_content(content: str) -> dict:
    """Validate the generated content for common issues"""
    warnings = []
    
    # Check for common issues
    lines = content.splitlines()
    
    # Check line length (Python convention)
    long_lines = [i+1 for i, line in enumerate(lines) if len(line) > 100]
    if long_lines:
        warnings.append(f"Lines exceed 100 characters: {long_lines[:5]}")
    
    # Check for TODO/FIXME markers
    todo_lines = [i+1 for i, line in enumerate(lines) if 'TODO' in line or 'FIXME' in line]
    if todo_lines:
        warnings.append(f"TODO/FIXME markers found on lines: {todo_lines[:3]}")
    
    # Check for empty functions/classes
    if 'def ' in content and 'pass' in content:
        warnings.append("Generated code contains empty functions with 'pass'")
    
    # Check for missing docstrings in Python code
    if content.strip().startswith('def ') or content.strip().startswith('class '):
        if '"""' not in content and "'''" not in content:
            warnings.append("Python code missing docstrings")
    
    return {"warnings": warnings}


def _validate_template_best_practices(content: str) -> list[str]:
    """Check template against best practices"""
    warnings = []
    
    # Check for hardcoded values that should be variables
    import re
    
    # Look for potential hardcoded strings
    string_literals = re.findall(r'"([^"]{10,})"', content)
    if len(string_literals) > 3:
        warnings.append("Many string literals found - consider using variables")
    
    # Check for missing metadata comments
    if "{#" not in content:
        warnings.append("Template missing metadata comments")
    
    # Check for complex logic that might belong in Python
    if content.count("{% if") > 3:
        warnings.append("Complex conditional logic - consider moving to Python")
    
    # Check for deeply nested blocks
    indent_levels = []
    for line in content.splitlines():
        if "{%" in line:
            if any(keyword in line for keyword in ["if", "for", "macro"]):
                # Count nesting level by counting leading whitespace
                indent = len(line) - len(line.lstrip())
                indent_levels.append(indent)
    
    if indent_levels and max(indent_levels) > 8:
        warnings.append("Deeply nested template blocks detected")
    
    return warnings


async def validate_template_output(args: dict[str, Any]) -> dict[str, Any]:
    """Validate template output against schema or rules"""
    try:
        template_name = args.get("template_name")
        variables = args.get("variables", {})
        schema_file = args.get("schema_file")
        validation_rules = args.get("validation_rules", [])
        
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
        
        # Render template
        try:
            template = env.get_template(template_name)
            generated_content = template.render(variables)
        except TemplateError as e:
            return _create_error("Render Failed", f"Cannot render template: {str(e)}")
        
        # Perform output validation
        validation_results = []
        
        # 1. Schema validation (if schema file provided)
        if schema_file:
            schema_result = _validate_against_schema(generated_content, schema_file, workspace_root)
            validation_results.append(schema_result)
        
        # 2. Custom validation rules
        for rule in validation_rules:
            rule_result = _validate_against_rule(generated_content, rule)
            validation_results.append(rule_result)
        
        # 3. Default content validation
        default_result = _validate_generated_content(generated_content)
        if default_result["warnings"]:
            validation_results.append({
                "rule_name": "content_quality",
                "passed": True,
                "warnings": default_result["warnings"]
            })
        
        # Format results
        success_msg = _format_output_validation_results(template_name, validation_results, generated_content)
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to validate template output: {e}")
        return _handle_exception(e, "Validate Template Output")


def _validate_against_schema(content: str, schema_file: str, workspace_root: Path) -> dict:
    """Validate content against a JSON schema"""
    result = {
        "rule_name": "schema_validation",
        "passed": False,
        "errors": [],
        "warnings": []
    }
    
    try:
        schema_path = workspace_root / schema_file
        if not schema_path.exists():
            result["errors"].append(f"Schema file not found: {schema_file}")
            return result
        
        # For now, just check if it's valid JSON (if content looks like JSON)
        content_stripped = content.strip()
        if content_stripped.startswith('{') and content_stripped.endswith('}'):
            try:
                json.loads(content)
                result["passed"] = True
            except json.JSONDecodeError as e:
                result["errors"].append(f"Invalid JSON: {str(e)}")
        else:
            result["warnings"].append("Content does not appear to be JSON")
            result["passed"] = True  # Not a JSON template
        
    except Exception as e:
        result["errors"].append(f"Schema validation error: {str(e)}")
    
    return result


def _validate_against_rule(content: str, rule: dict) -> dict:
    """Validate content against a custom rule"""
    result = {
        "rule_name": rule.get("name", "custom_rule"),
        "passed": False,
        "errors": [],
        "warnings": []
    }
    
    try:
        rule_type = rule.get("type", "contains")
        rule_value = rule.get("value", "")
        
        if rule_type == "contains":
            if rule_value in content:
                result["passed"] = True
            else:
                result["errors"].append(f"Content must contain: {rule_value}")
        
        elif rule_type == "not_contains":
            if rule_value not in content:
                result["passed"] = True
            else:
                result["errors"].append(f"Content must not contain: {rule_value}")
        
        elif rule_type == "regex":
            import re
            if re.search(rule_value, content):
                result["passed"] = True
            else:
                result["errors"].append(f"Content must match regex: {rule_value}")
        
        elif rule_type == "line_count":
            line_count = len(content.splitlines())
            max_lines = rule.get("max", float('inf'))
            min_lines = rule.get("min", 0)
            
            if min_lines <= line_count <= max_lines:
                result["passed"] = True
            else:
                result["errors"].append(f"Line count {line_count} not in range {min_lines}-{max_lines}")
        
        else:
            result["warnings"].append(f"Unknown rule type: {rule_type}")
            result["passed"] = True
        
    except Exception as e:
        result["errors"].append(f"Rule validation error: {str(e)}")
    
    return result


def _format_validation_success(result: dict) -> str:
    """Format successful validation result"""
    msg = (
        f"✅ **Template Validation Passed**\n\n"
        f"📄 **Template:** `{result['template_name']}`\n"
        f"📊 **Size:** {result['file_size']:,} bytes | **Lines:** {result['line_count']}\n"
        f"✅ **Syntax:** Valid\n"
        f"🔧 **Variables:** {len(result['variables_found'])} found"
    )
    
    if result["variables_found"]:
        vars_str = ", ".join(result["variables_found"][:5])
        if len(result["variables_found"]) > 5:
            vars_str += f" (+{len(result['variables_found']) - 5} more)"
        msg += f"\n   • {vars_str}"
    
    if result["render_successful"]:
        msg += f"\n🎯 **Render:** Successful"
    
    if result["warnings"]:
        msg += f"\n\n⚠️ **Warnings:** ({len(result['warnings'])})"
        for warning in result["warnings"][:3]:
            msg += f"\n   • {warning}"
        if len(result["warnings"]) > 3:
            msg += f"\n   • ... and {len(result['warnings']) - 3} more"
    
    return msg


def _format_validation_errors(result: dict) -> str:
    """Format validation errors"""
    msg = f"Template: `{result['template_name']}`\n\n"
    
    if result["errors"]:
        msg += f"**Errors:** ({len(result['errors'])})\n"
        for error in result["errors"]:
            msg += f"   • {error}\n"
    
    if result["warnings"]:
        msg += f"\n**Warnings:** ({len(result['warnings'])})\n"
        for warning in result["warnings"]:
            msg += f"   • {warning}\n"
    
    return msg


def _format_output_validation_results(template_name: str, results: list[dict], content: str) -> str:
    """Format output validation results"""
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    msg = (
        f"✅ **Template Output Validation**\n\n"
        f"📄 **Template:** `{template_name}`\n"
        f"📊 **Generated:** {len(content.splitlines())} lines, {len(content):,} characters\n"
        f"🧪 **Tests:** {passed_count}/{total_count} passed\n"
    )
    
    if results:
        msg += "\n**Validation Results:**"
        for result in results:
            status = "✅" if result["passed"] else "❌"
            msg += f"\n   {status} {result['rule_name']}"
            
            if result.get("errors"):
                for error in result["errors"][:2]:
                    msg += f"\n      • {error}"
            
            if result.get("warnings"):
                for warning in result["warnings"][:2]:
                    msg += f"\n      ⚠️ {warning}"
    
    return msg