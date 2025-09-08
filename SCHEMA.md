# Local LLM MCP Project Schema Definition

## Core Principle: Self-Maintaining Bite-Sized Contexts

This schema enforces a structure where each functional unit is completely self-contained within its own directory, optimized for small/local LLM consumption and self-maintenance.

## Hard Schema Rules

### 1. Functional Unit Structure

Each functional unit MUST follow this exact structure:

```
src/
├── {domain}/
│   ├── {category}/
│   │   ├── {function}/
│   │   │   ├── {function}.py              # Main implementation
│   │   │   ├── test_{function}.py         # Co-located tests
│   │   │   ├── README_{function}.md       # Context documentation
│   │   │   └── schema_{function}.json     # Data contracts (if applicable)
│   │   └── __init__.py                    # Category exports
│   └── __init__.py                        # Domain exports
```

### 2. Directory Naming Convention

- **Domain**: Top-level functional area (`api`, `mcp`, `core`, `bridges`)
- **Category**: Logical grouping within domain (`tools`, `handlers`, `auth`)
- **Function**: Specific capability (`commit`, `status`, `validate`)

### 3. File Naming Standards

#### Implementation Files
- **Primary**: `{function}.py` - Main implementation
- **Supporting**: `{function}_{type}.py` for complex functions (e.g., `commit_handlers.py`, `commit_validators.py`)

#### Test Files
- **Co-located**: `test_{function}.py` - Primary test file
- **Integration**: `test_{function}_integration.py` - Integration tests
- **Performance**: `test_{function}_performance.py` - Performance tests

#### Documentation Files
- **Context**: `README_{domain}_{category}_{function}.md` - Full context documentation
- **Schema**: `schema_{function}.json` - Data contracts and interfaces

### 4. Jinja2 Template System

All files in functional units MUST be generated from Jinja2 templates to ensure absolute consistency.

#### Template Directory Structure
```
templates/
├── function/
│   ├── implementation.py.j2
│   ├── test.py.j2
│   ├── readme.md.j2
│   └── schema.json.j2
├── helpers/
│   ├── imports.j2
│   ├── docstrings.j2
│   └── error_handling.j2
└── validators/
    ├── template_validator.py
    └── content_validator.py
```

#### README Template (`templates/function/readme.md.j2`)
```markdown
# {{ domain|title }} > {{ category|title }} > {{ function_name|title }}

## Purpose
{{ purpose }}

## Context Dependencies
- **Upstream**: {{ dependencies.upstream|join(', ') or 'None' }}
- **Downstream**: {{ dependencies.downstream|join(', ') or 'None' }}
- **External**: {{ dependencies.external|join(', ') or 'None' }}

## Interface Contract
- **Input**: {{ interface.input_type }} - {{ interface.input_description }}
- **Output**: {{ interface.output_type }} - {{ interface.output_description }}
- **Errors**: {{ interface.errors|join(', ') }}

## Implementation Notes
{% for note in implementation_notes -%}
- {{ note }}
{% endfor %}

## Test Strategy
{% for strategy in test_strategies -%}
- {{ strategy }}
{% endfor %}

## Self-Maintenance Notes
{% for note in maintenance_notes -%}
- {{ note }}
{% endfor %}

---
*Generated from template on {{ generation_date }}*
*Template version: {{ template_version }}*
```

#### Implementation Template (`templates/function/implementation.py.j2`)
```python
"""
{{ docstring }}

Generated from template on {{ generation_date }}
Template version: {{ template_version }}
"""

{% include 'helpers/imports.j2' %}

{% if logging_enabled -%}
logger = logging.getLogger(__name__)
{% endif %}

{% if class_based -%}
class {{ class_name }}:
    """{{ class_docstring }}"""

    def __init__(self{% if init_params %}, {{ init_params }}{% endif %}):
        {% for param in init_assignments -%}
        self.{{ param.name }} = {{ param.value }}
        {% endfor %}

    {% for method in methods -%}
    def {{ method.name }}(self{% if method.params %}, {{ method.params }}{% endif %}):
        """{{ method.docstring }}"""
        {% if method.validation -%}
        # Input validation
        {% for validation in method.validation -%}
        {{ validation }}
        {% endfor %}
        {% endif %}

        {% if method.logging -%}
        logger.{{ method.log_level }}("{{ method.log_message }}")
        {% endif %}

        # Implementation
        {% for line in method.implementation -%}
        {{ line }}
        {% endfor %}

        {% if method.error_handling -%}
        {% include 'helpers/error_handling.j2' %}
        {% endif %}

    {% endfor %}
{% else -%}
{% for function in functions -%}
def {{ function.name }}({{ function.params }}):
    """{{ function.docstring }}"""
    {% if function.validation -%}
    # Input validation
    {% for validation in function.validation -%}
    {{ validation }}
    {% endfor %}
    {% endif %}

    {% if function.logging -%}
    logger.{{ function.log_level }}("{{ function.log_message }}")
    {% endif %}

    # Implementation
    {% for line in function.implementation -%}
    {{ line }}
    {% endfor %}

    {% if function.error_handling -%}
    {% include 'helpers/error_handling.j2' %}
    {% endif %}

{% endfor %}
{% endif %}
```

