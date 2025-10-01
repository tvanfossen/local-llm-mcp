"""Tool Prompt Formatter for Local Model - JSON-Only with Prompt Manager"""

import logging
from typing import Dict, List, Any
from src.core.prompts.manager import PromptManager

logger = logging.getLogger(__name__)

class ToolPromptFormatter:
    """Formats MCP tools for inclusion in model prompts - JSON-only with prompt manager"""

    def __init__(self, tools: List[Dict[str, Any]]):
        self.tools = tools
        self.prompt_manager = PromptManager()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_tools_prompt(self) -> str:
        """Generate tool definitions prompt optimized for Qwen2.5"""
        self.logger.debug(f"ENTRY get_tools_prompt: {len(self.tools)} tools")
        
        if not self.tools:
            return ""
        
        tool_definitions = []
        for tool in self.tools:
            definition = self._format_single_tool(tool)
            if definition:
                tool_definitions.append(definition)
        
        # Use JSON-only prompt format
        prompt_format = 'tool_calling_json'
        prompt = self.prompt_manager.format_prompt(
            'system', prompt_format,
            tool_definitions=chr(10).join(tool_definitions)
        )
        
        self.logger.debug(f"EXIT get_tools_prompt: {len(prompt)} characters")
        return prompt

    def _format_single_tool(self, tool: Dict[str, Any]) -> str:
        """Format a single tool for the prompt with enhanced JSON file support"""
        try:
            name = tool.get('name', 'unknown_tool')

            # Try to load tool description from JSON file template with proper substitution
            try:
                # Prepare variables for tool template substitution
                tool_variables = {
                    'tool_name': name,
                    'description': tool.get('description', 'No description available'),
                    'operation': name,  # fallback
                    'action': 'tool_action',  # fallback
                    'path': 'file_path',  # fallback
                    'module_path': 'module.path'  # fallback
                }

                tool_prompt = self.prompt_manager.format_prompt('tools', name, **tool_variables)

                # Check if we got a valid template (not an error message)
                if tool_prompt and not tool_prompt.startswith("["):
                    self.logger.debug(f"✅ Loaded and formatted detailed description for {name} from JSON file")
                    return tool_prompt
                else:
                    self.logger.debug(f"⚠️ JSON template not found or invalid for {name}: {tool_prompt}")

            except Exception as e:
                self.logger.warning(f"Failed to format JSON template for tool {name}: {e}")

            # Enhanced fallback with detailed parameter formatting
            description = tool.get('description', 'No description available')

            # Extract input schema parameters
            input_schema = tool.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])

            # Format parameters with enhanced detail
            params_list = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', 'No description')
                is_required = param_name in required
                required_marker = " (REQUIRED)" if is_required else " (optional)"

                # Add enum information if available
                enum_values = param_info.get('enum')
                enum_text = f" [allowed: {', '.join(enum_values)}]" if enum_values else ""

                # Add default value if available
                default_value = param_info.get('default')
                default_text = f" (default: {default_value})" if default_value is not None else ""

                params_list.append(f"  - {param_name} ({param_type}){required_marker}: {param_desc}{enum_text}{default_text}")

            params_text = chr(10).join(params_list) if params_list else "  No parameters"

            # Enhanced tool description with schema source indicator
            fallback_description = f"""**{name}**: {description}
Parameters:
{params_text}

[Schema source: inputSchema fallback - detailed JSON template preferred]"""

            self.logger.debug(f"🔄 Using enhanced fallback formatting for {name}")
            return fallback_description

        except Exception as e:
            self.logger.error(f"Error formatting tool {tool}: {e}")
            return None

    def validate_tool_call(self, tool_call: Dict[str, Any]) -> tuple[bool, str]:
        """Enhanced validation with specific error detection and guidance"""
        self.logger.debug(f"ENTRY validate_tool_call: {tool_call}")

        tool_name = tool_call.get('tool_name') or tool_call.get('name')
        if not tool_name:
            return False, "No tool_name specified in tool call"

        # Find matching tool
        matching_tool = None
        for tool in self.tools:
            if tool.get('name') == tool_name:
                matching_tool = tool
                break

        if not matching_tool:
            available_tools = [tool.get('name', 'unknown') for tool in self.tools]
            return False, f"Tool '{tool_name}' not available. Available tools: {available_tools}"

        # Validate arguments - support both "parameters" and "arguments" formats
        arguments = tool_call.get('parameters', tool_call.get('arguments', {}))
        if not isinstance(arguments, dict):
            return False, f"Arguments must be a dictionary, got {type(arguments)}. Use {{'parameter_name': 'value'}} format."

        # Enhanced validation for file_metadata tool
        if tool_name == 'file_metadata':
            return self._validate_file_metadata_call(arguments, matching_tool)

        # General validation for other tools
        return self._validate_general_tool_call(arguments, matching_tool, tool_name)

    def _validate_file_metadata_call(self, arguments: dict, tool_schema: dict) -> tuple[bool, str]:
        """Specific validation for file_metadata tool calls with detailed error messages"""

        # Check for invalid action values
        action = arguments.get('action')
        if not action:
            return False, "file_metadata: 'action' parameter is required"

        # Action validation is handled by schema enum validation below

        # Handle model hallucination: redirect add_method to add_function
        if action == "add_method":
            self.logger.info(f"🔀 Redirecting hallucinated 'add_method' to 'add_function'")
            arguments['action'] = "add_function"
            action = "add_function"

        # Validate against schema enum
        input_schema = tool_schema.get('inputSchema', {})
        action_property = input_schema.get('properties', {}).get('action', {})
        allowed_actions = action_property.get('enum', [])

        if allowed_actions and action not in allowed_actions:
            return False, (
                f"file_metadata: Invalid action '{action}'. Allowed actions: {allowed_actions}"
            )

        # Validate parameters format for add_function
        if action == 'add_function':
            parameters = arguments.get('parameters')
            if parameters is not None:
                if not isinstance(parameters, list):
                    return False, (
                        "file_metadata: 'parameters' must be an array of objects. "
                        f"Example: [{{'name': 'self', 'type': 'ClassName'}}, {{'name': 'x', 'type': 'float'}}] "
                        f"Got: {type(parameters)} - {parameters}"
                    )

                # Validate parameter structure
                for i, param in enumerate(parameters):
                    if not isinstance(param, dict):
                        return False, (
                            f"file_metadata: Parameter {i} must be an object with 'name' and 'type' fields. "
                            f"Got: {type(param)} - {param}"
                        )

                    if 'name' not in param:
                        return False, (
                            f"file_metadata: Parameter {i} missing 'name' field. "
                            f"Required format: {{'name': 'param_name', 'type': 'param_type'}}"
                        )

            # Validate operations format
            operations = arguments.get('operations')
            if operations is not None:
                if not isinstance(operations, list):
                    return False, (
                        "file_metadata: 'operations' must be an array of objects. "
                        f"Example: [{{'type': 'return', 'value': 'x + y'}}] "
                        f"Got: {type(operations)} - {operations}"
                    )

                # Validate operations structure
                for i, op in enumerate(operations):
                    if not isinstance(op, dict):
                        return False, (
                            f"file_metadata: Operation {i} must be an object with 'type' and 'value' fields. "
                            f"Got: {type(op)} - {op}"
                        )

        # Check required parameters
        required_params = input_schema.get('required', [])
        for param in required_params:
            if param not in arguments:
                return False, f"file_metadata: Required parameter '{param}' missing"

        return True, "Valid file_metadata tool call"

    def _validate_general_tool_call(self, arguments: dict, tool_schema: dict, tool_name: str) -> tuple[bool, str]:
        """General validation for non-file_metadata tools"""

        # Check required parameters
        input_schema = tool_schema.get('inputSchema', {})
        required_params = input_schema.get('required', [])

        for param in required_params:
            if param not in arguments:
                return False, f"{tool_name}: Required parameter '{param}' missing"

        # Validate enum values if present
        properties = input_schema.get('properties', {})
        for param_name, param_value in arguments.items():
            if param_name in properties:
                param_schema = properties[param_name]
                allowed_values = param_schema.get('enum')
                if allowed_values and param_value not in allowed_values:
                    return False, (
                        f"{tool_name}: Invalid value '{param_value}' for parameter '{param_name}'. "
                        f"Allowed values: {allowed_values}"
                    )

        self.logger.debug(f"EXIT validate_tool_call: valid {tool_name} call")
        return True, f"Valid {tool_name} tool call"