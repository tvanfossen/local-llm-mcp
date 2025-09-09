"""Test Generation Tool - Generate comprehensive test coverage

Responsibilities:
- Analyze code to identify untested functions and classes
- Generate unit tests, integration tests, and edge case tests
- Create test fixtures and mock objects
- Generate property-based tests and fuzzing tests
- Ensure comprehensive test coverage metrics
- Integration with local LLM for intelligent test case generation

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
    return {"content": [{"type": "text", "text": f"❌ **Testing Error:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> Dict[str, Any]:
    """Handle exceptions with proper MCP formatting"""
    logger.error(f"Exception in {context}: {str(e)}", exc_info=True)
    return _create_error(f"{context}: {str(e)}")


class TestGenerator:
    """Intelligent test case generator and analyzer"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.test_framework = "pytest"  # Default to pytest
        self.coverage_threshold = 80.0
        
    def analyze_test_coverage(self, source_file: Path, test_file: Optional[Path] = None) -> Dict[str, Any]:
        """Analyze test coverage for a source file"""
        analysis = {
            "source_file": str(source_file),
            "test_file": str(test_file) if test_file else None,
            "functions_to_test": [],
            "classes_to_test": [],
            "existing_tests": [],
            "missing_tests": [],
            "coverage_gaps": [],
            "test_suggestions": []
        }
        
        # Read source file
        if not source_file.exists():
            analysis["error"] = f"Source file not found: {source_file}"
            return analysis
        
        source_content = source_file.read_text(encoding='utf-8')
        
        # Analyze source code
        try:
            tree = ast.parse(source_content)
            
            # Find testable functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith('_'):  # Skip private functions
                        func_info = self._extract_function_info(node, source_content)
                        analysis["functions_to_test"].append(func_info)
                
                elif isinstance(node, ast.ClassDef):
                    class_info = self._extract_class_info(node, source_content)
                    analysis["classes_to_test"].append(class_info)
            
            # Analyze existing tests if test file exists
            if test_file and test_file.exists():
                test_content = test_file.read_text(encoding='utf-8')
                analysis["existing_tests"] = self._extract_existing_tests(test_content)
            
            # Identify missing tests
            analysis["missing_tests"] = self._identify_missing_tests(
                analysis["functions_to_test"], 
                analysis["classes_to_test"], 
                analysis["existing_tests"]
            )
            
            # Generate test suggestions
            analysis["test_suggestions"] = self._generate_test_suggestions(analysis)
            
        except SyntaxError as e:
            analysis["error"] = f"Syntax error in source file: {e.msg} at line {e.lineno}"
        
        return analysis
    
    def _extract_function_info(self, node: ast.FunctionDef, source_content: str) -> Dict[str, Any]:
        """Extract detailed information about a function for testing"""
        func_info = {
            "name": node.name,
            "line": node.lineno,
            "parameters": [],
            "return_annotation": None,
            "complexity": self._calculate_complexity(node),
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "decorators": [ast.unparse(d) if hasattr(ast, 'unparse') else str(d) for d in node.decorator_list],
            "docstring": ast.get_docstring(node),
            "raises_exceptions": self._analyze_exceptions(node),
            "side_effects": self._analyze_side_effects(node)
        }
        
        # Extract parameter information
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation and hasattr(ast, 'unparse') else None,
                "has_default": False
            }
            func_info["parameters"].append(param_info)
        
        # Mark parameters with defaults
        defaults_start = len(node.args.args) - len(node.args.defaults)
        for i, default in enumerate(node.args.defaults):
            param_index = defaults_start + i
            if param_index < len(func_info["parameters"]):
                func_info["parameters"][param_index]["has_default"] = True
                func_info["parameters"][param_index]["default_value"] = ast.unparse(default) if hasattr(ast, 'unparse') else str(default)
        
        # Extract return annotation
        if node.returns:
            func_info["return_annotation"] = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        return func_info
    
    def _extract_class_info(self, node: ast.ClassDef, source_content: str) -> Dict[str, Any]:
        """Extract information about a class for testing"""
        class_info = {
            "name": node.name,
            "line": node.lineno,
            "methods": [],
            "properties": [],
            "base_classes": [ast.unparse(base) if hasattr(ast, 'unparse') else str(base) for base in node.bases],
            "docstring": ast.get_docstring(node),
            "is_exception": any("Exception" in str(base) or "Error" in str(base) for base in node.bases)
        }
        
        # Extract methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function_info(item, source_content)
                method_info["is_method"] = True
                method_info["is_static"] = any("staticmethod" in str(d) for d in item.decorator_list)
                method_info["is_class_method"] = any("classmethod" in str(d) for d in item.decorator_list)
                method_info["is_property"] = any("property" in str(d) for d in item.decorator_list)
                
                if method_info["is_property"]:
                    class_info["properties"].append(method_info)
                else:
                    class_info["methods"].append(method_info)
        
        return class_info
    
    def _extract_existing_tests(self, test_content: str) -> List[Dict[str, Any]]:
        """Extract existing test functions from test file"""
        existing_tests = []
        
        try:
            tree = ast.parse(test_content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "tested_function": self._infer_tested_function(node.name),
                        "test_type": self._classify_test_type(node, test_content),
                        "uses_fixtures": self._check_fixtures(node),
                        "uses_mocks": self._check_mocks(node, test_content)
                    }
                    existing_tests.append(test_info)
        
        except SyntaxError:
            pass  # If test file has syntax errors, return empty list
        
        return existing_tests
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function"""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _analyze_exceptions(self, node: ast.FunctionDef) -> List[str]:
        """Analyze what exceptions a function might raise"""
        exceptions = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc:
                    if isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                        exceptions.append(child.exc.func.id)
                    elif isinstance(child.exc, ast.Name):
                        exceptions.append(child.exc.id)
        
        return list(set(exceptions))
    
    def _analyze_side_effects(self, node: ast.FunctionDef) -> List[str]:
        """Analyze potential side effects of a function"""
        side_effects = []
        
        # Look for file operations, network calls, database operations, etc.
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    attr_name = child.func.attr
                    if attr_name in ['open', 'write', 'read', 'remove', 'mkdir']:
                        side_effects.append("file_system")
                    elif attr_name in ['get', 'post', 'put', 'delete', 'request']:
                        side_effects.append("network")
                    elif attr_name in ['execute', 'commit', 'rollback', 'query']:
                        side_effects.append("database")
                    elif attr_name in ['print', 'log', 'debug', 'info', 'warning', 'error']:
                        side_effects.append("logging")
        
        return list(set(side_effects))
    
    def _infer_tested_function(self, test_name: str) -> str:
        """Infer the function being tested from test name"""
        # Remove test_ prefix and common suffixes
        function_name = test_name.replace('test_', '')
        function_name = re.sub(r'_with_.*', '', function_name)
        function_name = re.sub(r'_when_.*', '', function_name)
        function_name = re.sub(r'_should_.*', '', function_name)
        function_name = re.sub(r'_returns_.*', '', function_name)
        function_name = re.sub(r'_raises_.*', '', function_name)
        
        return function_name
    
    def _classify_test_type(self, node: ast.FunctionDef, test_content: str) -> str:
        """Classify the type of test"""
        test_body = ast.get_source_segment(test_content, node) if hasattr(ast, 'get_source_segment') else ""
        
        if "mock" in test_body.lower() or "patch" in test_body.lower():
            return "unit_with_mocks"
        elif "assert" in test_body:
            return "unit"
        elif "integration" in node.name.lower():
            return "integration"
        elif "end_to_end" in node.name.lower() or "e2e" in node.name.lower():
            return "e2e"
        else:
            return "unit"
    
    def _check_fixtures(self, node: ast.FunctionDef) -> bool:
        """Check if test uses fixtures"""
        for arg in node.args.args:
            if arg.arg not in ['self']:  # Skip self parameter
                return True
        return False
    
    def _check_mocks(self, node: ast.FunctionDef, test_content: str) -> bool:
        """Check if test uses mocks"""
        test_body = ast.get_source_segment(test_content, node) if hasattr(ast, 'get_source_segment') else ""
        mock_keywords = ['mock', 'patch', 'Mock', 'MagicMock', 'side_effect']
        
        return any(keyword in test_body for keyword in mock_keywords)
    
    def _identify_missing_tests(self, functions: List[Dict], classes: List[Dict], existing_tests: List[Dict]) -> List[Dict]:
        """Identify functions and classes that need tests"""
        missing_tests = []
        tested_functions = {test["tested_function"] for test in existing_tests}
        
        # Check missing function tests
        for func in functions:
            if func["name"] not in tested_functions:
                missing_tests.append({
                    "type": "function",
                    "name": func["name"],
                    "priority": self._calculate_test_priority(func),
                    "test_cases_needed": self._suggest_test_cases_for_function(func)
                })
        
        # Check missing class tests
        for cls in classes:
            class_tested = any(cls["name"].lower() in test["name"].lower() for test in existing_tests)
            if not class_tested:
                missing_tests.append({
                    "type": "class",
                    "name": cls["name"],
                    "priority": "medium",
                    "test_cases_needed": self._suggest_test_cases_for_class(cls)
                })
        
        return missing_tests
    
    def _calculate_test_priority(self, func: Dict) -> str:
        """Calculate test priority based on function characteristics"""
        complexity = func.get("complexity", 1)
        has_side_effects = bool(func.get("side_effects", []))
        raises_exceptions = bool(func.get("raises_exceptions", []))
        is_public = not func["name"].startswith('_')
        
        score = 0
        if complexity > 5:
            score += 3
        elif complexity > 2:
            score += 1
        
        if has_side_effects:
            score += 2
        if raises_exceptions:
            score += 2
        if is_public:
            score += 1
        
        if score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    def _suggest_test_cases_for_function(self, func: Dict) -> List[Dict]:
        """Suggest test cases for a function"""
        test_cases = []
        
        # Happy path test
        test_cases.append({
            "type": "happy_path",
            "description": f"Test {func['name']} with valid inputs",
            "priority": "high"
        })
        
        # Edge cases based on parameters
        for param in func.get("parameters", []):
            if param["annotation"]:
                annotation = param["annotation"].lower()
                if "int" in annotation:
                    test_cases.append({
                        "type": "edge_case",
                        "description": f"Test {func['name']} with zero, negative, and large integers for {param['name']}",
                        "priority": "medium"
                    })
                elif "str" in annotation:
                    test_cases.append({
                        "type": "edge_case",
                        "description": f"Test {func['name']} with empty string, whitespace, and unicode for {param['name']}",
                        "priority": "medium"
                    })
                elif "list" in annotation or "List" in param["annotation"]:
                    test_cases.append({
                        "type": "edge_case",
                        "description": f"Test {func['name']} with empty list and large list for {param['name']}",
                        "priority": "medium"
                    })
        
        # Exception tests
        for exception in func.get("raises_exceptions", []):
            test_cases.append({
                "type": "exception",
                "description": f"Test {func['name']} raises {exception}",
                "priority": "high"
            })
        
        # Side effect tests
        for side_effect in func.get("side_effects", []):
            test_cases.append({
                "type": "side_effect",
                "description": f"Test {func['name']} {side_effect} side effects",
                "priority": "medium"
            })
        
        return test_cases
    
    def _suggest_test_cases_for_class(self, cls: Dict) -> List[Dict]:
        """Suggest test cases for a class"""
        test_cases = []
        
        # Constructor test
        test_cases.append({
            "type": "constructor",
            "description": f"Test {cls['name']} initialization",
            "priority": "high"
        })
        
        # Method tests
        for method in cls.get("methods", []):
            if not method["name"].startswith('_'):
                test_cases.append({
                    "type": "method",
                    "description": f"Test {cls['name']}.{method['name']} method",
                    "priority": self._calculate_test_priority(method)
                })
        
        # Property tests
        for prop in cls.get("properties", []):
            test_cases.append({
                "type": "property",
                "description": f"Test {cls['name']}.{prop['name']} property",
                "priority": "medium"
            })
        
        return test_cases
    
    def _generate_test_suggestions(self, analysis: Dict) -> List[str]:
        """Generate high-level test suggestions"""
        suggestions = []
        
        functions_count = len(analysis["functions_to_test"])
        classes_count = len(analysis["classes_to_test"])
        missing_count = len(analysis["missing_tests"])
        existing_count = len(analysis["existing_tests"])
        
        if missing_count == 0:
            suggestions.append("Excellent! All functions and classes have tests")
        elif missing_count > functions_count + classes_count * 0.5:
            suggestions.append("Consider implementing a comprehensive testing strategy - many components lack tests")
        elif missing_count > 5:
            suggestions.append("Focus on testing the most critical functions first")
        
        # Coverage suggestions
        if existing_count > 0:
            coverage_ratio = (functions_count + classes_count - missing_count) / (functions_count + classes_count)
            if coverage_ratio < 0.5:
                suggestions.append("Test coverage is low - aim for at least 80% coverage")
            elif coverage_ratio < 0.8:
                suggestions.append("Good test coverage progress - aim to complete the remaining gaps")
        
        # Specific suggestions based on analysis
        high_priority_missing = [t for t in analysis["missing_tests"] if t.get("priority") == "high"]
        if high_priority_missing:
            suggestions.append(f"Priority: {len(high_priority_missing)} high-priority functions need tests immediately")
        
        # Framework suggestions
        complex_functions = [f for f in analysis["functions_to_test"] if f.get("complexity", 1) > 5]
        if complex_functions:
            suggestions.append("Consider property-based testing for complex functions")
        
        side_effect_functions = [f for f in analysis["functions_to_test"] if f.get("side_effects")]
        if side_effect_functions:
            suggestions.append("Use mocks and fixtures for functions with side effects")
        
        return suggestions
    
    def generate_test_code(self, func_info: Dict, test_cases: List[Dict]) -> str:
        """Generate actual test code for a function"""
        func_name = func_info["name"]
        test_code = f"# Generated tests for {func_name}\n\n"
        
        # Imports
        test_code += "import pytest\n"
        if func_info.get("is_async"):
            test_code += "import asyncio\n"
        if any("mock" in tc.get("type", "") for tc in test_cases):
            test_code += "from unittest.mock import Mock, patch, MagicMock\n"
        test_code += "\n"
        
        # Generate test functions
        for i, test_case in enumerate(test_cases):
            test_function_name = f"test_{func_name}_{test_case['type']}"
            if i > 0 and test_case['type'] in [tc['type'] for tc in test_cases[:i]]:
                test_function_name += f"_{i}"
            
            test_code += f"def {test_function_name}():\n"
            test_code += f'    """{test_case["description"]}"""\n'
            
            # Generate test body based on type
            if test_case["type"] == "happy_path":
                test_code += self._generate_happy_path_test(func_info)
            elif test_case["type"] == "edge_case":
                test_code += self._generate_edge_case_test(func_info)
            elif test_case["type"] == "exception":
                test_code += self._generate_exception_test(func_info)
            else:
                test_code += "    # TODO: Implement this test case\n"
                test_code += "    assert False, 'Test not implemented'\n"
            
            test_code += "\n\n"
        
        return test_code
    
    def _generate_happy_path_test(self, func_info: Dict) -> str:
        """Generate happy path test code"""
        func_name = func_info["name"]
        parameters = func_info.get("parameters", [])
        
        # Create sample arguments
        args = []
        for param in parameters:
            if param["name"] in ["self", "cls"]:
                continue
            
            if param.get("has_default"):
                continue  # Skip parameters with defaults for happy path
            
            # Generate sample value based on annotation
            sample_value = self._generate_sample_value(param.get("annotation"))
            args.append(f"{param['name']}={sample_value}")
        
        test_body = "    # Arrange\n"
        if args:
            test_body += f"    # Act\n"
            test_body += f"    result = {func_name}({', '.join(args)})\n"
        else:
            test_body += f"    # Act\n"
            test_body += f"    result = {func_name}()\n"
        
        test_body += "    \n"
        test_body += "    # Assert\n"
        test_body += "    assert result is not None  # TODO: Add specific assertions\n"
        
        return test_body
    
    def _generate_edge_case_test(self, func_info: Dict) -> str:
        """Generate edge case test code"""
        return "    # TODO: Implement edge case test\n    pass\n"
    
    def _generate_exception_test(self, func_info: Dict) -> str:
        """Generate exception test code"""
        func_name = func_info["name"]
        exceptions = func_info.get("raises_exceptions", ["Exception"])
        
        test_body = "    # Arrange - Create conditions that should raise exception\n"
        test_body += "    # TODO: Set up invalid inputs\n"
        test_body += "    \n"
        test_body += f"    # Act & Assert\n"
        test_body += f"    with pytest.raises({exceptions[0] if exceptions else 'Exception'}):\n"
        test_body += f"        {func_name}()  # TODO: Add invalid arguments\n"
        
        return test_body
    
    def _generate_sample_value(self, annotation: Optional[str]) -> str:
        """Generate sample value based on type annotation"""
        if not annotation:
            return "'sample_value'"
        
        annotation_lower = annotation.lower()
        
        if "str" in annotation_lower:
            return "'test_string'"
        elif "int" in annotation_lower:
            return "42"
        elif "float" in annotation_lower:
            return "3.14"
        elif "bool" in annotation_lower:
            return "True"
        elif "list" in annotation_lower:
            return "[1, 2, 3]"
        elif "dict" in annotation_lower:
            return "{'key': 'value'}"
        elif "path" in annotation_lower:
            return "Path('test_file.txt')"
        else:
            return "None"


async def generate_tests(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive tests for a file"""
    try:
        source_file = args.get("source_file")
        if not source_file:
            return _create_error("source_file parameter is required")
        
        test_file = args.get("test_file")  # Optional
        generate_code = args.get("generate_code", False)
        test_types = args.get("test_types", ["unit", "integration", "edge_cases"])
        
        # Resolve paths
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(source_file).is_absolute():
            source_path = workspace_root / source_file
        else:
            source_path = Path(source_file)
        
        # Security check
        try:
            source_path.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return _create_error(f"Source path outside workspace: {source_file}")
        
        # Resolve test file path
        test_path = None
        if test_file:
            if not Path(test_file).is_absolute():
                test_path = workspace_root / test_file
            else:
                test_path = Path(test_file)
        else:
            # Auto-generate test file path
            test_path = source_path.parent / "tests" / f"test_{source_path.name}"
        
        # Analyze test coverage
        generator = TestGenerator()
        analysis = generator.analyze_test_coverage(source_path, test_path if test_path.exists() else None)
        
        if "error" in analysis:
            return _create_error(analysis["error"])
        
        return _format_test_analysis(source_path, test_path, analysis, generate_code)
    
    except Exception as e:
        return _handle_exception(e, "generate_tests")


