"""MCP Tool Call Router

Central routing for all tool calls with queue submission,
result tracking, priority handling, and timeout management.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.core.tasks.queue import TaskQueue, ToolCallTask
from .executor import ToolCallExecutor

logger = logging.getLogger(__name__)


class MCPRouter:
    """Central router for MCP tool calls"""

    def __init__(self, tool_executor, max_concurrent_tools: int = 5):
        self.tool_executor = tool_executor
        self.task_queue = TaskQueue(max_tasks=200, max_nesting_depth=5)
        self.tool_call_executor = ToolCallExecutor(tool_executor)
        self.max_concurrent_tools = max_concurrent_tools
        self.active_tool_calls: Dict[str, asyncio.Task] = {}
        self._started = False

    async def start(self):
        """Start the router and its components"""
        if self._started:
            return

        # Register the tool call executor
        self.task_queue.register_executor("tool_call", self.tool_call_executor)

        # Start the task queue worker
        await self.task_queue.start_worker()

        self._started = True
        logger.info("MCP Router started successfully")

    async def stop(self):
        """Stop the router and clean up"""
        if not self._started:
            return

        # Cancel active tool calls
        for task_id, task in self.active_tool_calls.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled active tool call: {task_id}")

        self.active_tool_calls.clear()

        # Stop task queue
        await self.task_queue.stop_worker()

        self._started = False
        logger.info("MCP Router stopped")

    async def execute_tool_call(self, tool_name: str, tool_args: Dict[str, Any],
                               parent_task_id: Optional[str] = None,
                               timeout: float = 30.0) -> Dict[str, Any]:
        """Execute a tool call with timeout and result tracking"""
        if not self._started:
            await self.start()

        # Create tool call task
        task = ToolCallTask.create(
            tool_name=tool_name,
            tool_args=tool_args,
            parent_task_id=parent_task_id,
            priority=self._get_tool_priority(tool_name)
        )

        # Queue the task
        task_id = self.task_queue.queue_task(task, parent_task_id)
        logger.info(f"Queued tool call {tool_name} with task_id {task_id}")

        # Wait for completion with timeout
        try:
            result = await asyncio.wait_for(
                self._wait_for_task_completion(task_id),
                timeout=timeout
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"Tool call {tool_name} timed out after {timeout}s")
            return {
                "success": False,
                "error": f"Tool call timed out after {timeout} seconds",
                "tool_name": tool_name
            }

    async def execute_multiple_tools(self, tool_calls: List[Dict[str, Any]],
                                   parent_task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute multiple tool calls concurrently"""
        if len(tool_calls) > self.max_concurrent_tools:
            logger.warning(f"Too many concurrent tools ({len(tool_calls)} > {self.max_concurrent_tools}), executing in batches")

        results = []
        for i in range(0, len(tool_calls), self.max_concurrent_tools):
            batch = tool_calls[i:i + self.max_concurrent_tools]
            batch_results = await self._execute_tool_batch(batch, parent_task_id)
            results.extend(batch_results)

        return results

    async def _execute_tool_batch(self, tool_calls: List[Dict[str, Any]],
                                 parent_task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute a batch of tool calls concurrently"""
        tasks = []
        for call in tool_calls:
            tool_name = call.get("tool_name") or call.get("function_name")
            tool_args = call.get("arguments", {})

            if tool_name:
                task = self.execute_tool_call(tool_name, tool_args, parent_task_id)
                tasks.append(task)
            else:
                # Invalid tool call
                tasks.append(asyncio.create_task(asyncio.coroutine(lambda: {
                    "success": False,
                    "error": "No tool name specified",
                    "call": call
                })()))

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _wait_for_task_completion(self, task_id: str) -> Dict[str, Any]:
        """Wait for a task to complete and return its result"""
        poll_interval = 0.1
        max_polls = 600  # 60 seconds maximum

        for _ in range(max_polls):
            task_status = self.task_queue.get_task_status(task_id)
            if not task_status:
                raise RuntimeError(f"Task {task_id} not found")

            status = task_status["status"]
            if status == "completed":
                result = self.task_queue.get_task_result(task_id)
                return result or {"success": True, "content": "Task completed"}

            elif status == "failed":
                error = task_status.get("error", "Unknown error")
                return {
                    "success": False,
                    "error": f"Task execution failed: {error}",
                    "task_id": task_id
                }

            await asyncio.sleep(poll_interval)

        raise asyncio.TimeoutError(f"Task {task_id} did not complete within timeout")

    def _get_tool_priority(self, tool_name: str) -> int:
        """Get priority for different tool types"""
        priority_map = {
            "validation": 2,    # High priority for validation
            "git_operations": 1, # Medium priority for git ops
            "workspace": 0,     # Normal priority for workspace
        }
        return priority_map.get(tool_name, 0)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and metrics"""
        return {
            "started": self._started,
            "active_tool_calls": len(self.active_tool_calls),
            "max_concurrent": self.max_concurrent_tools,
            "queue_tasks": len(self.task_queue.tasks),
            "performance": self.tool_call_executor.get_performance_metrics()
        }

    def list_active_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List active tool call tasks"""
        return self.task_queue.list_tasks(task_type="tool_call", limit=limit)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        return {
            "router_status": self.get_queue_status(),
            "executor_metrics": self.tool_call_executor.get_performance_metrics(),
            "cache_info": self.tool_call_executor.get_cached_results()
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the router"""
        try:
            # Quick test tool call
            test_result = await self.execute_tool_call(
                "workspace",
                {"action": "list", "path": "."},
                timeout=5.0
            )

            return {
                "status": "healthy" if test_result.get("success") else "degraded",
                "started": self._started,
                "test_result": test_result.get("success", False),
                "queue_size": len(self.task_queue.tasks),
                "metrics": self.tool_call_executor.get_performance_metrics()
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "started": self._started
            }