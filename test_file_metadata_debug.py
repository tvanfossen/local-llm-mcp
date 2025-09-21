#!/usr/bin/env python3
"""Debug test for file_metadata tool"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp.tools.file_metadata.file_metadata import file_metadata_tool


async def test_file_metadata():
    """Test file_metadata tool directly"""
    print("🧪 Testing file_metadata tool...")

    test_xml = """
<python_file id="pf_001" filepath="src/test_user.py">
    <metadata>
        <created>2024-01-01T00:00:00Z</created>
        <agent_id>test_agent</agent_id>
        <version>1.0.0</version>
        <description>Test file</description>
    </metadata>
    <classes>
        <class id="cls_001" name="TestUser">
            <docstring>Test class</docstring>
        </class>
    </classes>
</python_file>
"""

    # Test create
    print("Testing create action...")
    result = await file_metadata_tool({
        "action": "create",
        "path": "src/test_user.py",
        "xml_content": test_xml
    })

    print(f"Create result: {result}")

    # Test read
    print("Testing read action...")
    result = await file_metadata_tool({
        "action": "read",
        "path": "src/test_user.py"
    })

    print(f"Read result: {result}")


if __name__ == "__main__":
    asyncio.run(test_file_metadata())