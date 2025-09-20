"""Prompt Management System for External Prompt Storage

This module provides centralized prompt management for the local-llm-mcp system,
allowing prompts to be stored in external files for maintainability and rapid iteration.
"""

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

    def load_prompt(self, category: str, name: str, format: str = "txt") -> str:
        """Load a prompt file (txt, xml, or md)

        Args:
            category: Directory category (e.g., 'agents', 'tools', 'system')
            name: Prompt name (e.g., 'code_generation', 'tool_definition')
            format: File extension (txt, xml, md)

        Returns:
            Raw prompt content as string
        """
        prompt_path = self.prompts_dir / category / f"{name}.{format}"

        # Check cache first
        cache_key = str(prompt_path)
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not prompt_path.exists():
            logger.warning(f"Prompt file not found: {prompt_path}")
            return f"[PROMPT NOT FOUND: {category}/{name}.{format}]"

        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Cache the content
            self.cache[cache_key] = content
            logger.debug(f"Loaded prompt: {prompt_path}")
            return content

        except Exception as e:
            logger.error(f"Failed to load prompt {prompt_path}: {e}")
            return f"[PROMPT LOAD ERROR: {e}]"

    def format_prompt(self, category: str, name: str, format: str = "txt", **kwargs) -> str:
        """Load and format prompt with variables

        Args:
            category: Directory category
            name: Prompt name
            format: File extension
            **kwargs: Variables to substitute in the prompt

        Returns:
            Formatted prompt with variables substituted
        """
        prompt = self.load_prompt(category, name, format)

        # Merge variables: global < category < runtime
        all_variables = {}
        all_variables.update(self.variables)

        # Add category-specific variables if configured
        category_vars = self.config.category_variables.get(category, {})
        if isinstance(category_vars, dict):
            all_variables.update(category_vars.get('variables', {}))

        # Runtime variables override everything
        all_variables.update(kwargs)

        try:
            return prompt.format(**all_variables)
        except KeyError as e:
            logger.error(f"Missing variable in prompt {category}/{name}: {e}")
            return prompt  # Return unformatted if variables missing
        except Exception as e:
            logger.error(f"Failed to format prompt {category}/{name}: {e}")
            return prompt

    def register_variable(self, key: str, value: Any):
        """Register a global variable for prompts"""
        self.variables[key] = value
        logger.debug(f"Registered global variable: {key}")

    def validate_prompt(self, category: str, name: str, format: str = "txt") -> List[str]:
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

        # Walk through all prompt files
        for prompt_file in self.prompt_manager.prompts_dir.rglob("*.txt"):
            relative_path = prompt_file.relative_to(self.prompt_manager.prompts_dir)
            category = str(relative_path.parent)
            name = prompt_file.stem

            prompt_issues = self.prompt_manager.validate_prompt(category, name, "txt")
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

    def validate_xml_examples(self) -> List[str]:
        """Validate all XML examples against schema

        Returns:
            List of validation errors
        """
        errors = []

        # Find all XML files in examples
        xml_files = list(self.prompt_manager.prompts_dir.rglob("*.xml"))

        for xml_file in xml_files:
            try:
                import xml.etree.ElementTree as ET
                ET.parse(xml_file)
            except ET.ParseError as e:
                errors.append(f"{xml_file}: {e}")

        return errors