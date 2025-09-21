#!/usr/bin/env python3
"""Test jinja2 template generation with board.py metadata"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.mcp.tools.workspace.workspace import workspace_tool


class TestJinja2BoardGeneration:
    """Test jinja2 template generation with BoardManager metadata"""

    @pytest.mark.asyncio
    async def test_board_generation_from_metadata(self):
        """Test generating board.py from metadata using jinja2 templates"""

        print("🧪 Testing jinja2 template generation with BoardManager...")

        # Test the generate_from_metadata action
        result = await workspace_tool({
            "action": "generate_from_metadata",
            "path": "core/board.py"
        })

        print(f"Generation result: {result}")

        # Should succeed
        assert result.get("success") is True, f"Generation failed: {result}"

        # Check if the file was created
        workspace_path = Path("/home/tvanfossen/Projects/PyChess")
        generated_file = workspace_path / "core/board.py"

        assert generated_file.exists(), f"File not generated: {generated_file}"

        # Read and validate the generated content
        with open(generated_file, 'r') as f:
            content = f.read()

        print("\n📄 Generated content:")
        print("=" * 50)
        print(content)
        print("=" * 50)

        # Validate essential content
        assert "class BoardManager:" in content, "Should contain BoardManager class"
        assert "def initialize_board" in content, "Should contain initialize_board method"
        assert "def get_cell" in content, "Should contain get_cell method"
        assert "def set_cell" in content, "Should contain set_cell method"
        assert "def is_valid_position" in content, "Should contain is_valid_position method"
        assert "def clear_board" in content, "Should contain clear_board method"
        assert "from typing import List" in content, "Should contain proper imports"

        # Validate jinja2 template formatting worked correctly
        assert "self.board: List[List[str]] = []" in content, "Should have proper type hints"
        assert "def __init__(self):" in content, "Should have proper __init__ method"

        # Check that method bodies don't contain template artifacts
        assert "{{" not in content, "Should not contain template syntax artifacts"
        assert "}}" not in content, "Should not contain template syntax artifacts"
        assert "DEFAULT_VALUE" not in content, "Should resolve template variables"

    @pytest.mark.asyncio
    async def test_metadata_file_exists(self):
        """Verify the metadata file exists for testing"""

        metadata_path = Path("/home/tvanfossen/Projects/PyChess/.meta/core/board.py.xml")
        assert metadata_path.exists(), f"Metadata file missing: {metadata_path}"

        # Verify metadata content
        with open(metadata_path, 'r') as f:
            metadata_content = f.read()

        assert "BoardManager" in metadata_content, "Metadata should contain BoardManager class"
        assert "initialize_board" in metadata_content, "Metadata should contain method definitions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])