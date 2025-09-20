"""Unified Tool Call Parser - Single Source of Truth

This module consolidates all tool call parsing logic into a single, unified system
that handles both XML and JSON formats with proper fallback mechanisms.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ParsingStrategy(Enum):
    """Available parsing strategies"""
    XML_PRIMARY = "xml_primary"      # Try XML first, fallback to JSON
    JSON_PRIMARY = "json_primary"    # Try JSON first, fallback to XML
    XML_ONLY = "xml_only"           # Only parse XML
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
    """Unified parser for both XML and JSON tool calls"""

    # Regex patterns for different formats
    XML_FENCE_RE = re.compile(r'```xml\s*\n?(.*?)\n?```', re.DOTALL | re.IGNORECASE)
    JSON_FENCE_RE = re.compile(r'```(?:json)?\s*\n?(.*?)\n?```', re.DOTALL | re.IGNORECASE)
    XML_TOOL_CALL_RE = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL | re.IGNORECASE)
    JSON_BLOCK_RE = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)

    def __init__(self, strategy: ParsingStrategy = ParsingStrategy.XML_PRIMARY):
        self.strategy = strategy
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse(self, text: str) -> ParseResult:
        """Parse tool calls from text using the configured strategy"""
        self.logger.info(f"🔍 UNIFIED PARSER: Processing {len(text)} chars with {self.strategy.value}")

        if not text:
            return ParseResult([], "empty_input", ["Empty input text"])

        if self.strategy == ParsingStrategy.XML_PRIMARY:
            return self._parse_xml_primary(text)
        elif self.strategy == ParsingStrategy.JSON_PRIMARY:
            return self._parse_json_primary(text)
        elif self.strategy == ParsingStrategy.XML_ONLY:
            return self._parse_xml_only(text)
        elif self.strategy == ParsingStrategy.JSON_ONLY:
            return self._parse_json_only(text)
        else:
            return ParseResult([], "unknown_strategy", [f"Unknown strategy: {self.strategy}"])

    def _parse_xml_primary(self, text: str) -> ParseResult:
        """Try XML first, fallback to JSON"""
        # Try XML parsing
        xml_result = self._extract_xml_tool_calls(text)
        if xml_result.success:
            self.logger.info(f"✅ XML parsing successful: {len(xml_result)} calls")
            return xml_result

        self.logger.info("⚠️ XML parsing failed, trying JSON fallback")

        # Fallback to JSON
        json_result = self._extract_json_tool_calls(text)
        if json_result.success:
            self.logger.info(f"✅ JSON fallback successful: {len(json_result)} calls")
            return json_result

        # Both failed
        all_errors = xml_result.errors + json_result.errors
        return ParseResult([], "both_failed", all_errors)

    def _parse_json_primary(self, text: str) -> ParseResult:
        """Try JSON first, fallback to XML"""
        # Try JSON parsing
        json_result = self._extract_json_tool_calls(text)
        if json_result.success:
            self.logger.info(f"✅ JSON parsing successful: {len(json_result)} calls")
            return json_result

        self.logger.info("⚠️ JSON parsing failed, trying XML fallback")

        # Fallback to XML
        xml_result = self._extract_xml_tool_calls(text)
        if xml_result.success:
            self.logger.info(f"✅ XML fallback successful: {len(xml_result)} calls")
            return xml_result

        # Both failed
        all_errors = json_result.errors + xml_result.errors
        return ParseResult([], "both_failed", all_errors)

    def _parse_xml_only(self, text: str) -> ParseResult:
        """Parse XML only"""
        return self._extract_xml_tool_calls(text)

    def _parse_json_only(self, text: str) -> ParseResult:
        """Parse JSON only"""
        return self._extract_json_tool_calls(text)

    def _extract_xml_tool_calls(self, text: str) -> ParseResult:
        """Extract XML tool calls from text"""
        tool_calls = []
        errors = []

        try:
            # Strategy 1: XML fence blocks
            try:
                fence_calls = self._extract_xml_from_fences(text)
                tool_calls.extend(fence_calls)
            except Exception as e:
                errors.append(f"XML fence parsing error: {e}")

            # Strategy 2: Direct XML tags if no fence blocks
            if not tool_calls:
                try:
                    tag_calls = self._extract_xml_from_tags(text)
                    tool_calls.extend(tag_calls)
                except Exception as e:
                    errors.append(f"XML tag parsing error: {e}")

            # Validate all calls
            valid_calls = []
            for call in tool_calls:
                if self._validate_tool_call(call):
                    valid_calls.append(call)
                else:
                    errors.append(f"Invalid XML tool call: {call}")

            return ParseResult(valid_calls, "xml", errors)

        except Exception as e:
            errors.append(f"XML parsing error: {e}")
            return ParseResult([], "xml_error", errors)

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

    def _extract_xml_from_fences(self, text: str) -> List[Dict[str, Any]]:
        """Extract XML tool calls from fence blocks"""
        calls = []
        matches = list(self.XML_FENCE_RE.finditer(text))

        for match in matches:
            xml_content = match.group(1).strip()
            try:
                parsed_calls = self._parse_xml_content(xml_content)
                calls.extend(parsed_calls)
            except Exception as e:
                # Re-raise with context about which fence block failed
                raise Exception(f"Failed to parse XML fence block: {e}")

        return calls

    def _extract_xml_from_tags(self, text: str) -> List[Dict[str, Any]]:
        """Extract XML tool calls from direct tags"""
        calls = []
        matches = list(self.XML_TOOL_CALL_RE.finditer(text))

        for match in matches:
            xml_content = f"<tool_call>{match.group(1)}</tool_call>"
            try:
                parsed_calls = self._parse_xml_content(xml_content)
                calls.extend(parsed_calls)
            except Exception as e:
                # Re-raise with context about which tag failed
                raise Exception(f"Failed to parse XML tag: {e}")

        return calls

    def _parse_xml_content(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse XML content to extract tool calls"""
        calls = []

        try:
            # Try to parse as complete XML
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                # Wrap in root and try again
                wrapped = f"<root>{xml_content}</root>"
                root = ET.fromstring(wrapped)

            # Find all tool_call elements
            tool_call_elements = root.findall('.//tool_call')

            # If no nested tool_calls and root is tool_call, use root
            if not tool_call_elements and root.tag == 'tool_call':
                tool_call_elements = [root]

            for elem in tool_call_elements:
                call = self._parse_xml_tool_call_element(elem)
                if call:
                    calls.append(call)

        except ET.ParseError as e:
            self.logger.error(f"XML parse error: {e}")
            raise  # Re-raise so caller can handle
        except Exception as e:
            self.logger.error(f"XML processing error: {e}")
            raise  # Re-raise so caller can handle

        return calls

    def _parse_xml_tool_call_element(self, elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse a single XML tool_call element"""
        try:
            # Extract tool name - handle both formats
            tool_name = None

            # Format 1: <tool_name>workspace</tool_name>
            tool_name_elem = elem.find('tool_name')
            if tool_name_elem is not None and tool_name_elem.text:
                tool_name = tool_name_elem.text.strip()
            else:
                # Format 2: <workspace>action</workspace> (tool name as tag)
                # Find the first child that's not 'arguments'
                for child in elem:
                    if child.tag != 'arguments':
                        tool_name = child.tag
                        break

            if not tool_name:
                self.logger.error("No tool name found in XML tool call")
                return None

            # Extract arguments
            arguments = {}
            args_elem = elem.find('arguments')
            if args_elem is not None:
                for arg_elem in args_elem:
                    arg_name = arg_elem.tag

                    # Handle nested XML content (like structured_content parameter)
                    if len(arg_elem) > 0:
                        # Element has children - extract full inner XML
                        inner_xml_parts = []
                        for child in arg_elem:
                            inner_xml_parts.append(ET.tostring(child, encoding='unicode'))
                        arg_value = ''.join(inner_xml_parts).strip()
                    else:
                        # Simple text content
                        arg_value = arg_elem.text or ""

                    arguments[arg_name] = arg_value

            return {
                "tool_name": tool_name,
                "arguments": arguments
            }

        except Exception as e:
            self.logger.error(f"Failed to parse XML tool call: {e}")
            return None

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

        if "arguments" not in call:
            return False

        if not isinstance(call["arguments"], dict):
            return False

        return True


def create_parser(use_xml: bool = False) -> UnifiedToolCallParser:
    """Factory function to create parser with appropriate strategy"""
    if use_xml:
        return UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)
    else:
        return UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)


# Backward compatibility functions
def extract_tool_calls(text: str, use_xml: bool = False) -> List[Dict[str, Any]]:
    """Backward compatible function for existing code"""
    parser = create_parser(use_xml)
    result = parser.parse(text)
    return result.tool_calls