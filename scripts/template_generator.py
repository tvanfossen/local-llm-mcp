#!/usr/bin/env python3
"""
Template Generator - Create new functions using Jinja2 templates

Responsibilities:
- Generate function directories with proper schema structure
- Use Jinja2 templates for consistent code generation
- Support domain/category/function structure
- Validate template parameters
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class TemplateGenerator:
    def __init__(self, templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def generate_function(self, function_path: str, **kwargs: Any) -> None:
        """Generate a new function using templates

        Args:
            function_path: Path like 'src/domain/category/function'
            **kwargs: Additional template variables
        """
        # Parse path components
        path_parts = Path(function_path).parts
        if len(path_parts) < 4 or path_parts[0] != "src":
            raise ValueError("Function path must be in format: src/domain/category/function")

        domain = path_parts[1]
        category = path_parts[2]
        function_name = path_parts[3]

        # Create target directory
        target_dir = Path(function_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"📝 Generating function: {function_name}")
        print(f"   Domain: {domain}")
        print(f"   Category: {category}")
        print(f"   Path: {target_dir}")

        # Prepare template context
        context = {
            "function_name": function_name,
            "domain": domain,
            "category": category,
            "function_path": function_path,
            "generation_date": datetime.now().isoformat(),
            **kwargs,
        }

        # Generate files from templates
        templates = [
            ("function/function.py.j2", f"{function_name}.py"),
            ("function/test_function.py.j2", f"test_{function_name}.py"),
            ("function/README_function.md.j2", f"README_{domain}_{category}_{function_name}.md"),
            ("function/schema_function.json.j2", f"schema_{function_name}.json"),
        ]

        for template_name, output_filename in templates:
            self._generate_file(template_name, target_dir / output_filename, context)

    def _generate_file(self, template_name: str, output_path: Path, context: dict) -> None:
        """Generate a single file from template"""
        try:
            template = self.env.get_template(template_name)
            content = template.render(context)

            if not output_path.exists():
                output_path.write_text(content)
                print(f"   ✅ Created: {output_path}")
            else:
                print(f"   ⚠️  Exists: {output_path}")

        except Exception as e:
            print(f"   ❌ Error generating {output_path}: {e}")


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: template_generator.py <function_path> [key=value ...]")
        print("Example: template_generator.py src/core/utils/fibonacci")
        sys.exit(1)

    function_path = sys.argv[1]

    # Parse additional template variables from command line
    template_vars = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            template_vars[key] = value

    generator = TemplateGenerator()
    generator.generate_function(function_path, **template_vars)


if __name__ == "__main__":
    main()
