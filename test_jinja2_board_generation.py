#!/usr/bin/env python3
"""Test jinja2 template generation with board.py metadata"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp.tools.workspace.workspace import workspace_tool


def test_board_generation():
    """Test generating board.py from metadata using jinja2 templates"""

    print("🧪 Testing jinja2 template generation with BoardManager...")

    # Test the generate_from_metadata action
    result = workspace_tool({
        "action": "generate_from_metadata",
        "path": "core/board.py"
    })

    print(f"Generation result: {result}")

    # Check if the file was created
    workspace_path = Path("/home/tvanfossen/Projects/PyChess")
    generated_file = workspace_path / "core/board.py"

    if generated_file.exists():
        print(f"✅ File generated successfully: {generated_file}")

        # Read and display the generated content
        with open(generated_file, 'r') as f:
            content = f.read()

        print("\n📄 Generated content:")
        print("=" * 50)
        print(content)
        print("=" * 50)

        # Validate content
        assert "class BoardManager:" in content, "Should contain BoardManager class"
        assert "def initialize_board" in content, "Should contain initialize_board method"
        assert "def get_cell" in content, "Should contain get_cell method"
        assert "def set_cell" in content, "Should contain set_cell method"
        assert "def is_valid_position" in content, "Should contain is_valid_position method"
        assert "def clear_board" in content, "Should contain clear_board method"
        assert "from typing import List" in content, "Should contain proper imports"

        print("✅ All validation checks passed!")

    else:
        print(f"❌ File not generated: {generated_file}")
        print("❌ Template generation failed")


if __name__ == "__main__":
    test_board_generation()