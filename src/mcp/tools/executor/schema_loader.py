"""Dynamic Schema Loader for MCP Tools

Eliminates DRY violation by loading tool schemas from prompts/tools/*.json files
instead of hardcoding them in the executor.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolSchemaLoader:
    """Loads tool schemas dynamically from prompts/tools/*.json files"""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize schema loader

        Args:
            prompts_dir: Path to prompts directory. If None, auto-detect from project root.
        """
        if prompts_dir is None:
            # Auto-detect prompts directory from current file location
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[4]  # Go up to project root
            prompts_dir = project_root / "prompts"

        self.prompts_dir = prompts_dir
        self.tools_dir = prompts_dir / "tools"
        self.cache = {}

        logger.debug(f"ToolSchemaLoader initialized with prompts_dir: {self.prompts_dir}")

    def load_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Load schema for a specific tool from its JSON file

        Args:
            tool_name: Name of the tool (e.g., 'file_metadata', 'workspace')

        Returns:
            MCP tool schema dictionary or None if loading fails
        """
        # Check cache first
        cache_key = tool_name
        if cache_key in self.cache:
            return self.cache[cache_key]

        tool_file = self.tools_dir / f"{tool_name}.json"

        if not tool_file.exists():
            logger.error(f"Tool schema file not found: {tool_file}")
            return None

        try:
            with open(tool_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract schema components from the JSON structure
            schema = self._convert_prompt_to_mcp_schema(data, tool_name)

            # Cache the result
            self.cache[cache_key] = schema

            logger.debug(f"Successfully loaded schema for {tool_name}")
            return schema

        except Exception as e:
            logger.error(f"Failed to load schema for {tool_name}: {e}")
            return None

    def _convert_prompt_to_mcp_schema(self, prompt_data: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Convert prompt JSON structure to MCP tool schema format

        Args:
            prompt_data: Raw JSON data from prompts/tools/*.json
            tool_name: Name of the tool

        Returns:
            MCP-compatible tool schema
        """
        try:
            # Extract basic info
            description = prompt_data.get("description", f"Tool: {tool_name}")

            # Build input schema from parameters
            parameters = prompt_data.get("parameters", [])
            properties = {}
            required = []

            for param in parameters:
                param_name = param.get("name")
                if not param_name:
                    continue

                param_info = {
                    "type": param.get("type", "string"),
                    "description": param.get("description", "")
                }

                # Handle enum values (allowed_values)
                if "allowed_values" in param:
                    param_info["enum"] = param["allowed_values"]

                # Handle default values
                if "default" in param:
                    param_info["default"] = param["default"]

                properties[param_name] = param_info

                # Check if required
                if param.get("required", False):
                    required.append(param_name)

            # Also check action_requirements for required fields
            action_requirements = prompt_data.get("action_requirements", {})
            if action_requirements:
                # For file_metadata, action is always required
                if "action" in properties and "action" not in required:
                    required.append("action")

            input_schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }

            logger.debug(f"Generated schema for {tool_name}: {len(properties)} properties, {len(required)} required")

            return {
                "name": tool_name,
                "description": description,
                "inputSchema": input_schema
            }

        except Exception as e:
            logger.error(f"Failed to convert prompt data to MCP schema for {tool_name}: {e}")
            raise

    def get_all_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load schemas for all available tool JSON files

        Returns:
            Dictionary mapping tool names to their schemas
        """
        schemas = {}

        if not self.tools_dir.exists():
            logger.error(f"Tools directory not found: {self.tools_dir}")
            return schemas

        # Find all JSON files in tools directory
        for json_file in self.tools_dir.glob("*.json"):
            tool_name = json_file.stem  # filename without .json extension
            schema = self.load_tool_schema(tool_name)
            if schema:
                schemas[tool_name] = schema

        logger.info(f"Loaded {len(schemas)} tool schemas dynamically")
        return schemas