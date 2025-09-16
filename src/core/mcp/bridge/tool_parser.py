"""Tool Call Parser for Local Model Output

Adapted from society_scribe's ToolCallParser to handle multiple parsing
strategies for extracting tool calls from Qwen2.5-7B model output.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ToolCallParser:
    """Parser for extracting tool calls from LLM text output"""

    # Patterns for different tool call formats
    TOOL_FENCE_RE = re.compile(
        r'```(?:json|tool)\s*\n(.*?)\n```',
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

    def __init__(self, max_recent_calls: int = 10):
        self.recent_calls: Set[str] = set()
        self.max_recent_calls = max_recent_calls

    def parse_tool_calls(self, text: str) -> List[Dict]:
        """Parse tool calls from text using multiple strategies"""
        tool_calls = []

        # Strategy 1: Try fence blocks first (```json or ```tool)
        fence_calls = self._extract_from_fences(text)
        tool_calls.extend(fence_calls)

        # Strategy 2: Try XML-style tags
        if not tool_calls:
            tag_calls = self._extract_from_tags(text)
            tool_calls.extend(tag_calls)

        # Strategy 3: Try bare JSON blocks
        if not tool_calls:
            json_calls = self._extract_from_json_blocks(text)
            tool_calls.extend(json_calls)

        # Filter duplicates and validate
        validated_calls = []
        for call in tool_calls:
            if self._validate_and_dedupe_call(call):
                validated_calls.append(call)

        return validated_calls

    def _extract_from_fences(self, text: str) -> List[Dict]:
        """Extract tool calls from code fence blocks"""
        calls = []
        for match in self.TOOL_FENCE_RE.finditer(text):
            json_text = match.group(1).strip()
            parsed = self._parse_json_text(json_text)
            if parsed:
                calls.append(parsed)
        return calls

    def _extract_from_tags(self, text: str) -> List[Dict]:
        """Extract tool calls from XML-style tags"""
        calls = []
        for match in self.TOOL_TAG_RE.finditer(text):
            json_text = match.group(1).strip()
            parsed = self._parse_json_text(json_text)
            if parsed:
                calls.append(parsed)
        return calls

    def _extract_from_json_blocks(self, text: str) -> List[Dict]:
        """Extract tool calls from bare JSON blocks in text"""
        calls = []
        for match in self.JSON_BLOCK_RE.finditer(text):
            json_text = match.group(0).strip()
            parsed = self._parse_json_text(json_text)
            if parsed and self._looks_like_tool_call(parsed):
                calls.append(parsed)
        return calls

    def _parse_json_text(self, json_text: str) -> Optional[Dict]:
        """Parse JSON text with error handling and cleanup"""
        if not json_text:
            return None

        # Clean up common JSON issues
        cleaned = self._clean_json_text(json_text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse failed: {e} for text: {cleaned[:100]}")
            return None

    def _clean_json_text(self, text: str) -> str:
        """Clean up common JSON formatting issues"""
        # Replace smart quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Ensure balanced braces
        open_braces = text.count('{')
        close_braces = text.count('}')
        if open_braces > close_braces:
            text += '}' * (open_braces - close_braces)

        return text.strip()

    def _looks_like_tool_call(self, data: Dict) -> bool:
        """Check if parsed JSON looks like a tool call"""
        if not isinstance(data, dict):
            return False

        # Check for common tool call patterns
        tool_indicators = [
            'tool_name', 'function_name', 'action',
            'operation', 'command', 'method'
        ]

        return any(key in data for key in tool_indicators)

    def _validate_and_dedupe_call(self, call: Dict) -> bool:
        """Validate tool call and check for duplicates"""
        if not isinstance(call, dict):
            return False

        # Create signature for deduplication
        signature = self._create_call_signature(call)
        if signature in self.recent_calls:
            logger.debug(f"Duplicate tool call detected: {signature}")
            return False

        # Add to recent calls and maintain size limit
        self.recent_calls.add(signature)
        if len(self.recent_calls) > self.max_recent_calls:
            # Remove oldest (this is a simplification; in practice use deque)
            oldest = next(iter(self.recent_calls))
            self.recent_calls.remove(oldest)

        return True

    def _create_call_signature(self, call: Dict) -> str:
        """Create a signature for tool call deduplication"""
        # Use a subset of fields for signature to allow parameter variations
        key_fields = ['tool_name', 'function_name', 'action', 'operation']
        signature_parts = []

        for field in key_fields:
            if field in call:
                signature_parts.append(f"{field}:{call[field]}")

        return "|".join(signature_parts) if signature_parts else str(hash(str(call)))

    def extract_balanced_json(self, text: str, start_pos: int = 0) -> Tuple[Optional[str], int]:
        """Extract balanced JSON object starting from position"""
        if start_pos >= len(text):
            return None, start_pos

        # Find opening brace
        brace_pos = text.find('{', start_pos)
        if brace_pos == -1:
            return None, len(text)

        # Track brace balance
        brace_count = 0
        in_string = False
        escape_next = False

        for i in range(brace_pos, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON object
                        json_text = text[brace_pos:i + 1]
                        return json_text, i + 1

        return None, len(text)