"""Code Quality Analysis Tool - Analyze managed files for quality issues

Responsibilities:
- Static code analysis using AST parsing
- Code complexity metrics (cyclomatic, cognitive)
- Style and convention checking
- Security vulnerability detection
- Performance bottleneck identification
- Integration with local LLM for intelligent suggestions

Phase 5: Self-Improvement MCP Tools
"""

import ast
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    return {"content": [{"type": "text", "text": f"❌ **Analysis Error:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> Dict[str, Any]:
    """Handle exceptions with proper MCP formatting"""
    logger.error(f"Exception in {context}: {str(e)}", exc_info=True)
    return _create_error(f"{context}: {str(e)}")


class CodeQualityAnalyzer:
    """Comprehensive code quality analyzer"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.issues = []
        self.metrics = {}
        
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file for quality issues"""
        try:
            if not file_path.exists():
                return {"error": f"File not found: {file_path}"}
            
            # Reset analysis state
            self.issues = []
            self.metrics = {}
            
            # Read file content
            content = file_path.read_text(encoding='utf-8')
            
            # Determine file type and run appropriate analysis
            if file_path.suffix == '.py':
                return self._analyze_python_file(file_path, content)
            elif file_path.suffix in ['.js', '.ts']:
                return self._analyze_javascript_file(file_path, content)
            elif file_path.suffix in ['.md', '.txt']:
                return self._analyze_text_file(file_path, content)
            else:
                return self._analyze_generic_file(file_path, content)
                
        except Exception as e:
            logger.error(f"Failed to analyze {file_path}: {e}")
            return {"error": str(e)}
    
    def _analyze_python_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze Python file using AST"""
        analysis = {
            "file_path": str(file_path),
            "file_type": "python",
            "line_count": len(content.splitlines()),
            "issues": [],
            "metrics": {},
            "suggestions": []
        }
        
        try:
            # Parse AST
            tree = ast.parse(content)
            
            # Basic metrics
            analysis["metrics"] = {
                "functions": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
                "classes": len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]),
                "imports": len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]),
                "complexity_score": self._calculate_complexity(tree)
            }
            
            # Check for issues
            self._check_python_style(content, analysis)
            self._check_python_security(tree, analysis)
            self._check_python_performance(tree, analysis)
            self._check_documentation(content, analysis)
            self._check_type_hints(tree, analysis)
            
        except SyntaxError as e:
            analysis["issues"].append({
                "type": "syntax_error",
                "severity": "error",
                "message": f"Syntax error at line {e.lineno}: {e.msg}",
                "line": e.lineno
            })
        
        return analysis
    
    def _analyze_javascript_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript file"""
        analysis = {
            "file_path": str(file_path),
            "file_type": "javascript",
            "line_count": len(content.splitlines()),
            "issues": [],
            "metrics": {
                "functions": len(re.findall(r'function\s+\w+|const\s+\w+\s*=\s*\(.*?\)\s*=>', content)),
                "classes": len(re.findall(r'class\s+\w+', content)),
                "imports": len(re.findall(r'import\s+.*?from|require\s*\(', content))
            },
            "suggestions": []
        }
        
        # Basic JavaScript checks
        self._check_javascript_style(content, analysis)
        
        return analysis
    
    def _analyze_text_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze text/markdown files"""
        analysis = {
            "file_path": str(file_path),
            "file_type": "text",
            "line_count": len(content.splitlines()),
            "issues": [],
            "metrics": {
                "word_count": len(content.split()),
                "character_count": len(content),
                "empty_lines": len([line for line in content.splitlines() if not line.strip()])
            },
            "suggestions": []
        }
        
        # Check for common text issues
        self._check_text_quality(content, analysis)
        
        return analysis
    
    def _analyze_generic_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze generic files"""
        return {
            "file_path": str(file_path),
            "file_type": "generic",
            "line_count": len(content.splitlines()),
            "issues": [],
            "metrics": {
                "size_bytes": len(content.encode('utf-8')),
                "character_count": len(content)
            },
            "suggestions": ["Consider adding specific analysis for this file type"]
        }
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
                
        return complexity
    
    def _check_python_style(self, content: str, analysis: Dict[str, Any]) -> None:
        """Check Python style issues"""
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            # Line length check
            if len(line) > 100:
                analysis["issues"].append({
                    "type": "style",
                    "severity": "warning",
                    "message": f"Line too long ({len(line)} > 100 characters)",
                    "line": i
                })
            
            # Trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                analysis["issues"].append({
                    "type": "style",
                    "severity": "info",
                    "message": "Trailing whitespace",
                    "line": i
                })
            
            # Multiple consecutive blank lines
            if i > 2 and not line.strip() and not lines[i-2].strip() and not lines[i-3].strip():
                analysis["issues"].append({
                    "type": "style",
                    "severity": "info",
                    "message": "Too many consecutive blank lines",
                    "line": i
                })
    
    def _check_python_security(self, tree: ast.AST, analysis: Dict[str, Any]) -> None:
        """Check for security issues"""
        for node in ast.walk(tree):
            # Check for dangerous eval/exec usage
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['eval', 'exec']:
                    analysis["issues"].append({
                        "type": "security",
                        "severity": "error",
                        "message": f"Dangerous use of {node.func.id}()",
                        "line": node.lineno
                    })
            
            # Check for SQL injection patterns
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                    if 'SELECT' in node.left.value.upper() or 'INSERT' in node.left.value.upper():
                        analysis["issues"].append({
                            "type": "security",
                            "severity": "warning",
                            "message": "Potential SQL injection vulnerability",
                            "line": node.lineno
                        })
    
    def _check_python_performance(self, tree: ast.AST, analysis: Dict[str, Any]) -> None:
        """Check for performance issues"""
        for node in ast.walk(tree):
            # Check for inefficient string concatenation in loops
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if (isinstance(child, ast.AugAssign) and 
                        isinstance(child.op, ast.Add) and
                        isinstance(child.target, ast.Name)):
                        analysis["issues"].append({
                            "type": "performance",
                            "severity": "warning",
                            "message": "String concatenation in loop - consider using join()",
                            "line": child.lineno
                        })
    
    def _check_documentation(self, content: str, analysis: Dict[str, Any]) -> None:
        """Check for missing documentation"""
        lines = content.splitlines()
        
        # Check for missing docstrings in functions/classes
        in_function = False
        function_line = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('def ') or stripped.startswith('class '):
                in_function = True
                function_line = i + 1
                continue
                
            if in_function:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_function = False  # Found docstring
                elif stripped and not stripped.startswith('#'):
                    # Non-comment line without docstring
                    analysis["issues"].append({
                        "type": "documentation",
                        "severity": "warning",
                        "message": "Missing docstring",
                        "line": function_line
                    })
                    in_function = False
    
    def _check_type_hints(self, tree: ast.AST, analysis: Dict[str, Any]) -> None:
        """Check for missing type hints"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function parameters
                missing_hints = []
                for arg in node.args.args:
                    if not arg.annotation:
                        missing_hints.append(arg.arg)
                
                # Check return type
                if not node.returns:
                    missing_hints.append("return")
                
                if missing_hints:
                    analysis["issues"].append({
                        "type": "type_hints",
                        "severity": "info",
                        "message": f"Missing type hints for: {', '.join(missing_hints)}",
                        "line": node.lineno
                    })
    
    def _check_javascript_style(self, content: str, analysis: Dict[str, Any]) -> None:
        """Check JavaScript style issues"""
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                analysis["issues"].append({
                    "type": "style",
                    "severity": "warning",
                    "message": f"Line too long ({len(line)} > 120 characters)",
                    "line": i
                })
    
    def _check_text_quality(self, content: str, analysis: Dict[str, Any]) -> None:
        """Check text quality issues"""
        lines = content.splitlines()
        
        for i, line in enumerate(lines, 1):
            # Check for very long lines in text files
            if len(line) > 200:
                analysis["issues"].append({
                    "type": "readability",
                    "severity": "info",
                    "message": f"Very long line ({len(line)} characters)",
                    "line": i
                })


async def analyze_code_quality(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze code quality for a file or directory"""
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
        
        # Security check - ensure path is within workspace
        try:
            full_path.resolve().relative_to(workspace_root.resolve())
        except ValueError:
            return _create_error(f"Path outside workspace: {file_path}")
        
        analyzer = CodeQualityAnalyzer()
        
        if full_path.is_file():
            # Analyze single file
            result = analyzer.analyze_file(full_path)
            
            if "error" in result:
                return _create_error(result["error"])
            
            # Format results for display
            return _format_analysis_results([result], args.get("detailed", True))
            
        elif full_path.is_dir():
            # Analyze directory
            max_files = args.get("max_files", 50)
            file_patterns = args.get("file_patterns", ["*.py", "*.js", "*.ts", "*.md"])
            
            results = []
            file_count = 0
            
            for pattern in file_patterns:
                for file_path in full_path.rglob(pattern):
                    if file_count >= max_files:
                        break
                    
                    if file_path.is_file():
                        result = analyzer.analyze_file(file_path)
                        if "error" not in result:
                            results.append(result)
                            file_count += 1
            
            return _format_analysis_results(results, args.get("detailed", False))
        
        else:
            return _create_error(f"Path not found: {file_path}")
    
    except Exception as e:
        return _handle_exception(e, "analyze_code_quality")


def _format_analysis_results(results: List[Dict[str, Any]], detailed: bool = True) -> Dict[str, Any]:
    """Format analysis results for MCP response"""
    if not results:
        return _create_success("📊 **No files analyzed**")
    
    # Aggregate statistics
    total_files = len(results)
    total_issues = sum(len(r.get("issues", [])) for r in results)
    total_lines = sum(r.get("line_count", 0) for r in results)
    
    # Group issues by severity
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    issue_types = {}
    
    for result in results:
        for issue in result.get("issues", []):
            severity = issue.get("severity", "info")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            issue_type = issue.get("type", "unknown")
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    
    # Create summary
    summary = f"📊 **Code Quality Analysis Summary**\n\n"
    summary += f"**Files Analyzed:** {total_files}\n"
    summary += f"**Total Lines:** {total_lines:,}\n"
    summary += f"**Total Issues:** {total_issues}\n\n"
    
    summary += f"**Issues by Severity:**\n"
    for severity, count in severity_counts.items():
        emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "•")
        summary += f"   {emoji} {severity.title()}: {count}\n"
    
    if issue_types:
        summary += f"\n**Issues by Type:**\n"
        for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
            summary += f"   • {issue_type}: {count}\n"
    
    if detailed and results:
        summary += f"\n**Detailed Results:**\n"
        for result in results[:10]:  # Limit to first 10 files for readability
            file_path = result.get("file_path", "unknown")
            issues = result.get("issues", [])
            
            summary += f"\n🔍 **{Path(file_path).name}** ({len(issues)} issues)\n"
            
            for issue in issues[:5]:  # Show max 5 issues per file
                emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.get("severity"), "•")
                line = f" (line {issue['line']})" if issue.get("line") else ""
                summary += f"   {emoji} {issue.get('message', 'Unknown issue')}{line}\n"
            
            if len(issues) > 5:
                summary += f"   ... and {len(issues) - 5} more issues\n"
    
    # Add improvement suggestions
    suggestions = _generate_improvement_suggestions(results)
    if suggestions:
        summary += f"\n**🚀 Improvement Suggestions:**\n"
        for i, suggestion in enumerate(suggestions[:5], 1):
            summary += f"{i}. {suggestion}\n"
    
    return _create_success(summary, {"total_files": total_files, "total_issues": total_issues, "results": results})


