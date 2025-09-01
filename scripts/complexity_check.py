#!/usr/bin/env python3
# File: ~/Projects/local-llm-mcp/scripts/complexity_check.py
"""Cyclomatic Complexity Checker
Analyzes Python code complexity and reports violations
"""

import argparse
import ast
import sys
from pathlib import Path


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor to calculate cyclomatic complexity"""

    def __init__(self):
        self.functions = []
        self.current_function = None
        self.current_complexity = 0

    def visit_FunctionDef(self, node):
        """Visit function definition"""
        parent_function = self.current_function
        parent_complexity = self.current_complexity

        self.current_function = node.name
        self.current_complexity = 1  # Base complexity

        # Visit function body
        self.generic_visit(node)

        # Store results
        self.functions.append(
            (
                node.name,
                node.lineno,
                self.current_complexity,
            )
        )

        # Restore parent context
        self.current_function = parent_function
        self.current_complexity = parent_complexity

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        """Each if statement adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        """Each while loop adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        """Each for loop adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        """Each except clause adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        """Each with statement adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        """Each assert adds 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        """Each boolean operator adds to complexity"""
        if isinstance(node.op, (ast.And, ast.Or)):
            self.current_complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Lambda(self, node):
        """Lambda expressions add 1 to complexity"""
        self.current_complexity += 1
        self.generic_visit(node)


def check_file_complexity(filepath: Path, max_complexity: int) -> list[tuple[str, int, int]]:
    """Check complexity of a Python file

    Returns:
        List of (function_name, line_number, complexity) for violations
    """
    violations = []

    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(filepath))
        visitor = ComplexityVisitor()
        visitor.visit(tree)

        for func_name, line_no, complexity in visitor.functions:
            if complexity > max_complexity:
                violations.append((func_name, line_no, complexity))

    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    return violations


def main():
    parser = argparse.ArgumentParser(description="Check cyclomatic complexity")
    parser.add_argument("files", nargs="+", help="Python files to check")
    parser.add_argument(
        "--max-complexity", type=int, default=10, help="Maximum allowed complexity (default: 10)"
    )

    args = parser.parse_args()
    exit_code = _process_files(args.files, args.max_complexity)
    sys.exit(exit_code)


def _process_files(files: list[str], max_complexity: int) -> int:
    """Process files and return exit code"""
    exit_code = 0

    for filename in files:
        filepath = Path(filename)
        if not filepath.exists():
            continue

        violations = check_file_complexity(filepath, max_complexity)

        if violations:
            exit_code = 1
            _print_violations(filename, violations, max_complexity)

    return exit_code


def _print_violations(filename: str, violations: list, max_complexity: int):
    """Print complexity violations for a file"""
    print(f"Complexity violations in {filename}:")
    for func_name, line_no, complexity in violations:
        print(
            f"  Line {line_no}: {func_name}() has complexity {complexity} (max allowed: {max_complexity})"
        )


if __name__ == "__main__":
    main()