#### Test Template (`templates/function/test.py.j2`)
```python
"""
Tests for {{ domain }}.{{ category }}.{{ function_name }}

Generated from template on {{ generation_date }}
Template version: {{ template_version }}
"""

import pytest
{% for import in test_imports -%}
{{ import }}
{% endfor %}

from {{ module_path }} import {{ imports|join(', ') }}

{% if fixtures -%}
# Fixtures
{% for fixture in fixtures -%}
@pytest.fixture
def {{ fixture.name }}():
    """{{ fixture.docstring }}"""
    {{ fixture.implementation }}

{% endfor %}
{% endif %}

class Test{{ function_name|title }}:
    """Test suite for {{ function_name }}"""

    {% for test in unit_tests -%}
    def test_{{ test.name }}(self{% if test.fixtures %}, {{ test.fixtures|join(', ') }}{% endif %}):
        """{{ test.description }}"""
        # Arrange
        {% for line in test.arrange -%}
        {{ line }}
        {% endfor %}

        # Act
        {% for line in test.act -%}
        {{ line }}
        {% endfor %}

        # Assert
        {% for assertion in test.assertions -%}
        {{ assertion }}
        {% endfor %}

    {% endfor %}

    {% if error_tests -%}
    # Error condition tests
    {% for test in error_tests -%}
    def test_{{ test.name }}_raises_{{ test.exception|lower }}(self):
        """{{ test.description }}"""
        with pytest.raises({{ test.exception }}):
            {{ test.trigger }}

    {% endfor %}
    {% endif %}

{% if integration_tests -%}
class Test{{ function_name|title }}Integration:
    """Integration tests for {{ function_name }}"""

    {% for test in integration_tests -%}
    def test_{{ test.name }}(self):
        """{{ test.description }}"""
        {{ test.implementation }}

    {% endfor %}
{% endif %}
```

#### Schema Template (`templates/function/schema.json.j2`)
```json
{
  "function_metadata": {
    "name": "{{ function_name }}",
    "domain": "{{ domain }}",
    "category": "{{ category }}",
    "version": "{{ version }}",
    "generated": "{{ generation_date }}",
    "template_version": "{{ template_version }}"
  },
  "interface": {
    "input": {
      "type": "{{ interface.input_type }}",
      "required": {{ interface.required|tojson }},
      "properties": {{ interface.input_properties|tojson }}
    },
    "output": {
      "type": "{{ interface.output_type }}",
      "properties": {{ interface.output_properties|tojson }}
    },
    "errors": {{ interface.errors|tojson }}
  },
  "dependencies": {
    "internal": {{ dependencies.internal|tojson }},
    "external": {{ dependencies.external|tojson }},
    "optional": {{ dependencies.optional|tojson }}
  },
  "constraints": {
    "max_lines": {{ constraints.max_lines }},
    "max_complexity": {{ constraints.max_complexity }},
    "required_tests": {{ constraints.required_tests }}
  },
  "validation_rules": {{ validation_rules|tojson }}
}
```

### 5. Size Constraints (Enforced by Hook)

- **Implementation files**: Maximum 200 lines
- **Test files**: Maximum 300 lines
- **README files**: Maximum 100 lines
- **Functions**: Maximum 50 lines each
- **Classes**: Maximum 150 lines each

If limits exceeded, function MUST be split into sub-functions.

## Proposed Directory Structure

