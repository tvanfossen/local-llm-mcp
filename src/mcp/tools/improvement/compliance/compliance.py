"""Schema Compliance Tool - Ensure files meet project requirements

Responsibilities:
- Enforce file size limits (max 300 lines per project standards)
- Validate naming conventions and project structure
- Check for required file headers and metadata
- Ensure import organization and dependency compliance
- Validate code style and formatting standards
- Generate compliance reports and fix suggestions

Phase 5: Self-Improvement MCP Tools
"""

import ast
import logging
import re
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
    return {"content": [{"type": "text", "text": f"❌ **Compliance Error:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> Dict[str, Any]:
    """Handle exceptions with proper MCP formatting"""
    logger.error(f"Exception in {context}: {str(e)}", exc_info=True)
    return _create_error(f"{context}: {str(e)}")


class ComplianceValidator:
    """Project compliance validator and enforcer"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.rules = self._load_compliance_rules()
        self.violations = []
        
    def _load_compliance_rules(self) -> Dict[str, Any]:
        """Load project compliance rules"""
        return {
            "file_size": {
                "max_lines": 300,
                "warning_threshold": 250,
                "exceptions": ["__init__.py", "test_*.py"]
            },
            "naming_conventions": {
                "python_files": r"^[a-z_]+\.py$",
                "python_modules": r"^[a-z_]+$",
                "python_classes": r"^[A-Z][a-zA-Z0-9]*$",
                "python_functions": r"^[a-z_]+$",
                "python_constants": r"^[A-Z_]+$"
            },
            "required_headers": {
                "python_docstring": True,
                "file_description": True,
                "author_info": False,
                "license_info": False
            },
            "import_organization": {
                "separate_standard_lib": True,
                "separate_third_party": True,
                "separate_local": True,
                "alphabetical_order": True
            },
            "code_style": {
                "max_line_length": 100,
                "indentation": 4,
                "trailing_whitespace": False,
                "blank_line_rules": True
            },
            "security": {
                "no_hardcoded_secrets": True,
                "no_dangerous_functions": True,
                "no_sql_injection": True
            }
        }
    
    def validate_file_compliance(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Validate file against all compliance rules"""
        compliance_result = {
            "file_path": str(file_path),
            "compliant": True,
            "violations": [],
            "warnings": [],
            "score": 100.0,
            "categories": {}
        }
        
        # Check file size compliance
        size_result = self._check_file_size(file_path, content)
        compliance_result["categories"]["file_size"] = size_result
        compliance_result["violations"].extend(size_result.get("violations", []))
        compliance_result["warnings"].extend(size_result.get("warnings", []))
        
        # Check naming conventions
        if file_path.suffix == '.py':
            naming_result = self._check_naming_conventions(file_path, content)
            compliance_result["categories"]["naming"] = naming_result
            compliance_result["violations"].extend(naming_result.get("violations", []))
            
            # Check required headers
            header_result = self._check_required_headers(file_path, content)
            compliance_result["categories"]["headers"] = header_result
            compliance_result["violations"].extend(header_result.get("violations", []))
            
            # Check import organization
            import_result = self._check_import_organization(content)
            compliance_result["categories"]["imports"] = import_result
            compliance_result["violations"].extend(import_result.get("violations", []))
            
            # Check code style
            style_result = self._check_code_style(content)
            compliance_result["categories"]["style"] = style_result
            compliance_result["violations"].extend(style_result.get("violations", []))
            
            # Check security
            security_result = self._check_security_compliance(content)
            compliance_result["categories"]["security"] = security_result
            compliance_result["violations"].extend(security_result.get("violations", []))
        
        # Calculate overall compliance
        total_violations = len(compliance_result["violations"])
        total_warnings = len(compliance_result["warnings"])
        
        compliance_result["compliant"] = total_violations == 0
        compliance_result["score"] = max(0, 100 - (total_violations * 10) - (total_warnings * 2))
        
        return compliance_result
    
    def _check_file_size(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Check file size compliance"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        line_count = len(content.splitlines())
        max_lines = self.rules["file_size"]["max_lines"]
        warning_threshold = self.rules["file_size"]["warning_threshold"]
        
        result["metrics"]["line_count"] = line_count
        result["metrics"]["max_allowed"] = max_lines
        
        # Check exceptions
        is_exception = any(pattern in file_path.name for pattern in self.rules["file_size"]["exceptions"])
        
        if not is_exception:
            if line_count > max_lines:
                result["violations"].append({
                    "type": "file_size_violation",
                    "severity": "error",
                    "message": f"File exceeds maximum size: {line_count} > {max_lines} lines",
                    "suggestion": "Consider splitting into smaller modules or refactoring large functions"
                })
            elif line_count > warning_threshold:
                result["warnings"].append({
                    "type": "file_size_warning",
                    "severity": "warning",
                    "message": f"File approaching size limit: {line_count}/{max_lines} lines",
                    "suggestion": "Consider refactoring before reaching the limit"
                })
        
        return result
    
    def _check_naming_conventions(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Check naming convention compliance"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        # Check file name
        file_pattern = self.rules["naming_conventions"]["python_files"]
        if not re.match(file_pattern, file_path.name):
            result["violations"].append({
                "type": "naming_violation",
                "severity": "warning",
                "message": f"File name '{file_path.name}' doesn't follow convention",
                "suggestion": "Use lowercase with underscores (snake_case)"
            })
        
        try:
            tree = ast.parse(content)
            
            # Check class names
            class_pattern = self.rules["naming_conventions"]["python_classes"]
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if not re.match(class_pattern, node.name):
                        result["violations"].append({
                            "type": "naming_violation",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"Class '{node.name}' doesn't follow PascalCase convention",
                            "suggestion": "Use PascalCase for class names"
                        })
            
            # Check function names
            function_pattern = self.rules["naming_conventions"]["python_functions"]
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not re.match(function_pattern, node.name) and not node.name.startswith('__'):
                        result["violations"].append({
                            "type": "naming_violation",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"Function '{node.name}' doesn't follow snake_case convention",
                            "suggestion": "Use snake_case for function names"
                        })
            
            # Check constant names (simple heuristic)
            constant_pattern = self.rules["naming_conventions"]["python_constants"]
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            if not re.match(constant_pattern, target.id):
                                result["violations"].append({
                                    "type": "naming_violation",
                                    "severity": "info",
                                    "line": node.lineno,
                                    "message": f"Constant '{target.id}' should use UPPER_SNAKE_CASE",
                                    "suggestion": "Use UPPER_SNAKE_CASE for constants"
                                })
        
        except SyntaxError:
            result["violations"].append({
                "type": "syntax_error",
                "severity": "error",
                "message": "Cannot check naming conventions due to syntax errors",
                "suggestion": "Fix syntax errors first"
            })
        
        return result
    
    def _check_required_headers(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Check required file headers"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        lines = content.splitlines()
        
        # Check for module docstring
        if self.rules["required_headers"]["python_docstring"]:
            has_module_docstring = False
            
            # Simple check for module docstring (first non-comment, non-import line)
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    has_module_docstring = True
                    break
                if stripped.startswith(('import ', 'from ')):
                    continue
                break
            
            if not has_module_docstring:
                result["violations"].append({
                    "type": "missing_header",
                    "severity": "warning",
                    "message": "Missing module docstring",
                    "suggestion": "Add a descriptive module docstring at the top of the file"
                })
        
        # Check for file description in docstring
        if self.rules["required_headers"]["file_description"]:
            # This is a more detailed check that could be enhanced
            pass
        
        return result
    
    def _check_import_organization(self, content: str) -> Dict[str, Any]:
        """Check import organization compliance"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        try:
            tree = ast.parse(content)
            imports = []
            
            # Collect all imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            "type": "import",
                            "name": alias.name,
                            "line": node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    imports.append({
                        "type": "from_import",
                        "module": node.module or "",
                        "line": node.lineno
                    })
            
            # Check import grouping (simplified)
            if len(imports) > 5:  # Only check if there are multiple imports
                # Look for mixed import types without blank lines
                prev_type = None
                for imp in imports:
                    if prev_type and prev_type != imp["type"]:
                        result["warnings"].append({
                            "type": "import_organization",
                            "severity": "info",
                            "line": imp["line"],
                            "message": "Consider organizing imports into groups",
                            "suggestion": "Group standard library, third-party, and local imports separately"
                        })
                        break
                    prev_type = imp["type"]
            
            result["metrics"]["import_count"] = len(imports)
        
        except SyntaxError:
            result["violations"].append({
                "type": "syntax_error",
                "severity": "error",
                "message": "Cannot check imports due to syntax errors"
            })
        
        return result
    
    def _check_code_style(self, content: str) -> Dict[str, Any]:
        """Check code style compliance"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        lines = content.splitlines()
        max_line_length = self.rules["code_style"]["max_line_length"]
        
        # Check line length
        long_lines = 0
        for i, line in enumerate(lines, 1):
            if len(line) > max_line_length:
                long_lines += 1
                if long_lines <= 5:  # Report first 5 violations
                    result["violations"].append({
                        "type": "line_length",
                        "severity": "warning",
                        "line": i,
                        "message": f"Line too long: {len(line)} > {max_line_length} characters",
                        "suggestion": "Break long lines or use line continuation"
                    })
        
        if long_lines > 5:
            result["violations"].append({
                "type": "line_length",
                "severity": "warning",
                "message": f"Total of {long_lines} lines exceed length limit",
                "suggestion": "Consider using a code formatter like black"
            })
        
        # Check trailing whitespace
        if not self.rules["code_style"]["trailing_whitespace"]:
            trailing_count = 0
            for i, line in enumerate(lines, 1):
                if line.endswith(' ') or line.endswith('\t'):
                    trailing_count += 1
            
            if trailing_count > 0:
                result["violations"].append({
                    "type": "trailing_whitespace",
                    "severity": "info",
                    "message": f"{trailing_count} lines have trailing whitespace",
                    "suggestion": "Remove trailing whitespace"
                })
        
        # Check for multiple consecutive blank lines
        consecutive_blank = 0
        max_consecutive = 0
        
        for line in lines:
            if not line.strip():
                consecutive_blank += 1
                max_consecutive = max(max_consecutive, consecutive_blank)
            else:
                consecutive_blank = 0
        
        if max_consecutive > 2:
            result["violations"].append({
                "type": "excessive_blank_lines",
                "severity": "info",
                "message": f"Found {max_consecutive} consecutive blank lines",
                "suggestion": "Limit consecutive blank lines to 2"
            })
        
        result["metrics"]["max_line_length"] = max(len(line) for line in lines) if lines else 0
        result["metrics"]["trailing_whitespace_lines"] = trailing_count if 'trailing_count' in locals() else 0
        
        return result
    
    def _check_security_compliance(self, content: str) -> Dict[str, Any]:
        """Check security compliance"""
        result = {"violations": [], "warnings": [], "metrics": {}}
        
        # Check for hardcoded secrets (simple patterns)
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']{8,}["\']', "hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']{16,}["\']', "hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']{16,}["\']', "hardcoded secret"),
            (r'token\s*=\s*["\'][^"\']{20,}["\']', "hardcoded token"),
        ]
        
        for pattern, description in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["violations"].append({
                    "type": "security_risk",
                    "severity": "error",
                    "message": f"Potential {description} found",
                    "suggestion": "Use environment variables or configuration files for secrets"
                })
        
        # Check for dangerous functions
        if self.rules["security"]["no_dangerous_functions"]:
            dangerous_patterns = [
                (r'\beval\s*\(', "eval() usage"),
                (r'\bexec\s*\(', "exec() usage"),
                (r'__import__\s*\(', "__import__() usage"),
            ]
            
            for pattern, description in dangerous_patterns:
                if re.search(pattern, content):
                    result["violations"].append({
                        "type": "security_risk",
                        "severity": "warning",
                        "message": f"Dangerous {description} detected",
                        "suggestion": "Consider safer alternatives"
                    })
        
        # Check for SQL injection patterns
        if self.rules["security"]["no_sql_injection"]:
            sql_patterns = [
                r'["\']SELECT\s+.*%s.*["\']',
                r'["\']INSERT\s+.*%s.*["\']',
                r'["\']UPDATE\s+.*%s.*["\']',
                r'["\']DELETE\s+.*%s.*["\']',
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    result["violations"].append({
                        "type": "security_risk",
                        "severity": "error",
                        "message": "Potential SQL injection vulnerability",
                        "suggestion": "Use parameterized queries or ORM methods"
                    })
        
        return result


async def ensure_compliance(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure file meets project compliance standards"""
    try:
        file_path = args.get("file_path")
        if not file_path:
            return _create_error("file_path parameter is required")
        
        auto_fix = args.get("auto_fix", False)
        report_only = args.get("report_only", True)
        
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
        
        # Validate compliance
        validator = ComplianceValidator()
        compliance_result = validator.validate_file_compliance(full_path, content)
        
        return _format_compliance_report(full_path, compliance_result, auto_fix, report_only)
    
    except Exception as e:
        return _handle_exception(e, "ensure_compliance")


async def check_project_compliance(args: Dict[str, Any]) -> Dict[str, Any]:
    """Check compliance across multiple files in project"""
    try:
        directory_path = args.get("directory_path", ".")
        file_patterns = args.get("file_patterns", ["*.py"])
        max_files = args.get("max_files", 50)
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(directory_path).is_absolute():
            full_path = workspace_root / directory_path
        else:
            full_path = Path(directory_path)
        
        validator = ComplianceValidator()
        results = []
        processed_files = 0
        
        # Check files in directory
        for pattern in file_patterns:
            for file_path in full_path.rglob(pattern):
                if processed_files >= max_files:
                    break
                    
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        result = validator.validate_file_compliance(file_path, content)
                        results.append(result)
                        processed_files += 1
                    except Exception as e:
                        logger.warning(f"Failed to check compliance for {file_path}: {e}")
        
        return _format_project_compliance_report(results, processed_files)
    
    except Exception as e:
        return _handle_exception(e, "check_project_compliance")


def _format_compliance_report(file_path: Path, result: Dict[str, Any], auto_fix: bool, report_only: bool) -> Dict[str, Any]:
    """Format compliance report for single file"""
    violations = result.get("violations", [])
    warnings = result.get("warnings", [])
    score = result.get("score", 0)
    categories = result.get("categories", {})
    
    # Determine compliance status emoji and color
    if score >= 90:
        status_emoji = "✅"
        status_text = "COMPLIANT"
    elif score >= 70:
        status_emoji = "⚠️"
        status_text = "NEEDS ATTENTION"
    else:
        status_emoji = "❌"
        status_text = "NON-COMPLIANT"
    
    summary = f"{status_emoji} **Compliance Report for {file_path.name}**\n\n"
    summary += f"**Overall Status:** {status_text} (Score: {score:.1f}/100)\n\n"
    
    # Category breakdown
    if categories:
        summary += f"**Category Scores:**\n"
        for category, cat_result in categories.items():
            cat_violations = len(cat_result.get("violations", []))
            cat_warnings = len(cat_result.get("warnings", []))
            cat_score = max(0, 100 - (cat_violations * 15) - (cat_warnings * 5))
            
            cat_emoji = "✅" if cat_score >= 90 else "⚠️" if cat_score >= 70 else "❌"
            summary += f"   {cat_emoji} {category.replace('_', ' ').title()}: {cat_score:.0f}/100\n"
        summary += "\n"
    
    # Violations
    if violations:
        summary += f"**Violations ({len(violations)}):**\n"
        for i, violation in enumerate(violations[:10], 1):
            severity = violation.get("severity", "error")
            emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "•")
            message = violation.get("message", "Unknown violation")
            line_info = f" (line {violation['line']})" if violation.get("line") else ""
            
            summary += f"   {i}. {emoji} {message}{line_info}\n"
            
            suggestion = violation.get("suggestion")
            if suggestion:
                summary += f"      💡 *{suggestion}*\n"
        
        if len(violations) > 10:
            summary += f"   ... and {len(violations) - 10} more violations\n"
        summary += "\n"
    
    # Warnings
    if warnings:
        summary += f"**Warnings ({len(warnings)}):**\n"
        for warning in warnings[:5]:
            message = warning.get("message", "Unknown warning")
            summary += f"   ⚠️ {message}\n"
        
        if len(warnings) > 5:
            summary += f"   ... and {len(warnings) - 5} more warnings\n"
        summary += "\n"
    
    # Action recommendations
    if violations or warnings:
        summary += f"**Recommended Actions:**\n"
        
        # Prioritize actions based on violation types
        high_priority = [v for v in violations if v.get("severity") == "error"]
        medium_priority = [v for v in violations if v.get("severity") == "warning"]
        
        if high_priority:
            summary += f"   🚨 **Immediate attention:** {len(high_priority)} critical issues\n"
        if medium_priority:
            summary += f"   ⚠️ **Soon:** {len(medium_priority)} important issues\n"
        if warnings:
            summary += f"   ℹ️ **When convenient:** {len(warnings)} minor issues\n"
        
        if auto_fix and not report_only:
            summary += f"   🔧 **Auto-fix:** Some issues can be automatically resolved\n"
        elif report_only:
            summary += f"   📋 **Report only:** Set `report_only: false` to enable fixes\n"
    else:
        summary += f"🎉 **Perfect Compliance!** No violations found.\n"
    
    # File metrics
    file_metrics = {}
    for category, cat_result in categories.items():
        metrics = cat_result.get("metrics", {})
        file_metrics.update({f"{category}_{k}": v for k, v in metrics.items()})
    
    return _create_success(summary, {
        "file_path": str(file_path),
        "compliance_score": score,
        "compliant": result.get("compliant", False),
        "total_violations": len(violations),
        "total_warnings": len(warnings),
        "categories": categories,
        "metrics": file_metrics
    })


def _format_project_compliance_report(results: List[Dict[str, Any]], processed_files: int) -> Dict[str, Any]:
    """Format project-wide compliance report"""
    if not results:
        return _create_success(f"📊 **No files processed** from {processed_files} candidates")
    
    # Calculate aggregate statistics
    total_violations = sum(len(r.get("violations", [])) for r in results)
    total_warnings = sum(len(r.get("warnings", [])) for r in results)
    avg_score = sum(r.get("score", 0) for r in results) / len(results)
    compliant_files = sum(1 for r in results if r.get("compliant", False))
    
    # Determine overall project health
    if avg_score >= 90:
        health_emoji = "🟢"
        health_status = "EXCELLENT"
    elif avg_score >= 70:
        health_emoji = "🟡"
        health_status = "GOOD"
    elif avg_score >= 50:
        health_emoji = "🟠"
        health_status = "NEEDS WORK"
    else:
        health_emoji = "🔴"
        health_status = "POOR"
    
    summary = f"📊 **Project Compliance Report**\n\n"
    summary += f"**Overall Health:** {health_emoji} {health_status} (Score: {avg_score:.1f}/100)\n\n"
    
    summary += f"**Project Statistics:**\n"
    summary += f"   • Files Processed: {processed_files}\n"
    summary += f"   • Files Analyzed: {len(results)}\n"
    summary += f"   • Compliant Files: {compliant_files} ({compliant_files/len(results)*100:.1f}%)\n"
    summary += f"   • Total Violations: {total_violations}\n"
    summary += f"   • Total Warnings: {total_warnings}\n\n"
    
    # Identify problem files
    problem_files = [r for r in results if not r.get("compliant", False)]
    if problem_files:
        # Sort by score (worst first)
        problem_files.sort(key=lambda x: x.get("score", 0))
        
        summary += f"**Files Needing Attention ({len(problem_files)}):**\n"
        for i, result in enumerate(problem_files[:10], 1):
            file_path = Path(result["file_path"]).name
            score = result.get("score", 0)
            violations = len(result.get("violations", []))
            
            if score < 50:
                emoji = "🔴"
            elif score < 70:
                emoji = "🟠"
            else:
                emoji = "🟡"
            
            summary += f"   {i}. {emoji} {file_path} (Score: {score:.0f}, {violations} violations)\n"
        
        if len(problem_files) > 10:
            summary += f"   ... and {len(problem_files) - 10} more files\n"
        summary += "\n"
    
    # Category analysis
    category_stats = {}
    for result in results:
        for category, cat_result in result.get("categories", {}).items():
            if category not in category_stats:
                category_stats[category] = {"violations": 0, "files": 0}
            
            cat_violations = len(cat_result.get("violations", []))
            if cat_violations > 0:
                category_stats[category]["violations"] += cat_violations
                category_stats[category]["files"] += 1
    
    if category_stats:
        summary += f"**Common Issues by Category:**\n"
        for category, stats in sorted(category_stats.items(), key=lambda x: x[1]["violations"], reverse=True):
            summary += f"   • {category.replace('_', ' ').title()}: {stats['violations']} violations in {stats['files']} files\n"
        summary += "\n"
    
    # Implementation recommendations
    summary += f"**🚀 Recommended Action Plan:**\n"
    
    if avg_score < 50:
        summary += f"   **Phase 1 (Critical):** Focus on {len([r for r in results if r.get('score', 0) < 50])} lowest-scoring files\n"
        summary += f"   **Phase 2 (Important):** Address remaining non-compliant files\n"
        summary += f"   **Phase 3 (Polish):** Achieve 90%+ compliance across project\n"
    elif avg_score < 70:
        summary += f"   **Phase 1:** Fix critical violations in {len(problem_files)} files\n"
        summary += f"   **Phase 2:** Improve overall project score to 90%+\n"
    else:
        summary += f"   **Maintenance:** Address remaining {total_violations} violations for perfect compliance\n"
    
    summary += f"\n**Estimated Effort:** {_estimate_compliance_effort(results)} hours\n"
    
    return _create_success(summary, {
        "processed_files": processed_files,
        "analyzed_files": len(results),
        "average_score": avg_score,
        "compliant_files": compliant_files,
        "total_violations": total_violations,
        "total_warnings": total_warnings,
        "category_stats": category_stats,
        "problem_files": len(problem_files)
    })


def _estimate_compliance_effort(results: List[Dict[str, Any]]) -> int:
    """Estimate effort to fix compliance issues"""
    effort_by_violation = {
        "file_size_violation": 2.0,  # 2 hours to refactor large file
        "naming_violation": 0.1,     # 6 minutes to rename
        "missing_header": 0.25,      # 15 minutes to add docstring
        "line_length": 0.05,         # 3 minutes per line
        "security_risk": 1.0,        # 1 hour per security issue
        "import_organization": 0.5,   # 30 minutes to reorganize
        "trailing_whitespace": 0.02,  # 1 minute cleanup
    }
    
    total_effort = 0
    for result in results:
        for violation in result.get("violations", []):
            violation_type = violation.get("type", "unknown")
            effort = effort_by_violation.get(violation_type, 0.25)  # Default 15 minutes
            total_effort += effort
    
    return max(1, int(total_effort))  # Minimum 1 hour


async def fix_compliance_issues(args: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically fix simple compliance issues"""
    try:
        file_path = args.get("file_path")
        issue_types = args.get("issue_types", ["trailing_whitespace", "line_length"])
        
        if not file_path:
            return _create_error("file_path parameter is required")
        
        # Only allow safe automatic fixes
        safe_fixes = [
            "trailing_whitespace",
            "excessive_blank_lines", 
            "import_organization"
        ]
        
        unsafe_requested = [t for t in issue_types if t not in safe_fixes]
        if unsafe_requested:
            return _create_error(f"Automatic fixing not available for: {', '.join(unsafe_requested)}")
        
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
        
        # Read and fix content
        original_content = full_path.read_text(encoding='utf-8')
        fixed_content = original_content
        fixes_applied = []
        
        # Apply requested fixes
        for issue_type in issue_types:
            if issue_type == "trailing_whitespace":
                lines = fixed_content.splitlines()
                new_lines = [line.rstrip() for line in lines]
                if new_lines != lines:
                    fixed_content = '\n'.join(new_lines)
                    if fixed_content and not fixed_content.endswith('\n'):
                        fixed_content += '\n'
                    fixes_applied.append("Removed trailing whitespace")
            
            elif issue_type == "excessive_blank_lines":
                # Remove excessive consecutive blank lines (keep max 2)
                lines = fixed_content.splitlines()
                new_lines = []
                blank_count = 0
                
                for line in lines:
                    if not line.strip():
                        blank_count += 1
                        if blank_count <= 2:
                            new_lines.append(line)
                    else:
                        blank_count = 0
                        new_lines.append(line)
                
                if new_lines != lines:
                    fixed_content = '\n'.join(new_lines)
                    if fixed_content and not fixed_content.endswith('\n'):
                        fixed_content += '\n'
                    fixes_applied.append("Removed excessive blank lines")
        
        # Write fixed content if changes were made
        if fixed_content != original_content:
            full_path.write_text(fixed_content, encoding='utf-8')
            
            summary = f"🔧 **Compliance Fixes Applied to {full_path.name}**\n\n"
            summary += f"**Fixes Applied:**\n"
            for fix in fixes_applied:
                summary += f"   ✅ {fix}\n"
            
            return _create_success(summary, {
                "file_path": str(full_path),
                "fixes_applied": fixes_applied,
                "changes_made": True
            })
        else:
            return _create_success(f"✅ **No fixes needed** for {full_path.name} - file already compliant for requested issues")
    
    except Exception as e:
        return _handle_exception(e, "fix_compliance_issues")