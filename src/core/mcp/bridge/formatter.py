"""Tool Call Formatter for Local Model Communication

Provides strict JSON schema validation and tool-specific formatting
for Qwen2.5-7B model interactions.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolCallFormatter:
    """Formatter for tool calls and responses"""

    # Tool schemas for validation
    TOOL_SCHEMAS = {
        "workspace": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write", "create_dir", "list"]},
                "path": {"type": "string"},
                "json_artifact": {"type": "object"},
                "content": {"type": "string"},
                "recursive": {"type": "boolean"}
            },
            "required": ["action"]
        },
        "validation": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["tests", "pre-commit", "file-length", "all"]},
                "file_paths": {"type": "array", "items": {"type": "string"}},
                "test_path": {"type": "string"},
                "max_lines": {"type": "integer"}
            },
            "required": ["operation"]
        },
        "git_operations": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["status", "diff", "commit", "log", "branch"]},
                "message": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}},
                "add_all": {"type": "boolean"}
            },
            "required": ["operation"]
        }
    }

    def __init__(self):
        self.result_truncation_limit = 1000  # Character limit for tool results

    def format_tool_definition(self, tool_name: str, description: str) -> Dict[str, Any]:
        """Format tool definition for model consumption"""
        schema = self.TOOL_SCHEMAS.get(tool_name, {})

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": schema
            }
        }

    def format_all_tools_for_qwen(self) -> str:
        """Format all available tools for Qwen2.5-7B prompt"""
        tool_descriptions = {
            "workspace": "Manage workspace files with JSON artifacts for code generation",
            "validation": "Validate code files using tests, linting, and pre-commit hooks",
            "git_operations": "Perform git operations like status, diff, commit"
        }

        prompt = "You have access to the following tools:\n\n"

        for tool_name, description in tool_descriptions.items():
            schema = self.TOOL_SCHEMAS[tool_name]
            prompt += f"**{tool_name}**: {description}\n"
            prompt += f"Parameters: {json.dumps(schema, indent=2)}\n\n"

        prompt += """To use a tool, respond with JSON in this format:
```json
{
    "tool_name": "workspace",
    "arguments": {
        "action": "write",
        "path": "example.py",
        "json_artifact": {...}
    }
}
```

Always use this exact JSON format for tool calls."""

        return prompt

    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Validate tool call arguments against schema"""
        if tool_name not in self.TOOL_SCHEMAS:
            logger.warning(f"Unknown tool: {tool_name}")
            return False

        schema = self.TOOL_SCHEMAS[tool_name]
        return self._validate_against_schema(arguments, schema)

    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Simple schema validation"""
        if "required" in schema:
            for required_field in schema["required"]:
                if required_field not in data:
                    logger.warning(f"Missing required field: {required_field}")
                    return False

        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                if field in data:
                    if not self._validate_field(data[field], field_schema):
                        return False

        return True

    def _validate_field(self, value: Any, field_schema: Dict[str, Any]) -> bool:
        """Validate individual field against schema"""
        expected_type = field_schema.get("type")

        if expected_type == "string" and not isinstance(value, str):
            return False
        elif expected_type == "integer" and not isinstance(value, int):
            return False
        elif expected_type == "boolean" and not isinstance(value, bool):
            return False
        elif expected_type == "array" and not isinstance(value, list):
            return False
        elif expected_type == "object" and not isinstance(value, dict):
            return False

        if "enum" in field_schema and value not in field_schema["enum"]:
            return False

        return True

    def format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format tool execution result for model consumption"""
        # Truncate large results to prevent context overflow
        formatted_result = {
            "tool_name": tool_name,
            "success": result.get("success", False),
            "timestamp": result.get("timestamp"),
        }

        # Handle content based on success
        if result.get("success"):
            content = result.get("content", "")
            if isinstance(content, str) and len(content) > self.result_truncation_limit:
                formatted_result["content"] = content[:self.result_truncation_limit] + "... [truncated]"
            else:
                formatted_result["content"] = content
        else:
            formatted_result["error"] = result.get("error", "Unknown error")

        return formatted_result

    def create_tool_response_message(self, results: List[Dict[str, Any]]) -> str:
        """Create a formatted message with tool execution results"""
        if not results:
            return "No tool results to display."

        message_parts = ["Tool execution results:\n"]

        for result in results:
            tool_name = result.get("tool_name", "unknown")
            success = result.get("success", False)

            if success:
                message_parts.append(f"✅ {tool_name}: Success")
                if "content" in result:
                    content = str(result["content"])[:200]  # Compact representation
                    message_parts.append(f"   Output: {content}")
            else:
                error = result.get("error", "Unknown error")
                message_parts.append(f"❌ {tool_name}: {error}")

            message_parts.append("")  # Empty line

        return "\n".join(message_parts)

    def extract_json_artifact_schema(self) -> Dict[str, Any]:
        """Get the JSON artifact schema for Python code elements"""
        return {
            "type": "object",
            "properties": {
                "element_type": {
                    "type": "string",
                    "enum": ["function", "class", "module", "import"]
                },
                "element_data": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "docstring": {"type": "string"},
                        "parameters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "default": {"type": ["string", "null"]}
                                }
                            }
                        },
                        "return_type": {"type": "string"},
                        "body": {"type": "string"},
                        "decorators": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["element_type", "element_data"]
        }