```
src/
├── api/
│   ├── http/
│   │   ├── server/
│   │   │   ├── server.py
│   │   │   ├── test_server.py
│   │   │   └── README_api_http_server.md
│   │   ├── routes/
│   │   │   ├── routes.py
│   │   │   ├── test_routes.py
│   │   │   └── README_api_http_routes.md
│   │   └── endpoints/
│   │       ├── endpoints.py
│   │       ├── test_endpoints.py
│   │       └── README_api_http_endpoints.md
│   ├── websocket/
│   │   └── handler/
│   │       ├── handler.py
│   │       ├── test_handler.py
│   │       └── README_api_websocket_handler.md
│   └── middleware/
│       ├── auth/
│       │   ├── auth.py
│       │   ├── test_auth.py
│       │   └── README_api_middleware_auth.md
│       └── validation/
│           ├── validation.py
│           ├── test_validation.py
│           └── README_api_middleware_validation.md
├── mcp/
│   ├── tools/
│   │   ├── git/
│   │   │   ├── commit/
│   │   │   │   ├── commit.py
│   │   │   │   ├── test_commit.py
│   │   │   │   ├── README_mcp_tools_git_commit.md
│   │   │   │   └── schema_commit.json
│   │   │   ├── status/
│   │   │   │   ├── status.py
│   │   │   │   ├── test_status.py
│   │   │   │   └── README_mcp_tools_git_status.md
│   │   │   └── diff/
│   │   │       ├── diff.py
│   │   │       ├── test_diff.py
│   │   │       └── README_mcp_tools_git_diff.md
│   │   ├── file/
│   │   │   ├── create/
│   │   │   ├── update/
│   │   │   ├── delete/
│   │   │   └── read/
│   │   └── agent/
│   │       ├── create/
│   │       ├── update/
│   │       ├── list/
│   │       └── chat/
│   ├── validation/
│   │   ├── request/
│   │   ├── response/
│   │   └── schema/
│   └── auth/
│       ├── token/
│       ├── session/
│       └── permissions/
├── core/
│   ├── agents/
│   │   ├── registry/
│   │   ├── lifecycle/
│   │   └── communication/
│   ├── llm/
│   │   ├── manager/
│   │   ├── providers/
│   │   └── deployment/
│   ├── security/
│   │   ├── keys/
│   │   ├── encryption/
│   │   └── access/
│   └── config/
│       ├── loader/
│       ├── validation/
│       └── environment/
├── bridges/
│   └── claude/
│       ├── integration/
│       ├── communication/
│       └── formatting/
└── schemas/
    ├── agents/
    ├── requests/
    ├── responses/
    └── configuration/
```

### Template Generation System