async def analyze_test_coverage(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze test coverage for a project or directory"""
    try:
        directory_path = args.get("directory_path", ".")
        coverage_threshold = args.get("coverage_threshold", 80.0)
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(directory_path).is_absolute():
            dir_path = workspace_root / directory_path
        else:
            dir_path = Path(directory_path)
        
        generator = TestGenerator()
        generator.coverage_threshold = coverage_threshold
        
        # Find all Python source files
        source_files = []
        for py_file in dir_path.rglob("*.py"):
            if "test" not in py_file.name and "__pycache__" not in str(py_file):
                source_files.append(py_file)
        
        # Analyze each file
        coverage_results = []
        for source_file in source_files[:20]:  # Limit to 20 files for performance
            try:
                # Look for corresponding test file
                test_patterns = [
                    source_file.parent / "tests" / f"test_{source_file.name}",
                    source_file.parent / f"test_{source_file.name}",
                    workspace_root / "tests" / source_file.relative_to(workspace_root).with_name(f"test_{source_file.name}")
                ]
                
                test_file = None
                for pattern in test_patterns:
                    if pattern.exists():
                        test_file = pattern
                        break
                
                analysis = generator.analyze_test_coverage(source_file, test_file)
                if "error" not in analysis:
                    coverage_results.append(analysis)
            
            except Exception as e:
                logger.warning(f"Failed to analyze {source_file}: {e}")
        
        return _format_coverage_report(coverage_results, coverage_threshold)
    
    except Exception as e:
        return _handle_exception(e, "analyze_test_coverage")


def _format_test_analysis(source_path: Path, test_path: Path, analysis: Dict, generate_code: bool) -> Dict[str, Any]:
    """Format test analysis results"""
    functions_to_test = analysis.get("functions_to_test", [])
    classes_to_test = analysis.get("classes_to_test", [])
    existing_tests = analysis.get("existing_tests", [])
    missing_tests = analysis.get("missing_tests", [])
    suggestions = analysis.get("test_suggestions", [])
    
    total_testable = len(functions_to_test) + len(classes_to_test)
    total_missing = len(missing_tests)
    coverage_percent = ((total_testable - total_missing) / total_testable * 100) if total_testable > 0 else 100
    
    summary = f"🧪 **Test Analysis for {source_path.name}**\n\n"
    summary += f"**Test Coverage:** {coverage_percent:.1f}% ({total_testable - total_missing}/{total_testable} items tested)\n\n"
    
    summary += f"**Source Analysis:**\n"
    summary += f"   • Functions to test: {len(functions_to_test)}\n"
    summary += f"   • Classes to test: {len(classes_to_test)}\n"
    summary += f"   • Existing tests: {len(existing_tests)}\n"
    summary += f"   • Missing tests: {len(missing_tests)}\n\n"
    
    if missing_tests:
        # Group by priority
        high_priority = [t for t in missing_tests if t.get("priority") == "high"]
        medium_priority = [t for t in missing_tests if t.get("priority") == "medium"]
        low_priority = [t for t in missing_tests if t.get("priority") == "low"]
        
        summary += f"**Missing Tests by Priority:**\n"
        if high_priority:
            summary += f"   🚨 **High Priority ({len(high_priority)} items):**\n"
            for item in high_priority[:5]:
                summary += f"      • {item['name']} ({item['type']})\n"
        
        if medium_priority:
            summary += f"   ⚠️ **Medium Priority ({len(medium_priority)} items):**\n"
            for item in medium_priority[:3]:
                summary += f"      • {item['name']} ({item['type']})\n"
        
        if low_priority:
            summary += f"   ℹ️ **Low Priority ({len(low_priority)} items):**\n"
            for item in low_priority[:3]:
                summary += f"      • {item['name']} ({item['type']})\n"
        summary += "\n"
    
    if suggestions:
        summary += f"**Recommendations:**\n"
        for i, suggestion in enumerate(suggestions, 1):
            summary += f"   {i}. {suggestion}\n"
        summary += "\n"
    
    # Test file information
    if test_path.exists():
        summary += f"**Test File:** {test_path.name} (exists)\n"
    else:
        summary += f"**Test File:** {test_path.name} (will be created)\n"
    
    if generate_code and missing_tests:
        summary += f"\n**🚀 Ready to Generate Test Code:**\n"
        summary += f"   • {len(missing_tests)} test suites will be created\n"
        summary += f"   • Estimated {sum(len(t.get('test_cases_needed', [])) for t in missing_tests)} test cases\n"
        summary += f"   • Test file: {test_path}\n"
    elif missing_tests:
        summary += f"\n**Next Steps:**\n"
        summary += f"   • Set `generate_code: true` to create test templates\n"
        summary += f"   • Focus on high-priority items first\n"
        summary += f"   • Consider property-based testing for complex functions\n"
    else:
        summary += f"\n🎉 **Perfect Test Coverage!** All components have tests.\n"
    
    return _create_success(summary, {
        "source_file": str(source_path),
        "test_file": str(test_path),
        "coverage_percentage": coverage_percent,
        "total_testable": total_testable,
        "missing_tests": total_missing,
        "analysis": analysis
    })


def _format_coverage_report(results: List[Dict], threshold: float) -> Dict[str, Any]:
    """Format project-wide test coverage report"""
    if not results:
        return _create_success("📊 **No files analyzed** for test coverage")
    
    # Calculate aggregate statistics
    total_files = len(results)
    total_testable = sum(len(r.get("functions_to_test", [])) + len(r.get("classes_to_test", [])) for r in results)
    total_missing = sum(len(r.get("missing_tests", [])) for r in results)
    total_existing = sum(len(r.get("existing_tests", [])) for r in results)
    
    overall_coverage = ((total_testable - total_missing) / total_testable * 100) if total_testable > 0 else 100
    
    # Determine health status
    if overall_coverage >= 90:
        health_emoji = "🟢"
        health_status = "EXCELLENT"
    elif overall_coverage >= threshold:
        health_emoji = "🟡"  
        health_status = "GOOD"
    elif overall_coverage >= 50:
        health_emoji = "🟠"
        health_status = "NEEDS WORK"
    else:
        health_emoji = "🔴"
        health_status = "POOR"
    
    summary = f"📊 **Project Test Coverage Report**\n\n"
    summary += f"**Overall Coverage:** {health_emoji} {overall_coverage:.1f}% ({health_status})\n"
    summary += f"**Target Threshold:** {threshold}%\n\n"
    
    summary += f"**Project Statistics:**\n"
    summary += f"   • Files Analyzed: {total_files}\n"
    summary += f"   • Testable Items: {total_testable}\n"
    summary += f"   • Existing Tests: {total_existing}\n"
    summary += f"   • Missing Tests: {total_missing}\n\n"
    
    # Find files with poor coverage
    poor_coverage_files = []
    for result in results:
        functions = len(result.get("functions_to_test", []))
        classes = len(result.get("classes_to_test", []))
        missing = len(result.get("missing_tests", []))
        total = functions + classes
        
        if total > 0:
            coverage = ((total - missing) / total * 100)
            if coverage < threshold:
                poor_coverage_files.append({
                    "file": Path(result["source_file"]).name,
                    "coverage": coverage,
                    "missing": missing
                })
    
    if poor_coverage_files:
        poor_coverage_files.sort(key=lambda x: x["coverage"])
        summary += f"**Files Below Threshold ({len(poor_coverage_files)}):**\n"
        
        for i, file_info in enumerate(poor_coverage_files[:10], 1):
            coverage = file_info["coverage"]
            missing = file_info["missing"]
            
            if coverage < 25:
                emoji = "🔴"
            elif coverage < 50:
                emoji = "🟠"
            else:
                emoji = "🟡"
            
            summary += f"   {i}. {emoji} {file_info['file']}: {coverage:.1f}% ({missing} missing tests)\n"
        
        if len(poor_coverage_files) > 10:
            summary += f"   ... and {len(poor_coverage_files) - 10} more files\n"
        summary += "\n"
    
    # Implementation recommendations
    summary += f"**🚀 Recommended Action Plan:**\n"
    
    if overall_coverage < 50:
        summary += f"   **Phase 1 (Critical):** Focus on {len([f for f in poor_coverage_files if f['coverage'] < 25])} files with <25% coverage\n"
        summary += f"   **Phase 2 (Important):** Bring remaining files to {threshold}% threshold\n"
        summary += f"   **Phase 3 (Excellence):** Achieve 90%+ coverage across project\n"
    elif overall_coverage < threshold:
        summary += f"   **Phase 1:** Address {len(poor_coverage_files)} files below threshold\n"
        summary += f"   **Phase 2:** Enhance test quality and edge case coverage\n"
    else:
        summary += f"   **Maintenance:** Focus on test quality and maintainability\n"
    
    summary += f"\n**Estimated Effort:** {_estimate_testing_effort(results)} hours\n"
    
    return _create_success(summary, {
        "total_files": total_files,
        "overall_coverage": overall_coverage,
        "threshold": threshold,
        "total_testable": total_testable,
        "total_missing": total_missing,
        "files_below_threshold": len(poor_coverage_files),
        "health_status": health_status
    })


def _estimate_testing_effort(results: List[Dict]) -> int:
    """Estimate effort to create missing tests"""
    effort_per_function = 0.5  # 30 minutes per function test
    effort_per_class = 1.0     # 1 hour per class test suite
    
    total_effort = 0
    for result in results:
        missing_tests = result.get("missing_tests", [])
        for missing in missing_tests:
            if missing["type"] == "function":
                # Add extra time for complex functions
                test_cases = len(missing.get("test_cases_needed", []))
                total_effort += effort_per_function * max(1, test_cases * 0.2)
            else:  # class
                total_effort += effort_per_class
    
    return max(1, int(total_effort))


async def create_test_suite(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a complete test suite for a file"""
    try:
        source_file = args.get("source_file")
        if not source_file:
            return _create_error("source_file parameter is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(source_file).is_absolute():
            source_path = workspace_root / source_file
        else:
            source_path = Path(source_file)
        
        # Generate test analysis
        generator = TestGenerator()
        analysis = generator.analyze_test_coverage(source_path)
        
        if "error" in analysis:
            return _create_error(analysis["error"])
        
        # Generate test code
        test_code = "# Generated test suite\n"
        test_code += f"# Source: {source_path.name}\n"
        test_code += f"# Generated on: {__import__('datetime').datetime.now().isoformat()}\n\n"
        
        # Add imports
        test_code += "import pytest\n"
        test_code += f"from {source_path.stem} import *\n\n"
        
        # Generate tests for each missing function/class
        for missing_test in analysis.get("missing_tests", []):
            if missing_test["type"] == "function":
                # Find function info
                func_info = next(
                    (f for f in analysis.get("functions_to_test", []) if f["name"] == missing_test["name"]),
                    {"name": missing_test["name"], "parameters": []}
                )
                
                test_cases = missing_test.get("test_cases_needed", [])
                generated_code = generator.generate_test_code(func_info, test_cases)
                test_code += generated_code
        
        return _create_success(f"🧪 **Generated Test Suite**\n\n```python\n{test_code}\n```")
    
    except Exception as e:
        return _handle_exception(e, "create_test_suite")