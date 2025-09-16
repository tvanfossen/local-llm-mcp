"""MCP Bridge for Local Model Tool Calling"""

import json
import logging
from typing import Dict, List, Any, Optional
import asyncio

from .parser import ToolCallParser
from .formatter import ToolPromptFormatter

logger = logging.getLogger(__name__)

class MCPBridge:
    """Bridge between local model and MCP tools"""

    def __init__(self, task_queue=None, tool_executor=None, available_tools: List[Dict] = None):
        self.task_queue = task_queue
        self.tool_executor = tool_executor
        self.available_tools = available_tools or []

        self.parser = ToolCallParser()
        self.formatter = ToolPromptFormatter(self.available_tools)

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"MCPBridge initialized with {len(self.available_tools)} tools")

    def get_tools_prompt(self) -> str:
        """Get formatted tools prompt for model"""
        self.logger.debug("ENTRY get_tools_prompt")
        prompt = self.formatter.get_tools_prompt()
        self.logger.debug(f"EXIT get_tools_prompt: {len(prompt)} characters")
        return prompt

    async def process_model_output(self, model_output: str, parent_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Parse model output and execute tool calls"""
        self.logger.debug(f"ENTRY process_model_output: {len(model_output)} characters")

        try:
            # Extract tool calls from model output
            tool_calls = self.parser.extract_tool_calls(model_output)

            if not tool_calls:
                self.logger.info("No tool calls detected in model output")
                return {
                    "type": "text",
                    "content": model_output,
                    "tool_calls": []
                }

            self.logger.info(f"Found {len(tool_calls)} tool calls")

            # Validate and execute tool calls
            results = []
            for i, tool_call in enumerate(tool_calls):
                self.logger.info(f"Processing tool call {i+1}: {tool_call}")

                # Validate tool call
                is_valid, validation_error = self.formatter.validate_tool_call(tool_call)
                if not is_valid:
                    self.logger.error(f"Invalid tool call: {validation_error}")
                    results.append({
                        "success": False,
                        "error": validation_error,
                        "tool_call": tool_call
                    })
                    continue

                # Execute tool call
                try:
                    result = await self._execute_tool_call(tool_call, parent_task_id)
                    results.append(result)
                    self.logger.info(f"Tool call {i+1} executed: {result.get('success', False)}")
                except Exception as e:
                    self.logger.exception(f"Error executing tool call {i+1}: {e}")
                    results.append({
                        "success": False,
                        "error": str(e),
                        "tool_call": tool_call
                    })

            self.logger.debug(f"EXIT process_model_output: {len(results)} results")
            return {
                "type": "tool_calls",
                "content": model_output,
                "tool_calls": tool_calls,
                "results": results
            }

        except Exception as e:
            self.logger.exception(f"Error processing model output: {e}")
            return {
                "type": "error",
                "content": model_output,
                "error": str(e)
            }

    async def _execute_tool_call(self, tool_call: Dict[str, Any], parent_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a single tool call - via queue if available, otherwise direct"""
        tool_name = tool_call.get('tool_name') or tool_call.get('name')
        arguments = tool_call.get('arguments', {})

        self.logger.debug(f"ENTRY _execute_tool_call: {tool_name} with {arguments}")

        if not self.tool_executor:
            error = "No tool executor available"
            self.logger.error(f"EXIT _execute_tool_call: FAILED - {error}")
            return {
                "success": False,
                "error": error,
                "tool_name": tool_name
            }

        try:
            # Use task queue if available (preferred for depth limiting)
            if self.task_queue:
                return await self._execute_tool_call_queued(tool_name, arguments, parent_task_id)
            else:
                # Fall back to direct execution
                return await self._execute_tool_call_direct(tool_name, arguments)

        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": tool_name
            }
            self.logger.exception(f"EXIT _execute_tool_call: EXCEPTION - {e}")
            return error_result

    async def _execute_tool_call_queued(self, tool_name: str, arguments: Dict[str, Any], parent_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute tool call through task queue with depth limiting"""
        from src.core.tasks.queue.task import ToolCallTask

        self.logger.info(f"🔄 Queuing tool call: {tool_name} (parent: {parent_task_id})")

        # Create tool call task
        task = ToolCallTask.create(
            tool_name=tool_name,
            tool_args=arguments,
            parent_task_id=parent_task_id,
            priority=1  # Tool calls get higher priority
        )

        # Queue the task with parent tracking for depth limiting
        task_id = self.task_queue.queue_task(task, parent_task_id)

        self.logger.info(f"📝 Tool call task queued: {task_id}")

        # Wait for task completion (polling approach)
        max_wait = 30  # 30 second timeout
        wait_interval = 0.1  # Check every 100ms
        waited = 0

        while waited < max_wait:
            status = self.task_queue.get_task_status(task_id)
            if not status:
                break

            if status["status"] in ["completed", "failed"]:
                # Get result
                if status["status"] == "completed":
                    result = self.task_queue.get_task_result(task_id)
                    if result and not result.get("error"):
                        result["tool_name"] = tool_name
                        self.logger.info(f"✅ Queued tool call completed: {task_id}")
                        return result

                # Handle failure
                error = status.get("error", "Tool call failed")
                self.logger.error(f"❌ Queued tool call failed: {task_id} - {error}")
                return {
                    "success": False,
                    "error": error,
                    "tool_name": tool_name,
                    "task_id": task_id
                }

            await asyncio.sleep(wait_interval)
            waited += wait_interval

        # Timeout
        error = f"Tool call timeout after {max_wait}s"
        self.logger.error(f"⏰ Tool call timeout: {task_id}")
        return {
            "success": False,
            "error": error,
            "tool_name": tool_name,
            "task_id": task_id
        }

    async def _execute_tool_call_direct(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call directly (fallback mode)"""
        self.logger.warning(f"⚠️ Direct tool execution (no queue): {tool_name}")

        # Execute through tool executor
        result = await self.tool_executor.execute_tool(tool_name, arguments)

        # Ensure result has success field
        if not isinstance(result, dict):
            result = {"success": True, "result": result}

        result["tool_name"] = tool_name
        self.logger.debug(f"EXIT _execute_tool_call_direct: {result.get('success', False)}")
        return result

    def register_tools(self, tools: List[Dict[str, Any]]):
        """Register available tools"""
        self.logger.debug(f"ENTRY register_tools: {len(tools)} tools")
        self.available_tools = tools
        self.formatter = ToolPromptFormatter(self.available_tools)
        self.logger.info(f"Registered {len(tools)} tools: {[t.get('name') for t in tools]}")

    def is_ready(self) -> bool:
        """Check if bridge is ready to process tool calls"""
        ready = bool(self.available_tools and self.tool_executor)
        self.logger.debug(f"Bridge ready: {ready} (tools: {len(self.available_tools)}, executor: {bool(self.tool_executor)})")
        return ready