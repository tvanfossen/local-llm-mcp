#!/usr/bin/env python3
"""
Initialize target repositories with local-llm-mcp schema and test configuration.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader


class TargetRepoInitializer:
    def __init__(self, templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        self.env = Environment(loader=FileSystemLoader(templates_dir), trim_blocks=True, lstrip_blocks=True)

    def initialize_repo(self, target_path: Path, config: Dict[str, Any]) -> None:
        """Initialize target repository with schema-compliant structure"""
        if not target_path.exists():
            raise ValueError(f"Target path does not exist: {target_path}")

        print(f"Initializing {config['project_name']} at {target_path}")

        # Create basic schema-compliant structure
        self._create_base_structure(target_path, config)

        # Deploy conftest.py
        self._deploy_conftest(target_path, config)

        # Create or update pyproject.toml
        self._update_pyproject_toml(target_path, config)

        # Create schema validator
        self._deploy_schema_validator(target_path)

        # Create initial README with schema info
        self._create_schema_readme(target_path, config)

        print(f"✅ Successfully initialized {config['project_name']}")

    def _create_base_structure(self, target_path: Path, config: Dict[str, Any]) -> None:
        """Create basic src/ directory structure"""
        domains = config.get("domains", ["core", "utils"])

        for domain in domains:
            domain_path = target_path / "src" / domain
            domain_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            (domain_path / "__init__.py").touch()

    def _deploy_conftest(self, target_path: Path, config: Dict[str, Any]) -> None:
        """Deploy conftest.py from template"""
        template = self.env.get_template("target_repo_conftest.py.j2")

        context = {
            **config,
            "generation_date": datetime.now().isoformat(),
        }

        content = template.render(context)
        conftest_file = target_path / "conftest.py"
        conftest_file.write_text(content)

        print("  Created conftest.py")

    def _update_pyproject_toml(self, target_path: Path, config: Dict[str, Any]) -> None:
        """Create or update pyproject.toml with pytest configuration"""
        pyproject_file = target_path / "pyproject.toml"

        if pyproject_file.exists():
            print("  pyproject.toml exists - manual update required for pytest config")
            return

        # Create minimal pyproject.toml
        content = f'''[project]
name = "{config["project_name"]}"
version = "{config.get("version", "0.1.0")}"
description = "{config.get("description", "Schema-compliant project")}"
requires-python = ">=3.10"
dependencies = {config.get("dependencies", [])}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["src"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--verbose",
    "--tb=short",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
]

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "E722", "E402"]
'''

        pyproject_file.write_text(content)
        print("  Created pyproject.toml")

    def _deploy_schema_validator(self, target_path: Path) -> None:
        """Copy schema validator to target repo"""
        scripts_dir = target_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        # Copy our schema validator
        source_validator = Path("scripts/schema_validator.py")
        target_validator = scripts_dir / "schema_validator.py"

        if source_validator.exists():
            target_validator.write_text(source_validator.read_text())
            target_validator.chmod(0o755)
            print("  Deployed schema validator")

    def _create_schema_readme(self, target_path: Path, config: Dict[str, Any]) -> None:
        """Create README with schema information"""
        readme_file = target_path / "SCHEMA_INFO.md"

        content = f"""# {config["project_name"]} - Schema Compliance

This project follows the local-llm-mcp schema for self-maintaining codebases.

## Structure

- `src/`: All functional code organized by domain/category/function
- Co-located tests: `test_*.py` files alongside implementation
- Schema validation: Run `python3 scripts/schema_validator.py`

## Running Tests

```bash
pytest                    # Run all tests
pytest src/domain/        # Run tests for specific domain
pytest -m unit           # Run only unit tests
```

## Adding New Functions

1. Create directory: `src/domain/category/function/`
2. Add required files:
   - `function.py` - Implementation
   - `test_function.py` - Tests
   - `README_domain_category_function.md` - Documentation

Generated by local-llm-mcp on {datetime.now().isoformat()}
"""

        readme_file.write_text(content)
        print("  Created SCHEMA_INFO.md")


def main():
    if len(sys.argv) != 3:
        print("Usage: init_target_repo.py <target_path> <config.json>")
        sys.exit(1)

    target_path = Path(sys.argv[1])
    config_file = Path(sys.argv[2])

    if not config_file.exists():
        print(f"Config file not found: {config_file}")
        sys.exit(1)

    with open(config_file) as f:
        config = json.load(f)

    initializer = TargetRepoInitializer()
    initializer.initialize_repo(target_path, config)


if __name__ == "__main__":
    main()
