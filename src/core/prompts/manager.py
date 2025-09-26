"""Prompt Management System for External Prompt Storage

This module provides centralized prompt management for the local-llm-mcp system,
allowing prompts to be stored in external files for maintainability and rapid iteration.
"""

import json
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Configuration for prompt system"""
    global_variables: Dict[str, Any]
    category_variables: Dict[str, List[str]]

    @classmethod
    def from_yaml(cls, config_path: Path) -> 'PromptConfig':
        """Load configuration from YAML file"""
        if not config_path.exists():
            return cls(global_variables={}, category_variables={})

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        return cls(
            global_variables=data.get('global_variables', {}),
            category_variables=data.get('categories', {})
        )


class PromptManager:
    """Central prompt management system"""

    def __init__(self, prompts_dir: Optional[Path] = None):
        if prompts_dir is None:
            # Default to prompts directory in project root
            project_root = Path(__file__).parent.parent.parent.parent
            prompts_dir = project_root / "prompts"

        self.prompts_dir = Path(prompts_dir)
        self.cache = {}  # filepath -> content cache
        self.variables = {}  # Global variables available to all prompts

        # Load configuration
        config_path = self.prompts_dir / "config.yaml"
        self.config = PromptConfig.from_yaml(config_path)
        self.variables.update(self.config.global_variables)

        logger.info(f"PromptManager initialized with directory: {self.prompts_dir}")

    def load_prompt(self, category: str, name: str, format: str = "json") -> str:
        """Load a prompt template from JSON file with schema validation

        Args:
            category: Directory category (e.g., 'agents', 'tools', 'system')
            name: Prompt name (e.g., 'structured_code_generation', 'tool_calling_json')
            format: File extension (only 'json' supported for strict schema enforcement)

        Returns:
            Prompt template string extracted from JSON schema
        """
        if format != "json":
            logger.error(f"Only JSON format supported for strict schema compliance, got: {format}")
            return f"[UNSUPPORTED FORMAT: {format} - JSON only]"

        prompt_path = self.prompts_dir / category / f"{name}.json"

        # Check cache first
        cache_key = str(prompt_path)
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not prompt_path.exists():
            logger.warning(f"JSON prompt file not found: {prompt_path}")
            return f"[JSON PROMPT NOT FOUND: {category}/{name}.json]"

        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract template from JSON schema
            if not isinstance(data, dict):
                raise ValueError("JSON prompt must be an object")

            template = data.get("template")
            if not template:
                raise ValueError("JSON prompt must contain 'template' field")

            # Cache the extracted template
            self.cache[cache_key] = template
            logger.debug(f"Loaded JSON prompt template: {prompt_path}")
            return template

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in prompt {prompt_path}: {e}")
            return f"[JSON PARSE ERROR: {e}]"
        except Exception as e:
            logger.error(f"Failed to load JSON prompt {prompt_path}: {e}")
            return f"[PROMPT LOAD ERROR: {e}]"

    def format_prompt(self, category: str, name: str, format: str = "json", **kwargs) -> str:
        """Load and format prompt with variables from JSON schema

        Args:
            category: Directory category
            name: Prompt name
            format: File extension (only 'json' supported)
            **kwargs: Variables to substitute in the prompt template

        Returns:
            Formatted prompt with variables substituted

        Raises:
            ValueError: If template substitution fails or prompt is too long
            KeyError: If required template variables are missing
        """
        prompt = self.load_prompt(category, name, format)

        # Check character limit BEFORE processing (2000 chars for Qwen2.5-7B)
        MAX_PROMPT_CHARS = 2000
        if len(prompt) > MAX_PROMPT_CHARS:
            raise ValueError(f"Prompt {category}/{name} exceeds {MAX_PROMPT_CHARS} character limit: {len(prompt)} chars")

        # Merge variables: global < category < runtime
        all_variables = {}
        all_variables.update(self.variables)

        # Add category-specific variables if configured
        category_vars = self.config.category_variables.get(category, {})
        if isinstance(category_vars, dict):
            all_variables.update(category_vars.get('variables', {}))

        # Load additional variables from JSON file itself (like metadata_schema)
        prompt_path = self.prompts_dir / category / f"{name}.json"
        if prompt_path.exists():
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Add metadata_schema if it exists and is needed by template
                if 'metadata_schema' in data and '{metadata_schema}' in prompt:
                    all_variables['metadata_schema'] = json.dumps(data['metadata_schema'], indent=2)

            except Exception as e:
                logger.warning(f"Could not load additional variables from {prompt_path}: {e}")

        # Runtime variables override everything
        all_variables.update(kwargs)

        # Format template with strict error handling
        try:
            formatted_prompt = prompt.format(**all_variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise KeyError(f"Missing required variable '{missing_var}' in prompt {category}/{name}")
        except Exception as e:
            raise ValueError(f"Template formatting failed for {category}/{name}: {str(e)}")

        # Validate that all placeholders were actually substituted
        import re
        remaining_placeholders = re.findall(r'\{(\w+)\}', formatted_prompt)
        if remaining_placeholders:
            raise ValueError(f"Unsubstituted placeholders in {category}/{name}: {remaining_placeholders}")

        # Check final prompt length
        if len(formatted_prompt) > MAX_PROMPT_CHARS:
            raise ValueError(f"Formatted prompt {category}/{name} exceeds {MAX_PROMPT_CHARS} character limit: {len(formatted_prompt)} chars")

        return formatted_prompt

    def register_variable(self, key: str, value: Any):
        """Register a global variable for prompts"""
        self.variables[key] = value
        logger.debug(f"Registered global variable: {key}")

    def validate_prompt(self, category: str, name: str, format: str = "json") -> List[str]:
        """Check for missing variables in prompt

        Returns:
            List of missing variable names
        """
        prompt = self.load_prompt(category, name, format)

        # Find all variables in the prompt (simple {variable} format)
        import re
        variables_in_prompt = set(re.findall(r'\{(\w+)\}', prompt))

        # Check which variables are not available
        available_variables = set(self.variables.keys())

        # Add category-specific variables
        category_vars = self.config.category_variables.get(category, {})
        if isinstance(category_vars, dict):
            available_variables.update(category_vars.get('variables', {}))

        missing_variables = variables_in_prompt - available_variables
        return list(missing_variables)

    def clear_cache(self):
        """Clear the prompt cache (useful for development)"""
        self.cache.clear()
        logger.info("Prompt cache cleared")

    def reload_config(self):
        """Reload configuration from file"""
        config_path = self.prompts_dir / "config.yaml"
        self.config = PromptConfig.from_yaml(config_path)
        self.variables.clear()
        self.variables.update(self.config.global_variables)
        logger.info("Prompt configuration reloaded")


class PromptValidator:
    """Validation system for prompts"""

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    def validate_all_prompts(self) -> Dict[str, List[str]]:
        """Validate all prompts for missing variables, syntax errors

        Returns:
            Dict mapping prompt paths to list of issues
        """
        issues = {}

        if not self.prompt_manager.prompts_dir.exists():
            return {"global": ["Prompts directory does not exist"]}

        # Walk through all JSON prompt files
        for prompt_file in self.prompt_manager.prompts_dir.rglob("*.json"):
            relative_path = prompt_file.relative_to(self.prompt_manager.prompts_dir)
            category = str(relative_path.parent)
            name = prompt_file.stem

            prompt_issues = self.prompt_manager.validate_prompt(category, name, "json")
            if prompt_issues:
                issues[str(relative_path)] = prompt_issues

        return issues

    def check_prompt_variables(self, prompt_path: Path) -> List[str]:
        """Check if all variables in prompt are documented

        Returns:
            List of undocumented variables
        """
        # This would check against metadata.yaml files
        # Implementation depends on metadata structure
        return []

    def validate_json_examples(self) -> List[str]:
        """Validate all JSON examples against schema

        Returns:
            List of validation errors
        """
        errors = []

        # Find all JSON files in examples
        json_files = list(self.prompt_manager.prompts_dir.rglob("*.json"))

        for json_file in json_files:
            try:
                import json
                with open(json_file, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{json_file}: {e}")

        return errors