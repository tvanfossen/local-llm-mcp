"""PyTest configuration and fixtures for local-llm-mcp tests"""

import os
import sys
import pytest
from pathlib import Path

# Add src to Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Test fixtures and configurations
@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory"""
    return Path(__file__).parent.parent

@pytest.fixture(scope="session")
def test_workspace(tmp_path_factory):
    """Create a temporary workspace for tests"""
    workspace = tmp_path_factory.mktemp("test_workspace")
    # Set environment variable so tools use this workspace
    os.environ["WORKSPACE_ROOT"] = str(workspace)
    return workspace

@pytest.fixture
def sample_prompts():
    """Sample prompts for testing"""
    return {
        "code_generation": """You are a code generation agent. You MUST use MCP tools to complete this task.

Context: {context}
Target File: {filename}
Request: {request}

You MUST follow this exact sequence:
1. First, use the 'workspace' tool with action='write' to create {filename}
2. Then, use the 'validation' tool with operation='file-length' to validate the file
3. Finally, use the 'git_operations' tool with operation='status' to check git status

Start by calling the workspace tool to write the file:""",

        "xml_tool_call": """```xml
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>write</action>
        <path>test.py</path>
        <content>def hello():
    print("Hello World!")
    return True</content>
    </arguments>
</tool_call>
```""",

        "json_tool_call": """```json
{
    "tool_name": "workspace",
    "arguments": {
        "action": "write",
        "path": "test.py",
        "content": "def hello():\\n    print('Hello World!')\\n    return True"
    }
}
```"""
    }

@pytest.fixture
def mock_llm_responses():
    """Mock LLM responses for testing"""
    return {
        "xml_response": """I'll create a simple test function for you.

```xml
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>write</action>
        <path>test_function.py</path>
        <content>def test_function():
    \"\"\"A simple test function\"\"\"
    result = 2 + 2
    assert result == 4
    return result

if __name__ == "__main__":
    test_function()
    print("Test passed!")
</content>
    </arguments>
</tool_call>
```""",

        "json_response": """I'll create a simple test function for you.

```json
{
    "tool_name": "workspace",
    "arguments": {
        "action": "write",
        "path": "test_function.py",
        "content": "def test_function():\\n    \\\"\\\"\\\"A simple test function\\\"\\\"\\\"\\n    result = 2 + 2\\n    assert result == 4\\n    return result\\n\\nif __name__ == \\\"__main__\\\":\\n    test_function()\\n    print(\\\"Test passed!\\\")"
    }
}
```""",

        "structured_xml_response": """I'll create a comprehensive class with proper structure.

```xml
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>write_structured</action>
        <path>example_class.py</path>
        <structured_content>
            <python_file id="pf_001" filepath="example_class.py">
                <metadata>
                    <created>2024-01-01T00:00:00Z</created>
                    <agent_id>test_agent</agent_id>
                    <version>1.0.0</version>
                    <description>Example class for testing</description>
                </metadata>
                <imports>
                    <import id="imp_001" module="typing" items="List, Optional"/>
                </imports>
                <classes>
                    <class id="cls_001" name="ExampleClass">
                        <docstring>Example class for demonstration</docstring>
                        <init_method id="init_001">
                            <parameters>
                                <parameter name="self"/>
                                <parameter name="value" type="str" default="'default'"/>
                            </parameters>
                            <body>self.value = value</body>
                        </init_method>
                        <methods>
                            <method id="mth_001" name="get_value">
                                <parameters>
                                    <parameter name="self"/>
                                </parameters>
                                <returns type="str" description="The current value"/>
                                <body>return self.value</body>
                            </method>
                        </methods>
                    </class>
                </classes>
            </python_file>
        </structured_content>
    </arguments>
</tool_call>
```"""
    }

@pytest.fixture
def available_tools():
    """Standard set of tools for testing"""
    return [
        {
            "name": "workspace",
            "description": "Workspace operations (read, write, delete, list)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                }
            }
        },
        {
            "name": "validation",
            "description": "Validation operations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "path": {"type": "string"}
                }
            }
        },
        {
            "name": "git_operations",
            "description": "Git operations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"}
                }
            }
        }
    ]

# Test markers for organization
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as requiring actual LLM"
    )
    config.addinivalue_line(
        "markers", "server: mark test as requiring running server"
    )