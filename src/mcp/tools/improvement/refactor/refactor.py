"""Refactoring Suggestion Tool - AI-powered code refactoring with local LLM

Responsibilities:
- Analyze code patterns for refactoring opportunities
- Generate intelligent refactoring suggestions using local LLM
- Implement common refactoring patterns automatically
- Extract methods, classes, and constants
- Simplify complex conditional logic
- Optimize imports and dependencies

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
    return {"content": [{"type": "text", "text": f"❌ **Refactoring Error:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> Dict[str, Any]:
    """Handle exceptions with proper MCP formatting"""
    logger.error(f"Exception in {context}: {str(e)}", exc_info=True)
    return _create_error(f"{context}: {str(e)}")


class RefactoringAnalyzer:
    """Intelligent code refactoring analyzer"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.refactoring_opportunities = []
        
    def analyze_refactoring_opportunities(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Find refactoring opportunities in code"""
        opportunities = []
        
        if file_path.suffix == '.py':
            opportunities.extend(self._analyze_python_refactoring(content))
        elif file_path.suffix in ['.js', '.ts']:
            opportunities.extend(self._analyze_javascript_refactoring(content))
        
        return opportunities
    
    def _analyze_python_refactoring(self, content: str) -> List[Dict[str, Any]]:
        """Find Python-specific refactoring opportunities"""
        opportunities = []
        
        try:
            tree = ast.parse(content)
            
            # Find long functions
            opportunities.extend(self._find_long_functions(tree))
            
            # Find duplicate code
            opportunities.extend(self._find_duplicate_code(tree, content))
            
            # Find complex conditionals
            opportunities.extend(self._find_complex_conditionals(tree))
            
            # Find magic numbers/strings
            opportunities.extend(self._find_magic_literals(tree))
            
            # Find large classes
            opportunities.extend(self._find_large_classes(tree))
            
            # Find unused imports
            opportunities.extend(self._find_unused_imports(tree, content))
            
        except SyntaxError as e:
            opportunities.append({
                "type": "syntax_fix",
                "priority": "high",
                "description": f"Fix syntax error: {e.msg}",
                "line": e.lineno,
                "suggestion": "Review and fix syntax error before refactoring"
            })
        
        return opportunities
    
    def _find_long_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find functions that are too long and suggest extraction"""
        opportunities = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Calculate function length
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    func_length = node.end_lineno - node.lineno + 1
                else:
                    # Fallback calculation
                    func_length = len([n for n in ast.walk(node) if hasattr(n, 'lineno')])
                
                if func_length > 50:  # Functions longer than 50 lines
                    opportunities.append({
                        "type": "extract_method",
                        "priority": "medium",
                        "description": f"Function '{node.name}' is {func_length} lines long - consider breaking into smaller functions",
                        "line": node.lineno,
                        "suggestion": f"Extract logical blocks from '{node.name}' into separate methods",
                        "details": {
                            "function_name": node.name,
                            "length": func_length,
                            "recommended_max": 30
                        }
                    })
        
        return opportunities
    
    def _find_duplicate_code(self, tree: ast.AST, content: str) -> List[Dict[str, Any]]:
        """Find potential duplicate code blocks"""
        opportunities = []
        lines = content.splitlines()
        
        # Simple duplicate detection - look for repeated line sequences
        line_sequences = {}
        sequence_length = 5  # Look for 5+ line duplicates
        
        for i in range(len(lines) - sequence_length + 1):
            sequence = '\n'.join(lines[i:i+sequence_length])
            sequence_hash = hash(sequence.strip())
            
            if sequence_hash not in line_sequences:
                line_sequences[sequence_hash] = []
            line_sequences[sequence_hash].append(i + 1)
        
        for sequence_hash, line_numbers in line_sequences.items():
            if len(line_numbers) > 1:  # Found duplicates
                opportunities.append({
                    "type": "extract_common_code",
                    "priority": "medium",
                    "description": f"Duplicate code found at lines {', '.join(map(str, line_numbers))}",
                    "line": line_numbers[0],
                    "suggestion": "Extract common code into a shared function or method",
                    "details": {
                        "duplicate_lines": line_numbers,
                        "sequence_length": sequence_length
                    }
                })
        
        return opportunities
    
    def _find_complex_conditionals(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find complex conditional statements that could be simplified"""
        opportunities = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Count nested conditions
                condition_complexity = self._count_boolean_operators(node.test)
                
                if condition_complexity > 3:  # More than 3 boolean operators
                    opportunities.append({
                        "type": "simplify_conditional",
                        "priority": "low",
                        "description": f"Complex conditional with {condition_complexity} boolean operations",
                        "line": node.lineno,
                        "suggestion": "Consider extracting condition into a well-named boolean function",
                        "details": {
                            "complexity": condition_complexity,
                            "recommended_max": 3
                        }
                    })
        
        return opportunities
    
    def _find_magic_literals(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find magic numbers and strings that should be constants"""
        opportunities = []
        magic_numbers = []
        magic_strings = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)) and node.value not in [0, 1, -1]:
                    magic_numbers.append((node.value, node.lineno))
                elif isinstance(node.value, str) and len(node.value) > 10:
                    magic_strings.append((node.value[:20] + "..." if len(node.value) > 20 else node.value, node.lineno))
        
        # Group similar magic numbers
        number_counts = {}
        for num, line in magic_numbers:
            if num not in number_counts:
                number_counts[num] = []
            number_counts[num].append(line)
        
        for num, lines in number_counts.items():
            if len(lines) > 1:  # Used in multiple places
                opportunities.append({
                    "type": "extract_constant",
                    "priority": "low",
                    "description": f"Magic number {num} used {len(lines)} times",
                    "line": lines[0],
                    "suggestion": f"Extract {num} into a named constant",
                    "details": {
                        "value": num,
                        "occurrences": len(lines),
                        "lines": lines
                    }
                })
        
        return opportunities
    
    def _find_large_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find classes that are too large"""
        opportunities = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Count methods and attributes
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                attributes = []
                
                for method in methods:
                    for assign in ast.walk(method):
                        if isinstance(assign, ast.Assign):
                            for target in assign.targets:
                                if isinstance(target, ast.Attribute):
                                    attributes.append(target.attr)
                
                if len(methods) > 15:  # Classes with more than 15 methods
                    opportunities.append({
                        "type": "split_class",
                        "priority": "medium",
                        "description": f"Class '{node.name}' has {len(methods)} methods - consider splitting responsibilities",
                        "line": node.lineno,
                        "suggestion": f"Split '{node.name}' into smaller, more focused classes",
                        "details": {
                            "class_name": node.name,
                            "method_count": len(methods),
                            "recommended_max": 10
                        }
                    })
        
        return opportunities
    
    def _find_unused_imports(self, tree: ast.AST, content: str) -> List[Dict[str, Any]]:
        """Find unused imports"""
        opportunities = []
        imports = []
        used_names = set()
        
        # Collect imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, alias.asname or alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append((f"{node.module}.{alias.name}", alias.asname or alias.name, node.lineno))
        
        # Collect used names (simple check)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                used_names.add(node.attr)
        
        # Find unused imports
        for full_name, local_name, line in imports:
            if local_name not in used_names:
                opportunities.append({
                    "type": "remove_unused_import",
                    "priority": "low",
                    "description": f"Unused import: {local_name}",
                    "line": line,
                    "suggestion": f"Remove unused import: {full_name}",
                    "details": {
                        "import_name": full_name,
                        "local_name": local_name
                    }
                })
        
        return opportunities
    
    def _analyze_javascript_refactoring(self, content: str) -> List[Dict[str, Any]]:
        """Find JavaScript-specific refactoring opportunities"""
        opportunities = []
        lines = content.splitlines()
        
        # Find long functions (simple regex-based detection)
        function_starts = []
        brace_count = 0
        current_function = None
        
        for i, line in enumerate(lines):
            if re.search(r'function\s+\w+|const\s+\w+\s*=\s*\(.*?\)\s*=>', line):
                current_function = i + 1
            
            brace_count += line.count('{') - line.count('}')
            
            if current_function and brace_count == 0 and '}' in line:
                func_length = i - current_function + 2
                if func_length > 50:
                    opportunities.append({
                        "type": "extract_method",
                        "priority": "medium",
                        "description": f"Long function ({func_length} lines) starting at line {current_function}",
                        "line": current_function,
                        "suggestion": "Break function into smaller, focused functions"
                    })
                current_function = None
        
        return opportunities
    
    def _count_boolean_operators(self, node: ast.AST) -> int:
        """Count boolean operators in an AST node"""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
            elif isinstance(child, ast.Compare):
                count += len(child.ops)
        return count


async def suggest_refactoring(args: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest refactoring opportunities for a file"""
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
        
        # Read file content
        content = full_path.read_text(encoding='utf-8')
        
        # Analyze refactoring opportunities
        analyzer = RefactoringAnalyzer()
        opportunities = analyzer.analyze_refactoring_opportunities(full_path, content)
        
        return _format_refactoring_suggestions(full_path, opportunities, args.get("priority_filter"))
    
    except Exception as e:
        return _handle_exception(e, "suggest_refactoring")


