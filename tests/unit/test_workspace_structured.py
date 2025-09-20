"""Unit tests for structured XML generation in workspace tool"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.mcp.tools.workspace.workspace import _write_structured_file


@pytest.mark.unit
class TestWorkspaceStructured:
    """Test structured XML generation functionality"""

    def setup_method(self):
        """Setup test workspace"""
        self.test_workspace = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup test workspace"""
        if self.test_workspace.exists():
            shutil.rmtree(self.test_workspace)

    @pytest.mark.asyncio
    async def test_write_structured_file_basic(self):
        """Test basic structured file writing"""
        structured_content = """<python_file id="pf_001" filepath="test.py">
    <metadata>
        <created>2024-01-01T00:00:00Z</created>
        <agent_id>test_agent</agent_id>
        <version>1.0.0</version>
        <description>Test file</description>
    </metadata>
    <imports>
        <import id="imp_001" module="typing" items="List, Dict"/>
    </imports>
    <constants>
        <constant id="const_001" name="TEST_VALUE" type="str" value="'hello'"/>
    </constants>
    <functions>
        <function id="func_001" name="test_function">
            <parameters>
                <parameter name="value" type="str"/>
            </parameters>
            <returns type="str" description="Processed value"/>
            <body>return value.upper()</body>
        </function>
    </functions>
    <classes>
        <class id="cls_001" name="TestClass">
            <docstring>A test class</docstring>
            <init_method id="init_001">
                <parameters>
                    <parameter name="self"/>
                    <parameter name="name" type="str"/>
                </parameters>
                <body>self.name = name</body>
            </init_method>
            <methods>
                <method id="mth_001" name="get_name">
                    <parameters>
                        <parameter name="self"/>
                    </parameters>
                    <returns type="str" description="The name"/>
                    <body>return self.name</body>
                </method>
            </methods>
        </class>
    </classes>
</python_file>"""

        arguments = {
            "path": "test_structured.py",
            "structured_content": structured_content
        }

        result = await _write_structured_file(arguments, self.test_workspace)

        # Debug: print the result to see what we get
        print(f"Result: {result}")

        # Verify the result (MCP format uses isError: False for success)
        assert "isError" in result, f"Expected 'isError' key in result: {result}"
        assert result["isError"] is False
        assert "content" in result
        assert len(result["content"]) > 0
        text_content = result["content"][0]["text"]
        assert "Successfully created structured file" in text_content

        # Verify the Python file was created
        python_file = self.test_workspace / "test_structured.py"
        assert python_file.exists()

        # Verify the metadata file was created
        meta_file = self.test_workspace / ".meta" / "test_structured.py.xml"
        assert meta_file.exists()

        # Check the content of the generated Python file
        content = python_file.read_text()
        assert "from typing import List, Dict" in content
        assert "TEST_VALUE = 'hello'" in content
        assert "def test_function(value: str) -> str:" in content
        assert "class TestClass:" in content
        assert "def __init__(self, name: str):" in content
        assert "def get_name(self) -> str:" in content

        # Check the metadata file contains the XML
        meta_content = meta_file.read_text()
        assert "<python_file" in meta_content
        assert "test_agent" in meta_content

    @pytest.mark.asyncio
    async def test_write_structured_file_invalid_xml(self):
        """Test handling of invalid XML"""
        invalid_xml = "<invalid>missing closing tag"

        arguments = {
            "path": "test_invalid.py",
            "structured_content": invalid_xml
        }

        result = await _write_structured_file(arguments, self.test_workspace)

        # Verify the result shows failure
        assert result["isError"] is True
        text_content = result["content"][0]["text"]
        assert "XML parsing error" in text_content

    @pytest.mark.asyncio
    async def test_write_structured_file_missing_content(self):
        """Test handling of missing structured content"""
        arguments = {
            "path": "test_missing.py"
            # Missing structured_content
        }

        result = await _write_structured_file(arguments, self.test_workspace)

        # Verify the result shows failure
        assert result["isError"] is True
        text_content = result["content"][0]["text"]
        assert "Missing 'structured_content'" in text_content

    @pytest.mark.asyncio
    async def test_write_structured_file_minimal(self):
        """Test with minimal valid XML structure"""
        minimal_xml = """<python_file id="pf_001" filepath="minimal.py">
    <metadata>
        <created>2024-01-01T00:00:00Z</created>
        <agent_id>test</agent_id>
        <version>1.0.0</version>
        <description>Minimal test</description>
    </metadata>
</python_file>"""

        arguments = {
            "path": "minimal.py",
            "structured_content": minimal_xml
        }

        result = await _write_structured_file(arguments, self.test_workspace)

        # Verify success
        assert result["isError"] is False

        # Verify minimal Python file was created
        python_file = self.test_workspace / "minimal.py"
        assert python_file.exists()

        content = python_file.read_text()
        assert '"""Generated Python file from structured XML metadata"""' in content