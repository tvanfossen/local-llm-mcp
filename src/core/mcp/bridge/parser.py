"""Tool Call Parser for Local Model Output"""

import json
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ToolCallParser:
    """Parser for extracting tool calls from LLM text output"""

    # Patterns for different tool call formats
    TOOL_FENCE_RE = re.compile(
        r'```(?:json|tool)?\s*\n(.*?)\n```',
        re.DOTALL | re.IGNORECASE
    )

    TOOL_TAG_RE = re.compile(
        r'<tool_call>\s*(.*?)\s*</tool_call>',
        re.DOTALL | re.IGNORECASE
    )

    JSON_BLOCK_RE = re.compile(
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        re.DOTALL
    )

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from model output text"""
        self.logger.debug(f"ENTRY extract_tool_calls: text_len={len(text)}")

        if not text:
            self.logger.debug("EXIT extract_tool_calls: empty text")
            return []

        tool_calls = []

        # Strategy 1: Try fence blocks first (```json or ```tool)
        fence_calls = self._extract_from_fences(text)
        tool_calls.extend(fence_calls)

        # Strategy 2: Try XML-style tags if no fence blocks
        if not tool_calls:
            tag_calls = self._extract_from_tags(text)
            tool_calls.extend(tag_calls)

        # Strategy 3: Try bare JSON blocks as last resort
        if not tool_calls:
            json_calls = self._extract_from_json_blocks(text)
            tool_calls.extend(json_calls)

        # Validate and filter tool calls
        validated_calls = []
        for call in tool_calls:
            if self._validate_tool_call(call):
                validated_calls.append(call)
            else:
                self.logger.warning(f"Invalid tool call: {call}")

        self.logger.debug(f"EXIT extract_tool_calls: found {len(validated_calls)} valid calls")
        return validated_calls

    def _extract_from_fences(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from code fence blocks"""
        calls = []
        for match in self.TOOL_FENCE_RE.finditer(text):
            json_text = match.group(1).strip()
            parsed = self._parse_json_safely(json_text)
            if parsed:
                calls.append(parsed)
        return calls

    def _extract_from_tags(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from XML-style tags"""
        calls = []
        for match in self.TOOL_TAG_RE.finditer(text):
            json_text = match.group(1).strip()
            parsed = self._parse_json_safely(json_text)
            if parsed:
                calls.append(parsed)
        return calls

    def _extract_from_json_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from bare JSON blocks"""
        calls = []
        for match in self.JSON_BLOCK_RE.finditer(text):
            json_text = match.group(0).strip()
            parsed = self._parse_json_safely(json_text)
            if parsed and self._looks_like_tool_call(parsed):
                calls.append(parsed)
        return calls

    def _parse_json_safely(self, json_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON text with error handling"""
        if not json_text:
            return None

        try:
            # Clean up common JSON issues
            cleaned = self._clean_json_text(json_text)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self.logger.debug(f"JSON parse failed: {e} for text: {cleaned[:100]}...")
            return None

    def _clean_json_text(self, text: str) -> str:
        """Clean up common JSON formatting issues"""
        # Replace smart quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',(\\s*[}\\]])', r'\\1', text)

        return text.strip()

    def _looks_like_tool_call(self, data: Dict[str, Any]) -> bool:
        """Check if parsed JSON looks like a tool call"""
        if not isinstance(data, dict):
            return False

        # Check for common tool call patterns
        tool_indicators = [
            'tool_name', 'name', 'function', 'action', 'operation', 'command'
        ]

        return any(key in data for key in tool_indicators)

    def _validate_tool_call(self, call: Dict[str, Any]) -> bool:
        """Validate tool call structure"""
        if not isinstance(call, dict):
            return False

        # Must have tool name
        tool_name = call.get('tool_name') or call.get('name') or call.get('function')
        if not tool_name:
            return False

        # Must have arguments (can be empty dict)
        if 'arguments' not in call and 'args' not in call and 'parameters' not in call:
            # Add empty arguments if missing
            call['arguments'] = {}

        return True