def _generate_improvement_suggestions(results: List[Dict[str, Any]]) -> List[str]:
    """Generate intelligent improvement suggestions based on analysis"""
    suggestions = []
    
    # Analyze common issues across files
    all_issues = []
    for result in results:
        all_issues.extend(result.get("issues", []))
    
    issue_counts = {}
    for issue in all_issues:
        issue_type = issue.get("type", "unknown")
        issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    
    # Generate suggestions based on most common issues
    if issue_counts.get("style", 0) > 10:
        suggestions.append("Consider running a code formatter (black, prettier) to fix style issues")
    
    if issue_counts.get("documentation", 0) > 5:
        suggestions.append("Add docstrings to functions and classes for better documentation")
    
    if issue_counts.get("type_hints", 0) > 5:
        suggestions.append("Add type hints to improve code clarity and IDE support")
    
    if issue_counts.get("security", 0) > 0:
        suggestions.append("Review security issues - consider using secure alternatives")
    
    if issue_counts.get("performance", 0) > 3:
        suggestions.append("Optimize performance bottlenecks identified in the analysis")
    
    # File-specific suggestions
    large_files = [r for r in results if r.get("line_count", 0) > 300]
    if large_files:
        suggestions.append(f"Consider refactoring {len(large_files)} large files (>300 lines) into smaller modules")
    
    complex_files = [r for r in results if r.get("metrics", {}).get("complexity_score", 0) > 20]
    if complex_files:
        suggestions.append(f"Reduce complexity in {len(complex_files)} files with high complexity scores")
    
    return suggestions


