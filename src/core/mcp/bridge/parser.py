"""Tool Call Parser for Local Model Output - ENHANCED DETECTION"""

import json
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ToolCallParser:
    """Parser for extracting tool calls from LLM text output - enhanced for Qwen2.5"""

    # Patterns for different tool call formats
    TOOL_FENCE_RE = re.compile(
        r'```(?:json|tool)?\s*\n?(.*?)\n?```',
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
        """Extract tool calls from model output text - enhanced detection with comprehensive debugging"""
        self.logger.info(f"🔍 PARSER ENTRY: Processing {len(text)} characters")
        self.logger.info(f"🔍 TEXT PREVIEW: {text[:200]}...")
        self.logger.info(f"🔍 TEXT SUFFIX: ...{text[-200:]}")

        if not text:
            self.logger.warning("⚠️ PARSER: Empty text input")
            return []

        tool_calls = []

        # Strategy 1: Try fence blocks first
        self.logger.info("🔍 PARSER: Attempting fence block extraction...")
        fence_calls = self._extract_from_fences(text)
        self.logger.info(f"🔍 FENCE RESULT: Found {len(fence_calls)} calls")
        if fence_calls:
            for i, call in enumerate(fence_calls):
                self.logger.info(f"  Fence call {i+1}: {call.get('tool_name', 'unknown')}")
        tool_calls.extend(fence_calls)

        # Strategy 2: Try XML-style tags
        if not tool_calls:
            self.logger.info("🔍 PARSER: Attempting XML tag extraction...")
            tag_calls = self._extract_from_tags(text)
            self.logger.info(f"🔍 TAG RESULT: Found {len(tag_calls)} calls")
            tool_calls.extend(tag_calls)

        # Strategy 3: Try bare JSON blocks
        if not tool_calls:
            self.logger.info("🔍 PARSER: Attempting bare JSON extraction...")
            json_calls = self._extract_from_json_blocks(text)
            self.logger.info(f"🔍 JSON RESULT: Found {len(json_calls)} calls")
            tool_calls.extend(json_calls)

        # Strategy 3.5: Try AST-based JSON extraction (more robust)
        if not tool_calls:
            self.logger.info("🔍 PARSER: Attempting AST-based JSON extraction...")
            ast_calls = self._extract_with_ast_parsing(text)
            self.logger.info(f"🔍 AST RESULT: Found {len(ast_calls)} calls")
            tool_calls.extend(ast_calls)

        # Strategy 4: AGGRESSIVE - Look for tool-like patterns
        if not tool_calls:
            self.logger.info("🔍 PARSER: Attempting aggressive pattern extraction...")
            # Look for patterns like "workspace tool" or "call workspace"
            if 'workspace' in text.lower() or 'tool' in text.lower():
                self.logger.warning("⚠️ Model mentioned tools but didn't format properly")
                # Try to extract any JSON-like structure
                json_pattern = re.compile(r'\{[^}]*"(?:tool_name|action|operation)"[^}]*\}', re.DOTALL)
                matches = list(json_pattern.finditer(text))
                self.logger.info(f"🔍 AGGRESSIVE: Found {len(matches)} potential JSON matches")
                for i, match in enumerate(matches):
                    try:
                        json_text = match.group()
                        self.logger.info(f"🔍 AGGRESSIVE MATCH {i+1}: {json_text[:100]}...")
                        parsed = json.loads(json_text)
                        if parsed:
                            tool_calls.append(parsed)
                            self.logger.info(f"🔧 Extracted tool call via aggressive pattern: {parsed.get('tool_name', 'unknown')}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ AGGRESSIVE PARSE FAILED {i+1}: {e}")

        # Validate and filter with detailed logging
        self.logger.info(f"🔍 VALIDATION: Processing {len(tool_calls)} raw tool calls")
        validated_calls = []
        for i, call in enumerate(tool_calls):
            self.logger.info(f"🔍 VALIDATING CALL {i+1}: {call}")
            if self._validate_tool_call(call):
                validated_calls.append(call)
                self.logger.info(f"✅ CALL {i+1} VALID")
            else:
                self.logger.warning(f"❌ CALL {i+1} INVALID: {call}")

        if validated_calls:
            self.logger.info(f"✅ PARSER SUCCESS: {len(validated_calls)} valid tool calls detected")
            for i, call in enumerate(validated_calls):
                self.logger.info(f"  Final call {i+1}: {call.get('tool_name') or call.get('name', 'unknown')}")
        else:
            self.logger.error(f"❌ PARSER FAILURE: NO VALID TOOL CALLS in {len(text)} characters")
            self.logger.error(f"❌ SAMPLE TEXT: {text[:500]}...")
            # Log fence pattern matches for debugging
            fence_matches = list(self.TOOL_FENCE_RE.finditer(text))
            self.logger.error(f"❌ FENCE MATCHES: {len(fence_matches)}")
            for i, match in enumerate(fence_matches[:3]):  # First 3 matches
                self.logger.error(f"❌ FENCE MATCH {i+1}: {match.group()[:200]}...")

        self.logger.info(f"🔍 PARSER EXIT: Returning {len(validated_calls)} valid calls")
        return validated_calls

    def _extract_from_fences(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from code fence blocks with detailed debugging"""
        calls = []

        # Log the regex pattern being used
        self.logger.info(f"🔍 FENCE: Using pattern: {self.TOOL_FENCE_RE.pattern}")

        # Find all matches
        matches = list(self.TOOL_FENCE_RE.finditer(text))
        self.logger.info(f"🔍 FENCE: Found {len(matches)} fence matches")

        for i, match in enumerate(matches):
            self.logger.info(f"🔍 FENCE MATCH {i+1}: Full match: {match.group()[:100]}...")

            json_text = match.group(1).strip()
            self.logger.info(f"🔍 FENCE MATCH {i+1}: Extracted JSON: {json_text[:200]}...")

            parsed = self._parse_json_safely(json_text)
            if parsed:
                calls.append(parsed)
                self.logger.info(f"✅ FENCE MATCH {i+1}: Successfully parsed - tool: {parsed.get('tool_name', 'unknown')}")
            else:
                self.logger.warning(f"❌ FENCE MATCH {i+1}: JSON parse failed")

        self.logger.info(f"🔍 FENCE FINAL: Returning {len(calls)} valid fence calls")
        return calls

    def _extract_from_tags(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from XML-style tags"""
        calls = []
        for match in self.TOOL_TAG_RE.finditer(text):
            json_text = match.group(1).strip()
            parsed = self._parse_json_safely(json_text)
            if parsed:
                calls.append(parsed)
                self.logger.debug(f"Found tool call in XML tag: {parsed.get('tool_name', 'unknown')}")
        return calls

    def _extract_from_json_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from bare JSON blocks"""
        calls = []
        for match in self.JSON_BLOCK_RE.finditer(text):
            json_text = match.group(0).strip()
            parsed = self._parse_json_safely(json_text)
            if parsed and self._looks_like_tool_call(parsed):
                calls.append(parsed)
                self.logger.debug(f"Found tool call in JSON block: {parsed.get('tool_name', 'unknown')}")
        return calls

    def _parse_json_safely(self, json_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON text with error handling and detailed debugging"""
        if not json_text:
            self.logger.warning("⚠️ JSON PARSE: Empty JSON text")
            return None

        self.logger.info(f"🔍 JSON PARSE: Input length: {len(json_text)}")
        self.logger.info(f"🔍 JSON PARSE: Raw text: {json_text[:300]}...")

        try:
            # Clean up common JSON issues
            cleaned = self._clean_json_text(json_text)
            self.logger.info(f"🔍 JSON PARSE: Cleaned text: {cleaned[:300]}...")

            result = json.loads(cleaned)
            self.logger.info(f"✅ JSON PARSE: Successfully parsed - keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON PARSE: Failed - {e}")
            self.logger.error(f"❌ JSON PARSE: Failed text: {cleaned[:200]}...")
            self.logger.error(f"❌ JSON PARSE: Error position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
            return None

    def _clean_json_text(self, text: str) -> str:
        """Clean up common JSON formatting issues"""
        # Replace smart quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # Remove trailing commas before closing braces/brackets
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Remove trailing dots/ellipsis after the JSON object
        text = re.sub(r'}[\s.]*$', '}', text)

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

    def _extract_with_ast_parsing(self, text: str) -> List[Dict[str, Any]]:
        """More robust JSON extraction using character-by-character parsing"""
        calls = []

        # Look for JSON-like structures starting with '{'
        brace_count = 0
        json_start = None
        i = 0

        self.logger.info(f"🔍 AST: Scanning {len(text)} characters for JSON structures")

        while i < len(text):
            char = text[i]

            if char == '{':
                if brace_count == 0:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start is not None:
                    # Found a complete JSON object
                    json_text = text[json_start:i+1]
                    self.logger.info(f"🔍 AST: Found JSON candidate at {json_start}-{i}: {json_text[:100]}...")

                    # Try to parse it
                    parsed = self._parse_json_safely(json_text)
                    if parsed and self._looks_like_tool_call(parsed):
                        calls.append(parsed)
                        self.logger.info(f"✅ AST: Valid tool call found - {parsed.get('tool_name', 'unknown')}")

                    json_start = None

            i += 1

        self.logger.info(f"🔍 AST: Found {len(calls)} valid tool calls")
        return calls

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

        # Normalize to standard format
        if 'args' in call and 'arguments' not in call:
            call['arguments'] = call.pop('args')
        if 'parameters' in call and 'arguments' not in call:
            call['arguments'] = call.pop('parameters')

        return True