#### Function Generator (`scripts/generate_function.py`)
```python
#!/usr/bin/env python3
"""
Generate new functional units from Jinja2 templates.
Ensures all functions follow exact schema compliance.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, Template

class FunctionGenerator:
    def __init__(self, templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def generate_function(self, spec_file: Path) -> None:
        """Generate complete function unit from specification"""
        with open(spec_file) as f:
            spec = json.load(f)

        # Validate specification
        self._validate_spec(spec)

        # Create function directory
        func_dir = Path("src") / spec["domain"] / spec["category"] / spec["function_name"]
        func_dir.mkdir(parents=True, exist_ok=True)

        # Generate all files from templates
        self._generate_implementation(func_dir, spec)
        self._generate_test(func_dir, spec)
        self._generate_readme(func_dir, spec)
        self._generate_schema(func_dir, spec)

        print(f"✅ Generated function: {func_dir}")

    def _validate_spec(self, spec: Dict[str, Any]) -> None:
        """Validate function specification"""
        required = ["domain", "category", "function_name", "purpose", "interface"]
        for field in required:
            if field not in spec:
                raise ValueError(f"Missing required field: {field}")

    def _generate_implementation(self, func_dir: Path, spec: Dict[str, Any]) -> None:
        template = self.env.get_template("function/implementation.py.j2")

        context = {
            **spec,
            "generation_date": datetime.now().isoformat(),
            "template_version": "1.0.0",
            "module_path": f"src.{spec['domain']}.{spec['category']}.{spec['function_name']}"
        }

        content = template.render(context)
        output_file = func_dir / f"{spec['function_name']}.py"
        output_file.write_text(content)

    def _generate_test(self, func_dir: Path, spec: Dict[str, Any]) -> None:
        template = self.env.get_template("function/test.py.j2")

        context = {
            **spec,
            "generation_date": datetime.now().isoformat(),
            "template_version": "1.0.0",
            "module_path": f"src.{spec['domain']}.{spec['category']}.{spec['function_name']}"
        }

        content = template.render(context)
        output_file = func_dir / f"test_{spec['function_name']}.py"
        output_file.write_text(content)

    def _generate_readme(self, func_dir: Path, spec: Dict[str, Any]) -> None:
        template = self.env.get_template("function/readme.md.j2")

        context = {
            **spec,
            "generation_date": datetime.now().isoformat(),
            "template_version": "1.0.0"
        }

        content = template.render(context)
        output_file = func_dir / f"README_{spec['domain']}_{spec['category']}_{spec['function_name']}.md"
        output_file.write_text(content)

    def _generate_schema(self, func_dir: Path, spec: Dict[str, Any]) -> None:
        template = self.env.get_template("function/schema.json.j2")

        context = {
            **spec,
            "generation_date": datetime.now().isoformat(),
            "template_version": "1.0.0"
        }

        content = template.render(context)
        output_file = func_dir / f"schema_{spec['function_name']}.json"
        output_file.write_text(content)

def main():
    if len(sys.argv) != 2:
        print("Usage: generate_function.py <spec_file.json>")
        sys.exit(1)

    spec_file = Path(sys.argv[1])
    if not spec_file.exists():
        print(f"Specification file not found: {spec_file}")
        sys.exit(1)

    generator = FunctionGenerator()
    generator.generate_function(spec_file)

if __name__ == "__main__":
    main()
```

#### Example Function Specification (`specs/mcp_tools_git_commit.json`)
```json
{
  "domain": "mcp",
  "category": "tools",
  "function_name": "commit",
  "purpose": "Create git commits with proper validation and error handling",
  "class_based": false,
  "logging_enabled": true,
  "dependencies": {
    "upstream": ["git.status", "git.diff"],
    "downstream": ["git.push"],
    "external": ["subprocess", "pathlib"],
    "internal": ["mcp.validation.request"],
    "optional": []
  },
  "interface": {
    "input_type": "dict",
    "input_description": "Commit parameters including message and files",
    "input_properties": {
      "message": {"type": "string", "required": true},
      "files": {"type": "array", "items": {"type": "string"}, "required": false}
    },
    "output_type": "dict",
    "output_description": "Commit result with status and commit hash",
    "output_properties": {
      "success": {"type": "boolean"},
      "commit_hash": {"type": "string"},
      "message": {"type": "string"}
    },
    "errors": ["InvalidCommitMessage", "GitRepositoryError", "NoChangesToCommit"]
  },
  "functions": [
    {
      "name": "create_commit",
      "params": "message: str, files: list[str] = None",
      "docstring": "Create a git commit with the specified message and files",
      "validation": [
        "if not message or not message.strip():",
        "    raise ValueError('Commit message cannot be empty')"
      ],
      "logging": true,
      "log_level": "info",
      "log_message": "Creating commit with message: {message}",
      "implementation": [
        "try:",
        "    # Add files to staging area",
        "    if files:",
        "        subprocess.run(['git', 'add'] + files, check=True)",
        "    else:",
        "        subprocess.run(['git', 'add', '.'], check=True)",
        "    ",
        "    # Create commit",
        "    result = subprocess.run(",
        "        ['git', 'commit', '-m', message],",
        "        capture_output=True, text=True, check=True",
        "    )",
        "    ",
        "    # Get commit hash",
        "    hash_result = subprocess.run(",
        "        ['git', 'rev-parse', 'HEAD'],",
        "        capture_output=True, text=True, check=True",
        "    )",
        "    ",
        "    return {",
        "        'success': True,",
        "        'commit_hash': hash_result.stdout.strip(),",
        "        'message': f'Successfully created commit: {message}'",
        "    }",
        "except subprocess.CalledProcessError as e:",
        "    logger.error(f'Git commit failed: {e.stderr}')",
        "    return {",
        "        'success': False,",
        "        'commit_hash': None,",
        "        'message': f'Commit failed: {e.stderr.strip()}'",
        "    }"
      ],
      "error_handling": true
    }
  ],
  "unit_tests": [
    {
      "name": "successful_commit",
      "description": "Test successful commit creation",
      "fixtures": ["mock_git_repo"],
      "arrange": [
        "message = 'Test commit message'",
        "expected_hash = 'abc123def456'"  # pragma: allowlist secret
      ],
      "act": [
        "result = create_commit(message)"
      ],
      "assertions": [
        "assert result['success'] is True",
        "assert 'commit_hash' in result",
        "assert message in result['message']"
      ]
    },
    {
      "name": "empty_message",
      "description": "Test commit with empty message fails",
      "arrange": [
        "message = ''"
      ],
      "act": [],
      "assertions": []
    }
  ],
  "error_tests": [
    {
      "name": "empty_message",
      "description": "Empty commit message should raise ValueError",
      "exception": "ValueError",
      "trigger": "create_commit('')"
    }
  ],
  "fixtures": [
    {
      "name": "mock_git_repo",
      "docstring": "Mock git repository for testing",
      "implementation": "return MockGitRepo()"
    }
  ],
  "test_imports": [
    "from unittest.mock import patch, MagicMock"
  ],
  "implementation_notes": [
    "Uses subprocess to interact with git command line",
    "Validates commit message is not empty",
    "Handles both specific files and all changes",
    "Returns structured response for consistent error handling"
  ],
  "test_strategies": [
    "Mock subprocess calls to avoid actual git operations",
    "Test both successful and failed commit scenarios",
    "Verify proper error handling and logging",
    "Test edge cases like empty messages and no changes"
  ],
  "maintenance_notes": [
    "When modifying git commands, ensure subprocess calls remain secure",
    "Update tests when changing return value structure",
    "Consider git version compatibility when adding new features",
    "Logging level can be adjusted based on deployment environment"
  ],
  "constraints": {
    "max_lines": 200,
    "max_complexity": 10,
    "required_tests": 3
  },
  "validation_rules": [
    "commit_message_not_empty",
    "return_value_structure_valid",
    "error_handling_comprehensive"
  ]
}
```