async def analyze_project_health(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze overall project health metrics"""
    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        analyzer = CodeQualityAnalyzer()
        results = []
        
        # Analyze key project files
        important_patterns = ["*.py", "*.js", "*.ts", "*.md", "*.json", "*.yml", "*.yaml"]
        
        for pattern in important_patterns:
            for file_path in workspace_root.rglob(pattern):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    result = analyzer.analyze_file(file_path)
                    if "error" not in result:
                        results.append(result)
        
        # Calculate health score
        health_score = _calculate_health_score(results)
        
        summary = f"🏥 **Project Health Analysis**\n\n"
        summary += f"**Overall Health Score:** {health_score:.1f}/10.0\n\n"
        
        return _format_analysis_results(results, detailed=False)
    
    except Exception as e:
        return _handle_exception(e, "analyze_project_health")


def _calculate_health_score(results: List[Dict[str, Any]]) -> float:
    """Calculate overall project health score (0-10)"""
    if not results:
        return 0.0
    
    total_files = len(results)
    total_issues = sum(len(r.get("issues", [])) for r in results)
    total_lines = sum(r.get("line_count", 0) for r in results)
    
    # Base score
    score = 10.0
    
    # Deduct for issues
    if total_lines > 0:
        issue_ratio = total_issues / total_lines * 1000  # Issues per 1000 lines
        score -= min(issue_ratio * 2, 5.0)  # Max 5 points deduction
    
    # Deduct for large files
    large_files = sum(1 for r in results if r.get("line_count", 0) > 300)
    if large_files > 0:
        score -= min(large_files * 0.5, 2.0)  # Max 2 points deduction
    
    # Deduct for missing documentation
    undocumented_files = sum(1 for r in results 
                           if any(i.get("type") == "documentation" for i in r.get("issues", [])))
    if undocumented_files > 0:
        score -= min(undocumented_files * 0.2, 1.5)  # Max 1.5 points deduction
    
    return max(0.0, score)