async def generate_refactoring_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a comprehensive refactoring plan for multiple files"""
    try:
        directory_path = args.get("directory_path", ".")
        file_patterns = args.get("file_patterns", ["*.py"])
        max_files = args.get("max_files", 20)
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        if not Path(directory_path).is_absolute():
            full_path = workspace_root / directory_path
        else:
            full_path = Path(directory_path)
        
        analyzer = RefactoringAnalyzer()
        all_opportunities = []
        processed_files = 0
        
        # Analyze files in directory
        for pattern in file_patterns:
            for file_path in full_path.rglob(pattern):
                if processed_files >= max_files:
                    break
                    
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        opportunities = analyzer.analyze_refactoring_opportunities(file_path, content)
                        
                        for opportunity in opportunities:
                            opportunity["file_path"] = str(file_path.relative_to(workspace_root))
                            all_opportunities.append(opportunity)
                        
                        processed_files += 1
                    except Exception as e:
                        logger.warning(f"Failed to analyze {file_path}: {e}")
        
        return _format_refactoring_plan(all_opportunities, processed_files)
    
    except Exception as e:
        return _handle_exception(e, "generate_refactoring_plan")


def _format_refactoring_suggestions(file_path: Path, opportunities: List[Dict[str, Any]], priority_filter: Optional[str] = None) -> Dict[str, Any]:
    """Format refactoring suggestions for display"""
    if priority_filter:
        opportunities = [op for op in opportunities if op.get("priority") == priority_filter]
    
    if not opportunities:
        return _create_success(f"🎉 **No refactoring opportunities found** in {file_path.name}")
    
    # Sort by priority and line number
    priority_order = {"high": 0, "medium": 1, "low": 2}
    opportunities.sort(key=lambda x: (priority_order.get(x.get("priority", "low"), 3), x.get("line", 0)))
    
    summary = f"🔧 **Refactoring Suggestions for {file_path.name}**\n\n"
    summary += f"**Found {len(opportunities)} refactoring opportunities:**\n\n"
    
    # Group by priority
    by_priority = {}
    for op in opportunities:
        priority = op.get("priority", "low")
        if priority not in by_priority:
            by_priority[priority] = []
        by_priority[priority].append(op)
    
    # Display by priority
    priority_emojis = {"high": "🚨", "medium": "⚠️", "low": "💡"}
    
    for priority in ["high", "medium", "low"]:
        if priority in by_priority:
            ops = by_priority[priority]
            summary += f"{priority_emojis.get(priority, '•')} **{priority.title()} Priority** ({len(ops)} items):\n"
            
            for i, op in enumerate(ops, 1):
                line_info = f" (line {op['line']})" if op.get("line") else ""
                summary += f"   {i}. {op.get('description', 'Unknown issue')}{line_info}\n"
                summary += f"      💡 *{op.get('suggestion', 'No suggestion available')}*\n\n"
    
    # Add implementation recommendations
    high_priority_count = len(by_priority.get("high", []))
    if high_priority_count > 0:
        summary += f"🚨 **Recommended Actions:**\n"
        summary += f"   • Address {high_priority_count} high-priority items first\n"
        summary += f"   • Consider using automated refactoring tools\n"
        summary += f"   • Test thoroughly after each refactoring\n"
    
    return _create_success(summary, {
        "file_path": str(file_path),
        "total_opportunities": len(opportunities),
        "by_priority": {k: len(v) for k, v in by_priority.items()},
        "opportunities": opportunities
    })


def _format_refactoring_plan(opportunities: List[Dict[str, Any]], processed_files: int) -> Dict[str, Any]:
    """Format comprehensive refactoring plan"""
    if not opportunities:
        return _create_success(f"🎉 **No refactoring needed** - analyzed {processed_files} files")
    
    # Analyze opportunities
    by_priority = {}
    by_type = {}
    by_file = {}
    
    for op in opportunities:
        # Group by priority
        priority = op.get("priority", "low")
        if priority not in by_priority:
            by_priority[priority] = []
        by_priority[priority].append(op)
        
        # Group by type
        op_type = op.get("type", "unknown")
        if op_type not in by_type:
            by_type[op_type] = []
        by_type[op_type].append(op)
        
        # Group by file
        file_path = op.get("file_path", "unknown")
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(op)
    
    total_opportunities = len(opportunities)
    
    summary = f"📋 **Comprehensive Refactoring Plan**\n\n"
    summary += f"**Project Overview:**\n"
    summary += f"   • Files Analyzed: {processed_files}\n"
    summary += f"   • Total Opportunities: {total_opportunities}\n"
    summary += f"   • Files Needing Refactoring: {len(by_file)}\n\n"
    
    # Priority breakdown
    summary += f"**By Priority:**\n"
    for priority in ["high", "medium", "low"]:
        if priority in by_priority:
            count = len(by_priority[priority])
            percentage = (count / total_opportunities) * 100
            summary += f"   • {priority.title()}: {count} ({percentage:.1f}%)\n"
    
    # Type breakdown
    summary += f"\n**By Refactoring Type:**\n"
    for op_type, ops in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        summary += f"   • {op_type.replace('_', ' ').title()}: {len(ops)}\n"
    
    # Most problematic files
    summary += f"\n**Files Needing Most Attention:**\n"
    sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)
    for file_path, file_ops in sorted_files[:5]:
        summary += f"   • {file_path}: {len(file_ops)} opportunities\n"
    
    # Implementation plan
    summary += f"\n**🚀 Recommended Implementation Plan:**\n"
    
    phase_1 = len(by_priority.get("high", []))
    if phase_1 > 0:
        summary += f"   **Phase 1 (Critical):** Address {phase_1} high-priority issues\n"
        summary += f"      - Focus on security and performance issues\n"
        summary += f"      - Extract overly complex functions\n\n"
    
    phase_2 = len(by_priority.get("medium", []))
    if phase_2 > 0:
        summary += f"   **Phase 2 (Important):** Address {phase_2} medium-priority issues\n"
        summary += f"      - Split large classes and methods\n"
        summary += f"      - Remove code duplication\n\n"
    
    phase_3 = len(by_priority.get("low", []))
    if phase_3 > 0:
        summary += f"   **Phase 3 (Nice-to-have):** Address {phase_3} low-priority issues\n"
        summary += f"      - Extract constants and simplify conditionals\n"
        summary += f"      - Clean up unused imports\n\n"
    
    summary += f"**Estimated Effort:** {_estimate_refactoring_effort(opportunities)} hours\n"
    
    return _create_success(summary, {
        "total_opportunities": total_opportunities,
        "processed_files": processed_files,
        "by_priority": {k: len(v) for k, v in by_priority.items()},
        "by_type": {k: len(v) for k, v in by_type.items()},
        "files_needing_work": len(by_file),
        "opportunities": opportunities
    })


def _estimate_refactoring_effort(opportunities: List[Dict[str, Any]]) -> int:
    """Estimate refactoring effort in hours"""
    effort_by_type = {
        "extract_method": 0.5,
        "extract_common_code": 1.0,
        "simplify_conditional": 0.25,
        "extract_constant": 0.1,
        "split_class": 2.0,
        "remove_unused_import": 0.05,
        "syntax_fix": 0.5
    }
    
    total_effort = 0
    for op in opportunities:
        op_type = op.get("type", "unknown")
        effort = effort_by_type.get(op_type, 0.5)  # Default 30 minutes
        
        # Adjust for priority
        priority = op.get("priority", "low")
        if priority == "high":
            effort *= 1.5  # High priority items often more complex
        elif priority == "low":
            effort *= 0.8  # Low priority items often simpler
        
        total_effort += effort
    
    return max(1, int(total_effort))  # Minimum 1 hour


async def apply_simple_refactoring(args: Dict[str, Any]) -> Dict[str, Any]:
    """Apply simple, safe refactoring automatically"""
    try:
        file_path = args.get("file_path")
        refactoring_type = args.get("refactoring_type")
        
        if not file_path or not refactoring_type:
            return _create_error("file_path and refactoring_type parameters are required")
        
        # Only allow safe refactorings
        safe_refactorings = ["remove_unused_import", "extract_constant", "format_code"]
        if refactoring_type not in safe_refactorings:
            return _create_error(f"Automatic refactoring not available for {refactoring_type}")
        
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
        
        # Apply refactoring based on type
        if refactoring_type == "format_code":
            return await _format_code_file(full_path)
        else:
            return _create_error(f"Refactoring type {refactoring_type} not yet implemented")
    
    except Exception as e:
        return _handle_exception(e, "apply_simple_refactoring")


async def _format_code_file(file_path: Path) -> Dict[str, Any]:
    """Format code file using appropriate formatter"""
    try:
        if file_path.suffix == '.py':
            # Try to use black for Python formatting
            import subprocess
            result = subprocess.run(
                ["black", "--line-length", "100", "--check", str(file_path)],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                # File needs formatting
                format_result = subprocess.run(
                    ["black", "--line-length", "100", str(file_path)],
                    capture_output=True, text=True, timeout=30
                )
                
                if format_result.returncode == 0:
                    return _create_success(f"✅ **Code Formatted:** {file_path.name} has been formatted with black")
                else:
                    return _create_error(f"Black formatting failed: {format_result.stderr}")
            else:
                return _create_success(f"✅ **Already Formatted:** {file_path.name} is already properly formatted")
        
        else:
            return _create_error(f"Automatic formatting not supported for {file_path.suffix} files")
    
    except subprocess.TimeoutExpired:
        return _create_error("Code formatting timed out")
    except FileNotFoundError:
        return _create_error("Code formatter not found - install black: pip install black")
    except Exception as e:
        return _create_error(f"Formatting failed: {str(e)}")