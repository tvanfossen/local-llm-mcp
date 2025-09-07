#!/usr/bin/env python3
"""
Schema enforcement hook for Local LLM MCP project.
Validates directory structure, file naming, size constraints, and template compliance.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


class SchemaValidator:
    MAX_LINES = {"implementation": 300, "test": 500, "readme": 100, "function": 50, "class": 150}

    REQUIRED_FILES = ["*.py", "test_*.py", "README_*.md"]
    VALID_DOMAINS = ["api", "mcp", "core", "bridges", "schemas"]
    TEMPLATE_MARKERS = {
        "generation_date": re.compile(r"Generated from template on \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        "template_version": re.compile(r"Template version: \d+\.\d+\.\d+"),
    }

    def validate_structure(self, src_path: Path) -> list[str]:
        """Validate overall directory structure"""
        errors = []

        for domain_dir in src_path.iterdir():
            if not domain_dir.is_dir():
                continue

            if domain_dir.name not in self.VALID_DOMAINS:
                errors.append(f"Invalid domain: {domain_dir.name}")
                continue

            errors.extend(self._validate_domain(domain_dir))

        return errors

    def _validate_domain(self, domain_path: Path) -> list[str]:
        """Validate domain-level structure"""
        errors = []

        for category_dir in domain_path.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("__"):
                continue

            errors.extend(self._validate_category(domain_path.name, category_dir))

        return errors

    def _validate_category(self, domain: str, category_path: Path) -> list[str]:
        """Validate category-level structure"""
        errors = []

        for function_dir in category_path.iterdir():
            if not function_dir.is_dir() or function_dir.name.startswith("__"):
                continue

            errors.extend(self._validate_function(domain, category_path.name, function_dir))

        return errors

    def _validate_function(self, domain: str, category: str, function_path: Path) -> list[str]:
        """Validate function-level structure and files"""
        errors = []
        function_name = function_path.name

        # Check required files exist
        required_files = [
            f"{function_name}.py",
            f"test_{function_name}.py",
            f"README_{domain}_{category}_{function_name}.md",
        ]

        for req_file in required_files:
            if not (function_path / req_file).exists():
                errors.append(f"Missing required file: {function_path}/{req_file}")

        # Validate file sizes
        for py_file in function_path.glob("*.py"):
            if py_file.name.startswith("test_"):
                max_lines = self.MAX_LINES["test"]
            else:
                max_lines = self.MAX_LINES["implementation"]

            line_count = len(py_file.read_text().splitlines())
            if line_count > max_lines:
                errors.append(f"File too large: {py_file} ({line_count} > {max_lines} lines)")

        # Validate README size
        readme_file = function_path / f"README_{domain}_{category}_{function_name}.md"
        if readme_file.exists():
            line_count = len(readme_file.read_text().splitlines())
            if line_count > self.MAX_LINES["readme"]:
                errors.append(f"README too large: {readme_file} ({line_count} > {self.MAX_LINES['readme']} lines)")

        return errors

    def _validate_template_compliance(self, function_path: Path, domain: str, category: str) -> list[str]:
        """Validate that files were generated from templates"""
        errors = []
        function_name = function_path.name

        # Check implementation file for template markers
        impl_file = function_path / f"{function_name}.py"
        if impl_file.exists():
            content = impl_file.read_text()
            if not self.TEMPLATE_MARKERS["generation_date"].search(content):
                errors.append(f"Implementation file missing template generation marker: {impl_file}")
            if not self.TEMPLATE_MARKERS["template_version"].search(content):
                errors.append(f"Implementation file missing template version marker: {impl_file}")

        # Check test file for template markers
        test_file = function_path / f"test_{function_name}.py"
        if test_file.exists():
            content = test_file.read_text()
            if not self.TEMPLATE_MARKERS["generation_date"].search(content):
                errors.append(f"Test file missing template generation marker: {test_file}")

        # Check README for template markers
        readme_file = function_path / f"README_{domain}_{category}_{function_name}.md"
        if readme_file.exists():
            content = readme_file.read_text()
            if not self.TEMPLATE_MARKERS["generation_date"].search(content):
                errors.append(f"README file missing template generation marker: {readme_file}")

        return errors

    def validate_manual_edits(self, src_path: Path) -> list[str]:
        """Validate that manual edits don't violate schema"""
        errors = []

        for domain_dir in src_path.iterdir():
            if not domain_dir.is_dir() or domain_dir.name not in self.VALID_DOMAINS:
                continue

            for category_dir in domain_dir.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith("__"):
                    continue

                for function_dir in category_dir.iterdir():
                    if not function_dir.is_dir() or function_dir.name.startswith("__"):
                        continue

                    # Check if files have been manually edited without updating template markers
                    errors.extend(self._check_manual_modifications(function_dir, domain_dir.name, category_dir.name))

        return errors

    def _check_manual_modifications(self, function_path: Path, domain: str, category: str) -> list[str]:
        """Check for manual modifications that break template compliance"""
        errors = []
        function_name = function_path.name

        # Check if schema.json exists and matches implementation
        schema_file = function_path / f"schema_{function_name}.json"
        if schema_file.exists():
            try:
                schema = json.loads(schema_file.read_text())

                # Validate metadata matches directory structure
                if schema.get("function_metadata", {}).get("domain") != domain:
                    errors.append(f"Schema domain mismatch in {schema_file}")
                if schema.get("function_metadata", {}).get("category") != category:
                    errors.append(f"Schema category mismatch in {schema_file}")
                if schema.get("function_metadata", {}).get("name") != function_name:
                    errors.append(f"Schema function name mismatch in {schema_file}")

            except json.JSONDecodeError:
                errors.append(f"Invalid JSON in schema file: {schema_file}")

        return errors


def main():
    """Main hook entry point"""
    src_path = Path("src")

    if not src_path.exists():
        print("❌ src/ directory not found")
        return 1

    validator = SchemaValidator()

    # Run all validations
    errors = []
    errors.extend(validator.validate_structure(src_path))
    errors.extend(validator.validate_manual_edits(src_path))

    if errors:
        print("❌ Schema validation failed:")
        for error in errors:
            print(f"  • {error}")
        return 1

    print("✅ Schema validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
