"""Tool Prompt Formatter for Local Model - FIXED FOR QWEN2.5"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ToolPromptFormatter:
    """Formats MCP tools for inclusion in model prompts - optimized for Qwen2.5"""

    def __init__(self, tools: List[Dict[str, Any]]):
        self.tools = tools
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
        
        # CRITICAL: More explicit format for Qwen2.5-7B with completion instructions
        prompt = f"""You have access to the following MCP tools that you MUST use:

{chr(10).join(tool_definitions)}

CRITICAL INSTRUCTIONS:
1. You MUST respond with tool calls, NOT regular text
2. Make ONE tool call to complete the request
3. STOP immediately after making the tool call
4. DO NOT repeat the same tool call multiple times
5. DO NOT generate additional text after the tool call

To call a tool, output EXACTLY this format:
```json
{{
    "tool_name": "workspace",
    "arguments": {{
        "action": "write",
        "path": "filename.py",
        "content": "# Your code here\\nprint('hello')"
    }}
}}
```

IMPORTANT:
- Make ONE tool call and STOP
- Do NOT repeat tool calls
- Do NOT add explanatory text
- ALWAYS use exact tool names shown above
- OUTPUT FORMAT: ```json + tool call + ``` + STOP"""
        
        self.logger.debug(f"EXIT get_tools_prompt: {len(prompt)} characters")
        return prompt

    def _format_single_tool(self, tool: Dict[str, Any]) -> str:
        """Format a single tool for the prompt"""
        try:
            name = tool.get('name', 'unknown_tool')
            description = tool.get('description', 'No description available')

            # Extract input schema parameters
            input_schema = tool.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])

            # Format parameters
            params_list = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', 'No description')
                is_required = param_name in required
                required_marker = " (REQUIRED)" if is_required else " (optional)"

                params_list.append(f"  - {param_name} ({param_type}){required_marker}: {param_desc}")

            params_text = chr(10).join(params_list) if params_list else "  No parameters"

            return f"""**{name}**: {description}
Parameters:
{params_text}"""

        except Exception as e:
            self.logger.error(f"Error formatting tool {tool}: {e}")
            return None

    def validate_tool_call(self, tool_call: Dict[str, Any]) -> tuple[bool, str]:
        """Validate a tool call against available tools"""
        self.logger.debug(f"ENTRY validate_tool_call: {tool_call}")

        tool_name = tool_call.get('tool_name') or tool_call.get('name')
        if not tool_name:
            return False, "No tool_name specified"

        # Find matching tool
        matching_tool = None
        for tool in self.tools:
            if tool.get('name') == tool_name:
                matching_tool = tool
                break

        if not matching_tool:
            available_tools = [tool.get('name', 'unknown') for tool in self.tools]
            return False, f"Tool '{tool_name}' not available. Available tools: {available_tools}"

        # Validate arguments
        arguments = tool_call.get('arguments', {})
        if not isinstance(arguments, dict):
            return False, f"Arguments must be a dictionary, got {type(arguments)}"

        # Check required parameters
        input_schema = matching_tool.get('inputSchema', {})
        required_params = input_schema.get('required', [])

        for param in required_params:
            if param not in arguments:
                return False, f"Required parameter '{param}' missing"

        self.logger.debug(f"EXIT validate_tool_call: valid")
        return True, "Valid tool call"