## Schema Enforcement Hook

### Enhanced Pre-commit Hook with Template Validation

```python
#!/usr/bin/env python3
"""
Schema enforcement hook for Local LLM MCP project.
Validates directory structure, file naming, size constraints, and template compliance.
"""

import os
import sys
from pathlib import Path
import json
import re
from datetime import datetime

class SchemaValidator:
    MAX_LINES = {
        'implementation': 200,
        'test': 300,
        'readme': 100,
        'function': 50,
        'class': 150
    }

    REQUIRED_FILES = ['*.py', 'test_*.py', 'README_*.md']
    VALID_DOMAINS = ['api', 'mcp', 'core', 'bridges', 'schemas']
    TEMPLATE_MARKERS = {
        'generation_date': re.compile(r'Generated from template on \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'),
        'template_version': re.compile(r'Template version: \d+\.\d+\.\d+')
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
            if not category_dir.is_dir() or category_dir.name.startswith('__'):
                continue

            errors.extend(self._validate_category(domain_path.name, category_dir))

        return errors

    def _validate_category(self, domain: str, category_path: Path) -> list[str]:
        """Validate category-level structure"""
        errors = []

        for function_dir in category_path.iterdir():
            if not function_dir.is_dir() or function_dir.name.startswith('__'):
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
            f"README_{domain}_{category}_{function_name}.md"
        ]

        for req_file in required_files:
            if not (function_path / req_file).exists():
                errors.append(f"Missing required file: {function_path}/{req_file}")

        # Validate file sizes
        for py_file in function_path.glob("*.py"):
            if py_file.name.startswith('test_'):
                max_lines = self.MAX_LINES['test']
            else:
                max_lines = self.MAX_LINES['implementation']

            line_count = len(py_file.read_text().splitlines())
            if line_count > max_lines:
                errors.append(f"File too large: {py_file} ({line_count} > {max_lines} lines)")

        # Validate README size
        readme_file = function_path / f"README_{domain}_{category}_{function_name}.md"
        if readme_file.exists():
            line_count = len(readme_file.read_text().splitlines())
            if line_count > self.MAX_LINES['readme']:
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
            if not self.TEMPLATE_MARKERS['generation_date'].search(content):
                errors.append(f"Implementation file missing template generation marker: {impl_file}")
            if not self.TEMPLATE_MARKERS['template_version'].search(content):
                errors.append(f"Implementation file missing template version marker: {impl_file}")

        # Check test file for template markers
        test_file = function_path / f"test_{function_name}.py"
        if test_file.exists():
            content = test_file.read_text()
            if not self.TEMPLATE_MARKERS['generation_date'].search(content):
                errors.append(f"Test file missing template generation marker: {test_file}")

        # Check README for template markers
        readme_file = function_path / f"README_{domain}_{category}_{function_name}.md"
        if readme_file.exists():
            content = readme_file.read_text()
            if not self.TEMPLATE_MARKERS['generation_date'].search(content):
                errors.append(f"README file missing template generation marker: {readme_file}")

        return errors

    def validate_manual_edits(self, src_path: Path) -> list[str]:
        """Validate that manual edits don't violate schema"""
        errors = []

        for domain_dir in src_path.iterdir():
            if not domain_dir.is_dir() or domain_dir.name not in self.VALID_DOMAINS:
                continue

            for category_dir in domain_dir.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith('__'):
                    continue

                for function_dir in category_dir.iterdir():
                    if not function_dir.is_dir() or function_dir.name.startswith('__'):
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
                if schema.get('function_metadata', {}).get('domain') != domain:
                    errors.append(f"Schema domain mismatch in {schema_file}")
                if schema.get('function_metadata', {}).get('category') != category:
                    errors.append(f"Schema category mismatch in {schema_file}")
                if schema.get('function_metadata', {}).get('name') != function_name:
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
```

