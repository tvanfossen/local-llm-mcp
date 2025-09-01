#!/usr/bin/env python3
"""Documentation coverage checker."""

import argparse
import ast
import sys
from pathlib import Path


def check_doc_coverage(filepath: Path, min_coverage: float) -> bool:
    """Check documentation coverage of Python file."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    total = 0
    documented = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
            total += 1
            if ast.get_docstring(node):
                documented += 1

    coverage = (documented / total * 100) if total > 0 else 100
    return coverage >= min_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--min-coverage", type=float, default=80)
    args = parser.parse_args()

    for filename in args.files:
        if not check_doc_coverage(Path(filename), args.min_coverage):
            sys.exit(1)


if __name__ == "__main__":
    main()
