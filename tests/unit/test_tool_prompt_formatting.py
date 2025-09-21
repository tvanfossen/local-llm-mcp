#!/usr/bin/env python3
"""Test Tool Prompt Formatting

Tests that tool descriptions are loaded from prompt files
instead of being hardcoded.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.mcp.bridge.formatter import ToolPromptFormatter


class TestToolPromptFormatting:
    """Test tool prompt formatting with prompt files"""

    def test_tool_description_loaded_from_prompts(self):
        """Test that tool descriptions are loaded from prompt files"""

        # Mock tools with minimal schema
        tools = [
            {
                "name": "file_metadata",
                "description": "Hardcoded description",  # Should be ignored
                "inputSchema": {"properties": {}, "required": []}
            },
            {
                "name": "workspace",
                "description": "Another hardcoded description",  # Should be ignored
                "inputSchema": {"properties": {}, "required": []}
            }
        ]

        formatter = ToolPromptFormatter(tools, use_xml=True)
        prompt = formatter.get_tools_prompt()

        # Should contain content from prompt files, not hardcoded descriptions
        assert "Create and manage XML metadata files" in prompt, "Should load file_metadata prompt"
        assert "Comprehensive file and directory operations" in prompt, "Should load workspace prompt"

        # Should NOT contain hardcoded descriptions
        assert "Hardcoded description" not in prompt, "Should not use hardcoded descriptions"
        assert "Another hardcoded description" not in prompt, "Should not use hardcoded descriptions"

    def test_fallback_to_hardcoded_for_unknown_tool(self):
        """Test fallback to hardcoded description for tools without prompt files"""

        tools = [
            {
                "name": "unknown_tool",
                "description": "Fallback description",
                "inputSchema": {"properties": {}, "required": []}
            }
        ]

        formatter = ToolPromptFormatter(tools, use_xml=True)
        prompt = formatter.get_tools_prompt()

        # Should use fallback description for unknown tools
        assert "Fallback description" in prompt

    def test_all_core_tools_have_prompts(self):
        """Test that all core tools have corresponding prompt files"""

        core_tools = ["file_metadata", "workspace", "validation", "git_operations"]
        prompts_dir = Path(__file__).parent.parent.parent / "prompts" / "tools"

        for tool_name in core_tools:
            prompt_file = prompts_dir / f"{tool_name}.txt"
            assert prompt_file.exists(), f"Prompt file missing for {tool_name}"

            # Verify file has content
            content = prompt_file.read_text().strip()
            assert len(content) > 0, f"Prompt file empty for {tool_name}"
            assert tool_name in content, f"Tool name should appear in prompt for {tool_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])