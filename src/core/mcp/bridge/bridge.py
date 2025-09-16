"""MCP Bridge for Local Model Tool Calling

Main bridge implementation that handles tool call extraction,
validation, and execution routing for local LLM interactions.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .formatter import ToolCallFormatter
from .tool_parser import ToolCallParser

logger = logging.getLogger(__name__)


class MCPBridge:
    """Bridge between local LLM and MCP tools"""

    def __init__(self, task_queue=None, tool_executor=None):
        self.parser = ToolCallParser()
        self.formatter = ToolCallFormatter()
        self.task_queue = task_queue
        self.tool_executor = tool_executor
        self.max_retries = 3
        self.retry_delay = 1.0

    def get_tools_prompt(self) -> str:
        """Get formatted tools prompt for the model"""
        return self.formatter.format_all_tools_for_qwen()

    async def process_model_output(self, text: str) -> Dict[str, Any]:
        """Process model output and execute any tool calls found"""
        # Parse tool calls from output
        tool_calls = self.parser.parse_tool_calls(text)

        if not tool_calls:
            return {
                "type": "text",
                "content": text,
                "tool_calls": []
            }

        # Execute tool calls
        results = []
        for call in tool_calls:
            result = await self._execute_tool_call(call)
            results.append(result)

        return {
            "type": "tool_calls",
            "content": text,
            "tool_calls": tool_calls,
            "results": results
        }

    async def _execute_tool_call(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool call with validation and retry logic"""
        tool_name = call.get("tool_name") or call.get("function_name")
        arguments = call.get("arguments", {})

        if not tool_name:
            return {
                "success": False,
                "error": "No tool name specified in call",
                "call": call
            }

        # Validate tool call
        if not self.formatter.validate_tool_call(tool_name, arguments):
            return {
                "success": False,
                "error": f"Invalid arguments for tool {tool_name}",
                "call": call
            }

        # Execute with retry logic
        for attempt in range(self.max_retries):
            try:
                if self.task_queue:
                    # Route through task queue
                    result = await self._execute_via_queue(tool_name, arguments)
                else:
                    # Direct execution
                    result = await self._execute_direct(tool_name, arguments)

                # Format result for model consumption
                return self.formatter.format_tool_result(tool_name, result)

            except Exception as e:
                logger.warning(f"Tool execution attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return {
                        "success": False,
                        "error": f"Tool execution failed after {self.max_retries} attempts: {str(e)}",
                        "call": call
                    }

    async def _execute_via_queue(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call via task queue"""
        from src.core.tasks.queue import ToolCallTask

        # Create tool call task
        task = ToolCallTask.create(
            tool_name=tool_name,
            tool_args=arguments,
            priority=1  # High priority for tool calls
        )

        # Queue and wait for completion
        task_id = self.task_queue.queue_task(task)

        # Poll for completion (in production, use proper async notification)
        max_wait = 30  # 30 second timeout
        wait_interval = 0.1
        elapsed = 0

        while elapsed < max_wait:
            task_status = self.task_queue.get_task_status(task_id)
            if not task_status:
                raise RuntimeError(f"Task {task_id} not found")

            if task_status["status"] == "completed":
                result = self.task_queue.get_task_result(task_id)
                return result or {"success": True, "content": "Task completed"}

            elif task_status["status"] == "failed":
                error = task_status.get("error", "Unknown error")
                raise RuntimeError(f"Tool execution failed: {error}")

            await asyncio.sleep(wait_interval)
            elapsed += wait_interval

        raise TimeoutError(f"Tool execution timed out after {max_wait} seconds")

    async def _execute_direct(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call directly via tool executor"""
        if not self.tool_executor:
            raise RuntimeError("No tool executor available for direct execution")

        return await self.tool_executor.execute_tool(tool_name, arguments)

    def create_completion_message(self, results: List[Dict[str, Any]]) -> str:
        """Create a message to guide model toward task completion"""
        if not results:
            return "Continue with your task or let me know if you need to use any tools."

        successful_tools = [r for r in results if r.get("success")]
        failed_tools = [r for r in results if not r.get("success")]

        message_parts = []

        if successful_tools:
            message_parts.append("Successfully executed tools:")
            for result in successful_tools:
                tool_name = result.get("tool_name", "unknown")
                message_parts.append(f"  ✅ {tool_name}")

        if failed_tools:
            message_parts.append("Failed tool executions:")
            for result in failed_tools:
                tool_name = result.get("tool_name", "unknown")
                error = result.get("error", "Unknown error")
                message_parts.append(f"  ❌ {tool_name}: {error}")

        message_parts.append("\nBased on these results, please continue with your task or use additional tools if needed.")

        return "\n".join(message_parts)

    def should_continue_generation(self, results: List[Dict[str, Any]]) -> bool:
        """Determine if model should continue generating after tool execution"""
        # Continue if any tools failed (for self-correction)
        if any(not r.get("success") for r in results):
            return True

        # Continue if validation tools found issues
        for result in results:
            if result.get("tool_name") == "validation" and not result.get("success"):
                return True

        # Stop after successful git commit (workflow complete)
        if any(r.get("tool_name") == "git_operations" and r.get("success") for r in results):
            return False

        # Default: continue generation
        return True