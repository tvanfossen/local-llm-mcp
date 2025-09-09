"""Documentation Enhancement Tool - Add missing docstrings and type hints

Responsibilities:
- Generate comprehensive docstrings for functions and classes
- Add missing type hints using local LLM analysis
- Format docstrings according to style guides (Google, NumPy, Sphinx)
- Generate module-level documentation
- Create inline comments for complex code sections
- Integration with local LLM for intelligent documentation generation

Phase 5: Self-Improvement MCP Tools
"""

import ast
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.core.config.manager.manager import ConfigManager

logger = logging.getLogger(__name__)


def _create_success(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create successful MCP response"""
    content = [{"type": "text", "text": message}]
    if data:
        content.append({"type": "text", "text": f"```json\n{data}\n```"})
    return {"content": content, "isError": False}


def _create_error(message: str) -> Dict[str, Any]:
    """Create error MCP response"""
    return {"content": [{"type": "text", "text": f"❌ **Documentation Error:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> Dict[str, Any]:
    """Handle exceptions with proper MCP formatting"""
    logger.error(f"Exception in {context}: {str(e)}", exc_info=True)
    return _create_error(f"{context}: {str(e)}")


class DocumentationAnalyzer:
    """Intelligent documentation analyzer and generator"""
    
    def __init__(self, style: str = "google"):
        self.config_manager = ConfigManager()
        self.style = style  # google, numpy, sphinx
        self.missing_docs = []
        self.missing_types = []
        
    def analyze_documentation_gaps(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze file for missing documentation"""
        if file_path.suffix == '.py':
            return self._analyze_python_documentation(content)
        elif file_path.suffix in ['.js', '.ts']:
            return self._analyze_javascript_documentation(content)
        else:
            return {"error": f"Documentation analysis not supported for {file_path.suffix} files"}
    
    def _analyze_python_documentation(self, content: str) -> Dict[str, Any]:
        """Analyze Python file for documentation gaps"""
        analysis = {
            "missing_docstrings": [],
            "missing_type_hints": [],
            "documentation_coverage": 0.0,
            "type_hint_coverage": 0.0,
            "suggestions": []
        }
        
        try:
            tree = ast.parse(content)
            
            # Find functions and classes without docstrings
            functions_and_classes = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    functions_and_classes.append(node)
            
            # Check for docstrings
            total_items = len(functions_and_classes)
            documented_items = 0
            
            for node in functions_and_classes:
                has_docstring = (len(node.body) > 0 and 
                               isinstance(node.body[0], ast.Expr) and 
                               isinstance(node.body[0].value, ast.Constant) and 
                               isinstance(node.body[0].value.value, str))
                
                if has_docstring:
                    documented_items += 1
                else:
                    analysis["missing_docstrings"].append({
                        "name": node.name,
                        "type": "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class",
                        "line": node.lineno,
                        "parameters": self._extract_function_signature(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
                    })
            
            # Calculate documentation coverage
            analysis["documentation_coverage"] = (documented_items / total_items * 100) if total_items > 0 else 100.0
            
            # Check for type hints
            functions = [n for n in functions_and_classes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            total_functions = len(functions)
            typed_functions = 0
            
            for func in functions:
                missing_hints = self._check_type_hints(func)
                if not missing_hints:
                    typed_functions += 1
                else:
                    analysis["missing_type_hints"].append({
                        "name": func.name,
                        "line": func.lineno,
                        "missing_hints": missing_hints
                    })
            
            # Calculate type hint coverage
            analysis["type_hint_coverage"] = (typed_functions / total_functions * 100) if total_functions > 0 else 100.0
            
            # Generate suggestions
            analysis["suggestions"] = self._generate_documentation_suggestions(analysis)
            
        except SyntaxError as e:
            analysis["error"] = f"Syntax error: {e.msg} at line {e.lineno}"
        
        return analysis
    
    def _analyze_javascript_documentation(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript file for documentation gaps"""
        analysis = {
            "missing_docstrings": [],
            "documentation_coverage": 0.0,
            "suggestions": ["Consider using JSDoc comments for JavaScript documentation"]
        }
        
        # Simple regex-based analysis for JavaScript
        function_patterns = [
            r'function\s+(\w+)\s*\(',
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
            r'(\w+)\s*:\s*function\s*\(',
            r'class\s+(\w+)'
        ]
        
        functions_found = []
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            for pattern in function_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    functions_found.append({"name": match, "line": i})
        
        # Check for JSDoc comments
        jsdoc_pattern = r'/\*\*[\s\S]*?\*/'
        jsdoc_comments = re.findall(jsdoc_pattern, content)
        
        documented = len(jsdoc_comments)
        total = len(functions_found)
        
        analysis["documentation_coverage"] = (documented / total * 100) if total > 0 else 100.0
        
        # Estimate missing documentation
        for func in functions_found[documented:]:
            analysis["missing_docstrings"].append(func)
        
        return analysis
    
    def _extract_function_signature(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Dict[str, Any]:
        """Extract function signature information"""
        signature = {
            "parameters": [],
            "returns": None,
            "is_async": isinstance(node, ast.AsyncFunctionDef)
        }
        
        # Extract parameters
        for arg in node.args.args:
            param_info = {"name": arg.arg, "type_hint": None, "default": None}
            
            if arg.annotation:
                param_info["type_hint"] = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
            
            signature["parameters"].append(param_info)
        
        # Extract defaults
        defaults_start = len(node.args.args) - len(node.args.defaults)
        for i, default in enumerate(node.args.defaults):
            param_index = defaults_start + i
            if param_index < len(signature["parameters"]):
                signature["parameters"][param_index]["default"] = ast.unparse(default) if hasattr(ast, 'unparse') else str(default)
        
        # Extract return type
        if node.returns:
            signature["returns"] = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        return signature
    
    def _check_type_hints(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> List[str]:
        """Check for missing type hints in function"""
        missing = []
        
        # Check parameters
        for arg in node.args.args:
            if not arg.annotation and arg.arg != 'self' and arg.arg != 'cls':
                missing.append(f"parameter '{arg.arg}'")
        
        # Check return type
        if not node.returns and node.name != '__init__':
            missing.append("return type")
        
        return missing
    
    def _generate_documentation_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate intelligent suggestions for improving documentation"""
        suggestions = []
        
        doc_coverage = analysis.get("documentation_coverage", 0)
        type_coverage = analysis.get("type_hint_coverage", 0)
        
        if doc_coverage < 50:
            suggestions.append("Low documentation coverage - prioritize adding docstrings to public functions")
        elif doc_coverage < 80:
            suggestions.append("Good documentation progress - focus on completing remaining functions")
        
        if type_coverage < 30:
            suggestions.append("Consider adding type hints to improve code clarity and IDE support")
        elif type_coverage < 70:
            suggestions.append("Good type hint coverage - complete remaining functions for full typing")
        
        missing_docs = len(analysis.get("missing_docstrings", []))
        if missing_docs > 10:
            suggestions.append("Many functions need documentation - consider batch documentation generation")
        
        if analysis.get("missing_type_hints"):
            suggestions.append("Use mypy or similar tools to verify type hint correctness")
        
        return suggestions
    
    def generate_docstring(self, function_info: Dict[str, Any], context: str = "") -> str:
        """Generate a docstring for a function based on its signature and context"""
        name = function_info.get("name", "function")
        signature = function_info.get("parameters", {})
        func_type = function_info.get("type", "function")
        
        if func_type == "class":
            return self._generate_class_docstring(name, context)
        else:
            return self._generate_function_docstring(name, signature, context)
    
    def _generate_function_docstring(self, name: str, signature: Dict[str, Any], context: str) -> str:
        """Generate function docstring based on style"""
        if self.style == "google":
            return self._generate_google_style_docstring(name, signature, context)
        elif self.style == "numpy":
            return self._generate_numpy_style_docstring(name, signature, context)
        else:  # sphinx
            return self._generate_sphinx_style_docstring(name, signature, context)
    
    def _generate_google_style_docstring(self, name: str, signature: Dict[str, Any], context: str) -> str:
        """Generate Google-style docstring"""
        # Infer function purpose from name
        purpose = self._infer_function_purpose(name, context)
        
        docstring = f'    """{purpose}\n\n'
        
        # Add parameters section
        parameters = signature.get("parameters", [])
        if parameters:
            docstring += "    Args:\n"
            for param in parameters:
                param_name = param.get("name", "")
                param_type = param.get("type_hint", "Any")
                param_desc = self._infer_parameter_description(param_name)
                docstring += f"        {param_name} ({param_type}): {param_desc}\n"
            docstring += "\n"
        
        # Add returns section
        returns = signature.get("returns")
        if returns and returns != "None":
            return_desc = self._infer_return_description(name, returns)
            docstring += f"    Returns:\n        {returns}: {return_desc}\n\n"
        
        # Add raises section if function might raise exceptions
        if self._might_raise_exceptions(name, context):
            docstring += "    Raises:\n        Exception: Description of when this exception is raised\n\n"
        
        docstring += '    """'
        return docstring
    
    def _generate_numpy_style_docstring(self, name: str, signature: Dict[str, Any], context: str) -> str:
        """Generate NumPy-style docstring"""
        purpose = self._infer_function_purpose(name, context)
        
        docstring = f'    """{purpose}\n\n'
        
        # Add parameters section
        parameters = signature.get("parameters", [])
        if parameters:
            docstring += "    Parameters\n    ----------\n"
            for param in parameters:
                param_name = param.get("name", "")
                param_type = param.get("type_hint", "Any")
                param_desc = self._infer_parameter_description(param_name)
                docstring += f"    {param_name} : {param_type}\n        {param_desc}\n"
            docstring += "\n"
        
        # Add returns section
        returns = signature.get("returns")
        if returns and returns != "None":
            return_desc = self._infer_return_description(name, returns)
            docstring += f"    Returns\n    -------\n    {returns}\n        {return_desc}\n\n"
        
        docstring += '    """'
        return docstring
    
    def _generate_sphinx_style_docstring(self, name: str, signature: Dict[str, Any], context: str) -> str:
        """Generate Sphinx-style docstring"""
        purpose = self._infer_function_purpose(name, context)
        
        docstring = f'    """{purpose}\n\n'
        
        # Add parameters
        parameters = signature.get("parameters", [])
        for param in parameters:
            param_name = param.get("name", "")
            param_type = param.get("type_hint", "Any")
            param_desc = self._infer_parameter_description(param_name)
            docstring += f"    :param {param_name}: {param_desc}\n"
            docstring += f"    :type {param_name}: {param_type}\n"
        
        # Add return
        returns = signature.get("returns")
        if returns and returns != "None":
            return_desc = self._infer_return_description(name, returns)
            docstring += f"    :return: {return_desc}\n"
            docstring += f"    :rtype: {returns}\n"
        
        docstring += '    """'
        return docstring
    
    def _generate_class_docstring(self, name: str, context: str) -> str:
        """Generate class docstring"""
        purpose = self._infer_class_purpose(name, context)
        
        if self.style == "google":
            docstring = f'    """{purpose}\n\n    Attributes:\n        attribute_name (type): Description of attribute.\n    """'
        elif self.style == "numpy":
            docstring = f'    """{purpose}\n\n    Attributes\n    ----------\n    attribute_name : type\n        Description of attribute.\n    """'
        else:  # sphinx
            docstring = f'    """{purpose}\n\n    :ivar attribute_name: Description of attribute\n    :vartype attribute_name: type\n    """'
        
        return docstring
    
    def _infer_function_purpose(self, name: str, context: str) -> str:
        """Infer function purpose from name and context"""
        name_lower = name.lower()
        
        # Common patterns
        if name_lower.startswith('get_'):
            return f"Get {name[4:].replace('_', ' ')}"
        elif name_lower.startswith('set_'):
            return f"Set {name[4:].replace('_', ' ')}"
        elif name_lower.startswith('create_'):
            return f"Create {name[7:].replace('_', ' ')}"
        elif name_lower.startswith('delete_') or name_lower.startswith('remove_'):
            prefix_len = 7 if name_lower.startswith('delete_') else 7
            return f"Delete {name[prefix_len:].replace('_', ' ')}"
        elif name_lower.startswith('validate_'):
            return f"Validate {name[9:].replace('_', ' ')}"
        elif name_lower.startswith('is_') or name_lower.startswith('has_'):
            prefix_len = 3 if name_lower.startswith('is_') else 4
            return f"Check if {name[prefix_len:].replace('_', ' ')}"
        elif name_lower.startswith('process_'):
            return f"Process {name[8:].replace('_', ' ')}"
        elif name_lower.startswith('handle_'):
            return f"Handle {name[7:].replace('_', ' ')}"
        elif 'test' in name_lower:
            return f"Test {name.replace('test_', '').replace('_', ' ')}"
        else:
            # Generic description
            return f"{name.replace('_', ' ').title()} function"
    
    def _infer_class_purpose(self, name: str, context: str) -> str:
        """Infer class purpose from name and context"""
        if name.endswith('Manager'):
            return f"Manager class for {name[:-7].replace('_', ' ').lower()}"
        elif name.endswith('Handler'):
            return f"Handler class for {name[:-7].replace('_', ' ').lower()}"
        elif name.endswith('Analyzer'):
            return f"Analyzer class for {name[:-8].replace('_', ' ').lower()}"
        elif name.endswith('Builder'):
            return f"Builder class for {name[:-7].replace('_', ' ').lower()}"
        elif name.endswith('Exception') or name.endswith('Error'):
            return f"Custom exception for {name.replace('Exception', '').replace('Error', '').replace('_', ' ').lower()}"
        else:
            return f"{name.replace('_', ' ')} class"
    
    def _infer_parameter_description(self, param_name: str) -> str:
        """Infer parameter description from name"""
        name_lower = param_name.lower()
        
        if 'path' in name_lower:
            return "Path to file or directory"
        elif 'file' in name_lower:
            return "File to process"
        elif 'data' in name_lower:
            return "Data to process"
        elif 'config' in name_lower:
            return "Configuration parameters"
        elif 'args' in name_lower:
            return "Arguments dictionary"
        elif 'kwargs' in name_lower:
            return "Keyword arguments"
        elif name_lower in ['id', 'uuid']:
            return "Unique identifier"
        elif 'name' in name_lower:
            return "Name identifier"
        elif 'content' in name_lower:
            return "Content to process"
        elif 'message' in name_lower:
            return "Message text"
        elif 'limit' in name_lower:
            return "Maximum number of items"
        elif 'count' in name_lower:
            return "Number of items"
        elif name_lower.startswith('is_') or name_lower.startswith('has_'):
            return "Boolean flag"
        else:
            return f"{param_name.replace('_', ' ').title()} parameter"
    
    def _infer_return_description(self, func_name: str, return_type: str) -> str:
        """Infer return value description"""
        if 'bool' in return_type.lower():
            return "True if successful, False otherwise"
        elif 'list' in return_type.lower() or 'List' in return_type:
            return "List of results"
        elif 'dict' in return_type.lower() or 'Dict' in return_type:
            return "Dictionary containing results"
        elif 'str' in return_type.lower():
            return "String result"
        elif 'int' in return_type.lower():
            return "Integer value"
        elif func_name.lower().startswith('get_'):
            return f"Retrieved {func_name[4:].replace('_', ' ')}"
        else:
            return "Function result"
    
    def _might_raise_exceptions(self, name: str, context: str) -> bool:
        """Determine if function might raise exceptions"""
        risk_indicators = [
            'file', 'path', 'read', 'write', 'open', 'save',
            'network', 'request', 'connect', 'socket',
            'parse', 'validate', 'convert', 'transform',
            'database', 'query', 'execute'
        ]
        
        name_lower = name.lower()
        context_lower = context.lower()
        
        return any(indicator in name_lower or indicator in context_lower for indicator in risk_indicators)


async def add_documentation(args: Dict[str, Any]) -> Dict[str, Any]:
    """Add missing documentation to a file"""
    try:
        file_path = args.get("file_path")
        if not file_path:
            return _create_error("file_path parameter is required")
        
        style = args.get("style", "google")  # google, numpy, sphinx
        dry_run = args.get("dry_run", True)  # Default to dry run for safety
        
        # Resolve path
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(file_path).is_absolute():
            full_path = workspace_root / file_path
        else:
            full_path = Path(file_path)
        
        # Security check
        try:
            full_path.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return _create_error(f"Path outside workspace: {file_path}")
        
        if not full_path.exists():
            return _create_error(f"File not found: {file_path}")
        
        # Read file content
        content = full_path.read_text(encoding='utf-8')
        
        # Analyze documentation gaps
        analyzer = DocumentationAnalyzer(style=style)
        analysis = analyzer.analyze_documentation_gaps(full_path, content)
        
        if "error" in analysis:
            return _create_error(analysis["error"])
        
        return _format_documentation_analysis(full_path, analysis, dry_run)
    
    except Exception as e:
        return _handle_exception(e, "add_documentation")


async def generate_type_hints(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate missing type hints for a Python file"""
    try:
        file_path = args.get("file_path")
        if not file_path:
            return _create_error("file_path parameter is required")
        
        # Resolve path
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(file_path).is_absolute():
            full_path = workspace_root / file_path
        else:
            full_path = Path(file_path)
        
        # Security check
        try:
            full_path.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return _create_error(f"Path outside workspace: {file_path}")
        
        if not full_path.exists():
            return _create_error(f"File not found: {file_path}")
        
        if full_path.suffix != '.py':
            return _create_error("Type hints are only supported for Python files")
        
        # Read file content
        content = full_path.read_text(encoding='utf-8')
        
        # Analyze type hint gaps
        analyzer = DocumentationAnalyzer()
        analysis = analyzer.analyze_documentation_gaps(full_path, content)
        
        return _format_type_hint_suggestions(full_path, analysis)
    
    except Exception as e:
        return _handle_exception(e, "generate_type_hints")


def _format_documentation_analysis(file_path: Path, analysis: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """Format documentation analysis results"""
    missing_docs = analysis.get("missing_docstrings", [])
    missing_types = analysis.get("missing_type_hints", [])
    doc_coverage = analysis.get("documentation_coverage", 0)
    type_coverage = analysis.get("type_hint_coverage", 0)
    suggestions = analysis.get("suggestions", [])
    
    summary = f"📚 **Documentation Analysis for {file_path.name}**\n\n"
    summary += f"**Coverage Metrics:**\n"
    summary += f"   • Documentation: {doc_coverage:.1f}%\n"
    summary += f"   • Type Hints: {type_coverage:.1f}%\n\n"
    
    if missing_docs:
        summary += f"**Missing Docstrings ({len(missing_docs)} items):**\n"
        for item in missing_docs[:10]:  # Show first 10
            item_type = item.get("type", "function")
            name = item.get("name", "unknown")
            line = item.get("line", "?")
            summary += f"   • {item_type.title()}: `{name}` (line {line})\n"
        
        if len(missing_docs) > 10:
            summary += f"   ... and {len(missing_docs) - 10} more items\n"
        summary += "\n"
    
    if missing_types:
        summary += f"**Missing Type Hints ({len(missing_types)} functions):**\n"
        for item in missing_types[:10]:  # Show first 10
            name = item.get("name", "unknown")
            line = item.get("line", "?")
            missing = ", ".join(item.get("missing_hints", []))
            summary += f"   • `{name}` (line {line}): {missing}\n"
        
        if len(missing_types) > 10:
            summary += f"   ... and {len(missing_types) - 10} more functions\n"
        summary += "\n"
    
    if suggestions:
        summary += f"**Recommendations:**\n"
        for i, suggestion in enumerate(suggestions, 1):
            summary += f"   {i}. {suggestion}\n"
        summary += "\n"
    
    # Action recommendations
    if missing_docs or missing_types:
        if dry_run:
            summary += f"**Next Steps (Dry Run Mode):**\n"
            summary += f"   • Set `dry_run: false` to apply changes\n"
            summary += f"   • Review generated docstrings before applying\n"
            summary += f"   • Consider batch processing for large files\n"
        else:
            summary += f"**🚀 Ready to Apply Documentation:**\n"
            summary += f"   • {len(missing_docs)} docstrings will be added\n"
            summary += f"   • {len(missing_types)} functions will get type hints\n"
            summary += f"   • Backup your files before applying changes\n"
    else:
        summary += f"🎉 **Documentation Complete!** No missing docstrings or type hints found.\n"
    
    return _create_success(summary, {
        "file_path": str(file_path),
        "documentation_coverage": doc_coverage,
        "type_hint_coverage": type_coverage,
        "missing_docstrings": len(missing_docs),
        "missing_type_hints": len(missing_types),
        "analysis": analysis
    })


def _format_type_hint_suggestions(file_path: Path, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Format type hint suggestions"""
    missing_types = analysis.get("missing_type_hints", [])
    type_coverage = analysis.get("type_hint_coverage", 0)
    
    summary = f"🔤 **Type Hint Analysis for {file_path.name}**\n\n"
    summary += f"**Current Coverage:** {type_coverage:.1f}%\n\n"
    
    if missing_types:
        summary += f"**Suggested Type Hints:**\n"
        
        for item in missing_types:
            name = item.get("name", "unknown")
            line = item.get("line", "?")
            missing_hints = item.get("missing_hints", [])
            
            summary += f"\n**Function: `{name}` (line {line})**\n"
            
            # Generate suggested type hints
            for hint in missing_hints:
                if "parameter" in hint:
                    param_name = hint.split("'")[1] if "'" in hint else "param"
                    suggested_type = _suggest_parameter_type(param_name)
                    summary += f"   • {hint}: `{suggested_type}`\n"
                elif "return" in hint:
                    suggested_type = _suggest_return_type(name)
                    summary += f"   • {hint}: `{suggested_type}`\n"
        
        summary += f"\n**Implementation Example:**\n"
        if missing_types:
            first_func = missing_types[0]
            func_name = first_func.get("name", "function")
            summary += f"```python\n"
            summary += f"def {func_name}(param: str, data: Dict[str, Any]) -> bool:\n"
            summary += f"    # Your implementation here\n"
            summary += f"    pass\n"
            summary += f"```\n"
    else:
        summary += f"🎉 **All functions have type hints!**\n"
    
    return _create_success(summary, {
        "file_path": str(file_path),
        "type_hint_coverage": type_coverage,
        "missing_type_hints": len(missing_types),
        "analysis": analysis
    })


def _suggest_parameter_type(param_name: str) -> str:
    """Suggest type for parameter based on name"""
    name_lower = param_name.lower()
    
    if 'path' in name_lower:
        return "Union[str, Path]"
    elif 'file' in name_lower:
        return "str"
    elif 'data' in name_lower:
        return "Dict[str, Any]"
    elif 'args' in name_lower:
        return "Dict[str, Any]"
    elif 'list' in name_lower or 'items' in name_lower:
        return "List[Any]"
    elif 'count' in name_lower or 'size' in name_lower or 'limit' in name_lower:
        return "int"
    elif 'message' in name_lower or 'text' in name_lower or 'name' in name_lower:
        return "str"
    elif name_lower.startswith('is_') or name_lower.startswith('has_') or 'flag' in name_lower:
        return "bool"
    elif 'id' in name_lower:
        return "str"
    else:
        return "Any"


def _suggest_return_type(func_name: str) -> str:
    """Suggest return type based on function name"""
    name_lower = func_name.lower()
    
    if name_lower.startswith('is_') or name_lower.startswith('has_') or name_lower.startswith('can_'):
        return "bool"
    elif name_lower.startswith('get_') or name_lower.startswith('find_'):
        return "Optional[Any]"
    elif name_lower.startswith('list_') or 'list' in name_lower:
        return "List[Any]"
    elif name_lower.startswith('create_') or name_lower.startswith('build_'):
        return "Any"
    elif name_lower.startswith('validate_') or name_lower.startswith('check_'):
        return "bool"
    elif 'count' in name_lower:
        return "int"
    else:
        return "Any"


async def generate_module_docs(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate module-level documentation"""
    try:
        file_path = args.get("file_path")
        if not file_path:
            return _create_error("file_path parameter is required")
        
        # Resolve path
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(file_path).is_absolute():
            full_path = workspace_root / file_path
        else:
            full_path = Path(file_path)
        
        if not full_path.exists():
            return _create_error(f"File not found: {file_path}")
        
        # Read file content
        content = full_path.read_text(encoding='utf-8')
        
        # Generate module documentation
        module_doc = _generate_module_documentation(full_path, content)
        
        return _create_success(f"📄 **Generated Module Documentation for {full_path.name}**\n\n{module_doc}")
    
    except Exception as e:
        return _handle_exception(e, "generate_module_docs")


def _generate_module_documentation(file_path: Path, content: str) -> str:
    """Generate module-level documentation"""
    module_name = file_path.stem
    
    # Basic module docstring
    doc = f'"""{module_name.replace("_", " ").title()} Module\n\n'
    doc += f"This module contains functionality for {module_name.replace('_', ' ')}.\n\n"
    
    if file_path.suffix == '.py':
        try:
            tree = ast.parse(content)
            
            # Find classes and functions
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
            
            if classes:
                doc += "Classes:\n"
                for cls in classes:
                    doc += f"    {cls}: {cls.replace('_', ' ')} class\n"
                doc += "\n"
            
            if functions:
                doc += "Functions:\n"
                for func in functions:
                    doc += f"    {func}: {func.replace('_', ' ')} function\n"
                doc += "\n"
        
        except SyntaxError:
            doc += "Note: File contains syntax errors - manual review required.\n\n"
    
    doc += f"Created: {file_path.stat().st_ctime if file_path.exists() else 'Unknown'}\n"
    doc += '"""'
    
    return doc