## Pytest Configuration for Co-located Tests

### Custom Test Discovery

```python
# conftest.py
import pytest
from pathlib import Path

def pytest_collect_file(parent, path):
    """Custom test collection for co-located tests"""
    if path.suffix == ".py" and path.basename.startswith("test_"):
        return pytest.Module.from_parent(parent, fspath=path)

def pytest_configure(config):
    """Configure pytest for co-located test structure"""
    # Add src/ to Python path
    src_path = Path(__file__).parent / "src"
    if src_path.exists():
        import sys
        sys.path.insert(0, str(src_path))
```

### Test Discovery Script

```bash
#!/bin/bash
# discover_tests.sh - Find all co-located test files

find src/ -name "test_*.py" -type f | while read test_file; do
    echo "Found test: $test_file"
done

# Run pytest with custom test discovery
pytest $(find src/ -name "test_*.py" -type f)
```

## Benefits of Template-Enforced Schema

### 1. Self-Maintenance Optimized
- Each functional unit is completely self-contained
- Local LLMs can understand complete context from single directory
- Documentation co-located with implementation
- **Jinja2 templates ensure 100% consistency across all functions**

### 2. Small Context Windows
- Maximum 200 lines per implementation file
- Complete function context fits in small LLM context windows
- Clear dependencies documented in README
- **Template-generated specifications provide perfect context**

### 3. Absolute Consistency
- **All files follow identical structure and patterns**
- **Error handling, logging, and validation are standardized**
- **Documentation format never varies between functions**
- **Pre-commit hook validates template compliance**

### 4. Local LLM Friendly
- **Specifications in JSON format are easily consumed by small models**
- **Template system allows LLMs to generate new functions without context confusion**
- **Self-documenting code with mandatory context documentation**
- **Predictable patterns reduce cognitive load for model comprehension**

### 5. Automated Enforcement
- Pre-commit hook validates structure and template compliance
- Size constraints prevent bloat
- Required documentation ensures context
- **Template markers prevent manual drift from schema**

### 6. Discoverability
- Predictable naming conventions
- Clear hierarchical organization
- Test files co-located with implementation
- **Schema.json files provide machine-readable interfaces**

### 7. Scalability
- Easy to add new functions without restructuring
- Clear separation of concerns
- Modular architecture supports growth
- **Template system scales without human oversight**

## Migration Strategy

The schema can be enforced incrementally:

1. **Phase 1**: Implement hook with warnings only
2. **Phase 2**: Migrate existing large files to schema-compliant structure
3. **Phase 3**: Enable hook enforcement
4. **Phase 4**: Add required documentation
5. **Phase 5**: Full schema compliance

This ensures the codebase can maintain itself through small, focused changes that any local LLM can understand and implement safely.
