"""Unified Tool Call Parser - JSON-Only

This module provides JSON-only tool call parsing for the local-llm-mcp system.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ParsingStrategy(Enum):
    """Available parsing strategies - JSON only"""
    JSON_PRIMARY = "json_primary"    # JSON-only parsing (default)
    JSON_ONLY = "json_only"         # Only parse JSON


class ParseResult:
    """Result of tool call parsing"""
    def __init__(self, tool_calls: List[Dict[str, Any]], strategy_used: str, errors: List[str] = None):
        self.tool_calls = tool_calls
        self.strategy_used = strategy_used
        self.errors = errors or []
        self.success = len(tool_calls) > 0

    def __len__(self):
        return len(self.tool_calls)

    def __bool__(self):
        return self.success


class UnifiedToolCallParser:
    """Unified parser for JSON tool calls only"""

    # Regex patterns for JSON formats
    JSON_FENCE_RE = re.compile(r'```(?:json)?\s*\n?(.*?)\n?```', re.DOTALL | re.IGNORECASE)
    JSON_BLOCK_RE = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)

    def __init__(self, strategy: ParsingStrategy = ParsingStrategy.JSON_PRIMARY):
        self.strategy = strategy
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse(self, text: str) -> ParseResult:
        """Parse tool calls from text using JSON-only approach"""
        self.logger.info(f"🔍 JSON PARSER: Processing {len(text)} chars")

        if not text:
            return ParseResult([], "empty_input", ["Empty input text"])

        return self._extract_json_tool_calls(text)

    def _extract_json_tool_calls(self, text: str) -> ParseResult:
        """Extract JSON tool calls from text"""
        tool_calls = []
        errors = []

        try:
            # Strategy 1: JSON fence blocks
            fence_calls, fence_errors = self._extract_json_from_fences(text)
            tool_calls.extend(fence_calls)
            errors.extend(fence_errors)

            # Strategy 2: Direct JSON objects if no fence blocks
            if not tool_calls:
                direct_calls, direct_errors = self._extract_json_direct(text)
                tool_calls.extend(direct_calls)
                errors.extend(direct_errors)

            # Validate all calls
            valid_calls = []
            for call in tool_calls:
                if self._validate_tool_call(call):
                    valid_calls.append(call)
                else:
                    errors.append(f"Invalid JSON tool call: {call}")

            return ParseResult(valid_calls, "json", errors)

        except Exception as e:
            errors.append(f"JSON parsing error: {e}")
            return ParseResult([], "json_error", errors)

    def _extract_json_from_fences(self, text: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Extract JSON tool calls from fence blocks"""
        calls = []
        errors = []
        matches = list(self.JSON_FENCE_RE.finditer(text))

        for match in matches:
            json_content = match.group(1).strip()
            parsed_call = self._parse_json_safely(json_content)
            if parsed_call:
                calls.append(parsed_call)
            else:
                # If there were matches but parsing failed, it's an error
                if json_content.strip():
                    errors.append(f"Failed to parse JSON fence block: invalid JSON syntax")

        return calls, errors

    def _extract_json_direct(self, text: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Extract JSON tool calls directly from text"""
        calls = []
        errors = []

        # Find JSON-like structures
        matches = list(self.JSON_BLOCK_RE.finditer(text))

        for match in matches:
            json_content = match.group().strip()
            parsed_call = self._parse_json_safely(json_content)
            if parsed_call and "tool_name" in parsed_call:
                calls.append(parsed_call)
            elif json_content.strip().startswith('{') and json_content.strip().endswith('}'):
                # Looks like JSON but failed to parse or missing tool_name
                errors.append(f"Failed to parse JSON block: invalid syntax or missing tool_name")

        return calls, errors

    def _parse_json_safely(self, json_text: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON with error handling"""
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            self.logger.debug(f"JSON parse failed: {e}")
        except Exception as e:
            self.logger.debug(f"JSON processing failed: {e}")

        return None

    def _validate_tool_call(self, call: Dict[str, Any]) -> bool:
        """Validate that a tool call has required structure"""
        if not isinstance(call, dict):
            return False

        if "tool_name" not in call:
            return False

        if not call["tool_name"]:
            return False

        # Accept both "parameters" (new JSON format) and "arguments" (legacy)
        if "parameters" not in call and "arguments" not in call:
            return False

        params_key = "parameters" if "parameters" in call else "arguments"
        if not isinstance(call[params_key], dict):
            return False

        return True


def create_parser() -> UnifiedToolCallParser:
    """Factory function to create JSON-only parser"""
    return UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)


# Backward compatibility functions
def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Backward compatible function for existing code - JSON only"""
    parser = create_parser()
    result = parser.parse(text)
    return result.tool_calls