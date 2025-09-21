#!/usr/bin/env python3
"""Test Bridge Async Tool Call Queueing

Tests that the MCP bridge queues tool calls without blocking,
allowing the async task queue to process them independently.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.mcp.bridge.bridge import MCPBridge
from src.core.mcp.bridge.unified_parser import UnifiedToolCallParser
from src.core.mcp.bridge.formatter import ToolPromptFormatter
from src.core.tasks.queue.task import ToolCallTask


class TestBridgeAsyncQueueing:
    """Test async tool call queueing behavior"""

    @pytest.fixture
    def mock_task_queue(self):
        """Mock task queue"""
        mock_queue = Mock()
        mock_queue.queue_task.return_value = "test_task_id_123"
        return mock_queue

    @pytest.fixture
    def mock_tool_executor(self):
        """Mock tool executor"""
        return Mock()

    @pytest.fixture
    def bridge(self, mock_task_queue, mock_tool_executor):
        """Create bridge instance with mocked dependencies"""
        available_tools = [
            {"name": "file_metadata"},
            {"name": "workspace"},
            {"name": "validation"},
            {"name": "git_operations"}
        ]
        bridge = MCPBridge(
            task_queue=mock_task_queue,
            tool_executor=mock_tool_executor,
            available_tools=available_tools,
            use_xml=True
        )
        return bridge

    @pytest.mark.asyncio
    async def test_tool_call_queued_returns_immediately(self, bridge, mock_task_queue):
        """Test that _execute_tool_call_queued returns immediately without blocking"""

        # Record start time
        start_time = asyncio.get_event_loop().time()

        # Execute tool call
        result = await bridge._execute_tool_call_queued(
            tool_name="file_metadata",
            arguments={"action": "create", "path": "test.py", "xml_content": "<test/>"}
        )

        # Record end time
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        # Should return immediately (less than 100ms)
        assert execution_time < 0.1, f"Tool call took {execution_time}s, should be immediate"

        # Should return success with queued status
        assert result["success"] is True
        assert result["queued"] is True
        assert result["tool_name"] == "file_metadata"
        assert result["task_id"] == "test_task_id_123"
        assert "queued successfully" in result["message"]

        # Should have queued the task
        mock_task_queue.queue_task.assert_called_once()

        # Verify the queued task is a ToolCallTask
        queued_task = mock_task_queue.queue_task.call_args[0][0]
        assert isinstance(queued_task, ToolCallTask)
        assert queued_task.tool_name == "file_metadata"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_queue_independently(self, bridge, mock_task_queue):
        """Test that multiple tool calls can be queued without blocking each other"""

        # Queue multiple task IDs
        mock_task_queue.queue_task.side_effect = [
            "task_1", "task_2", "task_3", "task_4", "task_5"
        ]

        start_time = asyncio.get_event_loop().time()

        # Queue 5 tool calls concurrently
        tasks = [
            bridge._execute_tool_call_queued(f"tool_{i}", {"action": "test"})
            for i in range(1, 6)
        ]

        results = await asyncio.gather(*tasks)

        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time

        # All 5 calls should complete quickly (less than 500ms total)
        assert total_time < 0.5, f"5 tool calls took {total_time}s, should be immediate"

        # All should succeed and be queued
        for i, result in enumerate(results):
            assert result["success"] is True
            assert result["queued"] is True
            assert result["tool_name"] == f"tool_{i+1}"
            assert result["task_id"] == f"task_{i+1}"

        # Should have queued 5 tasks
        assert mock_task_queue.queue_task.call_count == 5

    @pytest.mark.asyncio
    async def test_process_model_output_with_multiple_tool_calls(self, bridge, mock_task_queue):
        """Test processing model output with multiple tool calls queues all independently"""

        # Mock task IDs
        mock_task_queue.queue_task.side_effect = ["task_1", "task_2"]

        # Model output with 2 tool calls
        model_output = '''<tool_call>
    <tool_name>file_metadata</tool_name>
    <arguments>
        <action>create</action>
        <path>test1.py</path>
        <xml_content><![CDATA[<test/>]]></xml_content>
    </arguments>
</tool_call>
<tool_call>
    <tool_name>workspace</tool_name>
    <arguments>
        <action>generate_from_metadata</action>
        <path>test1.py</path>
    </arguments>
</tool_call>'''

        start_time = asyncio.get_event_loop().time()

        # Process model output
        result = await bridge.process_model_output(model_output)

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        # Should complete quickly
        assert execution_time < 1.0, f"Processing took {execution_time}s, should be fast"

        # Should detect tool calls
        assert result["type"] == "tool_calls"
        assert len(result["tool_calls"]) == 2

        # Both tool calls should be queued
        assert mock_task_queue.queue_task.call_count == 2

        # Results should indicate queued status
        for tool_result in result["results"]:
            assert tool_result["success"] is True
            assert tool_result["queued"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])