#!/usr/bin/env python3
"""
Schema enforcement hook for Local LLM MCP project.
Validates directory structure, file naming, size constraints, and template compliance.
"""

import json
import re
import sys
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

        errors.extend(self._check_required_files(function_path, domain, category, function_name))
        errors.extend(self._validate_file_sizes(function_path, domain, category, function_name))

        return errors

    def _check_required_files(self, function_path: Path, domain: str, category: str, function_name: str) -> list[str]:
        """Check that all required files exist"""
        errors = []
        required_files = [
            f"{function_name}.py",
            f"test_{function_name}.py",
            f"README_{domain}_{category}_{function_name}.md",
        ]

        for req_file in required_files:
            if not (function_path / req_file).exists():
                errors.append(f"Missing required file: {function_path}/{req_file}")

        return errors

    def _validate_file_sizes(self, function_path: Path, domain: str, category: str, function_name: str) -> list[str]:
        """Validate that files don't exceed size limits"""
        errors = []

        # Validate Python file sizes
        for py_file in function_path.glob("*.py"):
            max_lines = self.MAX_LINES["test"] if py_file.name.startswith("test_") else self.MAX_LINES["implementation"]
            errors.extend(self._check_file_size(py_file, max_lines))

        # Validate README size
        readme_file = function_path / f"README_{domain}_{category}_{function_name}.md"
        if readme_file.exists():
            errors.extend(self._check_file_size(readme_file, self.MAX_LINES["readme"]))

        return errors

    def _check_file_size(self, file_path: Path, max_lines: int) -> list[str]:
        """Check if file exceeds line limit"""
        line_count = len(file_path.read_text().splitlines())
        if line_count > max_lines:
            return [f"File too large: {file_path} ({line_count} > {max_lines} lines)"]
        return []

    def _validate_template_compliance(self, function_path: Path, domain: str, category: str) -> list[str]:
        """Validate that files were generated from templates"""
        errors = []
        function_name = function_path.name

        file_checks = [
            (f"{function_name}.py", ["generation_date", "template_version"]),
            (f"test_{function_name}.py", ["generation_date"]),
            (f"README_{domain}_{category}_{function_name}.md", ["generation_date"]),
        ]

        for filename, markers in file_checks:
            errors.extend(self._check_file_template_markers(function_path / filename, markers))

        return errors

    def _check_file_template_markers(self, file_path: Path, required_markers: list[str]) -> list[str]:
        """Check if file has required template markers"""
        errors = []
        if not file_path.exists():
            return errors

        content = file_path.read_text()
        for marker in required_markers:
            if not self.TEMPLATE_MARKERS[marker].search(content):
                errors.append(f"{file_path} missing template {marker} marker")

        return errors

    def validate_manual_edits(self, src_path: Path) -> list[str]:
        """Validate that manual edits don't violate schema"""
        errors = []

        for domain_dir in self._get_valid_domains(src_path):
            for category_dir in self._get_valid_categories(domain_dir):
                for function_dir in self._get_valid_functions(category_dir):
                    errors.extend(self._check_manual_modifications(function_dir, domain_dir.name, category_dir.name))

        return errors

    def _get_valid_domains(self, src_path: Path):
        """Get valid domain directories"""
        for domain_dir in src_path.iterdir():
            if domain_dir.is_dir() and domain_dir.name in self.VALID_DOMAINS:
                yield domain_dir

    def _get_valid_categories(self, domain_dir: Path):
        """Get valid category directories"""
        for category_dir in domain_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith("__"):
                yield category_dir

    def _get_valid_functions(self, category_dir: Path):
        """Get valid function directories"""
        for function_dir in category_dir.iterdir():
            if function_dir.is_dir() and not function_dir.name.startswith("__"):
                yield function_dir

    def _check_manual_modifications(self, function_path: Path, domain: str, category: str) -> list[str]:
        """Check for manual modifications that break template compliance"""
        errors = []
        function_name = function_path.name

        schema_file = function_path / f"schema_{function_name}.json"
        if schema_file.exists():
            errors.extend(self._validate_schema_file(schema_file, domain, category, function_name))

        return errors

    def _validate_schema_file(self, schema_file: Path, domain: str, category: str, function_name: str) -> list[str]:
        """Validate schema file content and metadata"""
        errors = []
        try:
            schema = json.loads(schema_file.read_text())
            metadata = schema.get("function_metadata", {})

            metadata_checks = [("domain", domain), ("category", category), ("name", function_name)]

            for field, expected_value in metadata_checks:
                if metadata.get(field) != expected_value:
                    errors.append(f"Schema {field} mismatch in {schema_file}")

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
