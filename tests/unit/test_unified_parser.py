"""Unit tests for UnifiedToolCallParser"""

import pytest
from src.core.mcp.bridge.unified_parser import (
    UnifiedToolCallParser,
    ParsingStrategy,
    ParseResult
)


@pytest.mark.unit
class TestUnifiedToolCallParser:
    """Test the unified tool call parser"""

    def test_parser_creation(self):
        """Test parser can be created with different strategies"""
        parser_xml = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)
        assert parser_xml.strategy == ParsingStrategy.XML_PRIMARY

        parser_json = UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)
        assert parser_json.strategy == ParsingStrategy.JSON_PRIMARY

    def test_xml_parsing(self, sample_prompts):
        """Test XML tool call parsing"""
        parser = UnifiedToolCallParser(ParsingStrategy.XML_ONLY)

        xml_text = sample_prompts["xml_tool_call"]
        result = parser.parse(xml_text)

        assert result.success
        assert len(result.tool_calls) == 1
        assert result.strategy_used == "xml"

        call = result.tool_calls[0]
        assert call["tool_name"] == "workspace"
        assert call["arguments"]["action"] == "write"
        assert call["arguments"]["path"] == "test.py"
        assert "Hello World" in call["arguments"]["content"]

    def test_json_parsing(self, sample_prompts):
        """Test JSON tool call parsing"""
        parser = UnifiedToolCallParser(ParsingStrategy.JSON_ONLY)

        json_text = sample_prompts["json_tool_call"]
        result = parser.parse(json_text)

        assert result.success
        assert len(result.tool_calls) == 1
        assert result.strategy_used == "json"

        call = result.tool_calls[0]
        assert call["tool_name"] == "workspace"
        assert call["arguments"]["action"] == "write"
        assert call["arguments"]["path"] == "test.py"

    def test_xml_primary_fallback(self, sample_prompts):
        """Test XML primary with JSON fallback"""
        parser = UnifiedToolCallParser(ParsingStrategy.XML_PRIMARY)

        # Should parse JSON when XML fails
        json_text = sample_prompts["json_tool_call"]
        result = parser.parse(json_text)

        assert result.success
        assert len(result.tool_calls) == 1
        # Should indicate it fell back to JSON
        assert result.strategy_used in ["json", "both_failed"]

    def test_json_primary_fallback(self, sample_prompts):
        """Test JSON primary with XML fallback"""
        parser = UnifiedToolCallParser(ParsingStrategy.JSON_PRIMARY)

        # Should parse XML when JSON fails
        xml_text = sample_prompts["xml_tool_call"]
        result = parser.parse(xml_text)

        assert result.success
        assert len(result.tool_calls) == 1
        # Should indicate it fell back to XML
        assert result.strategy_used in ["xml", "both_failed"]

    def test_empty_input(self):
        """Test handling of empty input"""
        parser = UnifiedToolCallParser()

        result = parser.parse("")
        assert not result.success
        assert len(result.tool_calls) == 0
        assert result.strategy_used == "empty_input"

    def test_invalid_input(self):
        """Test handling of invalid input"""
        parser = UnifiedToolCallParser()

        result = parser.parse("This is just plain text with no tool calls")
        assert not result.success
        assert len(result.tool_calls) == 0

    def test_malformed_xml(self):
        """Test handling of malformed XML"""
        parser = UnifiedToolCallParser(ParsingStrategy.XML_ONLY)

        malformed_xml = """```xml
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>write</action>
        <!-- Missing closing tags -->
    </arguments>
```"""

        result = parser.parse(malformed_xml)
        assert not result.success
        assert len(result.errors) > 0

    def test_malformed_json(self):
        """Test handling of malformed JSON"""
        parser = UnifiedToolCallParser(ParsingStrategy.JSON_ONLY)

        malformed_json = """```json
{
    "tool_name": "workspace",
    "arguments": {
        "action": "write",
        "missing_quote: "value"
    }
}
```"""

        result = parser.parse(malformed_json)
        assert not result.success
        assert len(result.errors) > 0

    def test_multiple_tool_calls_xml(self):
        """Test parsing multiple XML tool calls"""
        parser = UnifiedToolCallParser(ParsingStrategy.XML_ONLY)

        multiple_xml = """```xml
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>write</action>
        <path>file1.py</path>
        <content>print("file1")</content>
    </arguments>
</tool_call>
```

```xml
<tool_call>
    <tool_name>validation</tool_name>
    <arguments>
        <operation>file-length</operation>
        <path>file1.py</path>
    </arguments>
</tool_call>
```"""

        result = parser.parse(multiple_xml)
        assert result.success
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["tool_name"] == "workspace"
        assert result.tool_calls[1]["tool_name"] == "validation"

    def test_parse_result_properties(self):
        """Test ParseResult properties"""
        # Test successful result
        successful_result = ParseResult([{"tool_name": "test"}], "xml")
        assert len(successful_result) == 1
        assert bool(successful_result) == True
        assert successful_result.success == True

        # Test failed result
        failed_result = ParseResult([], "xml", ["error"])
        assert len(failed_result) == 0
        assert bool(failed_result) == False
        assert failed_result.success == False
        assert len(failed_result.errors) == 1