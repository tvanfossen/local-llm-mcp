"""Tool Call Executor for MCP Router

Handles async execution of queued tool calls with error handling,
retry logic, result caching, and performance monitoring.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from src.core.tasks.queue import TaskExecutor, Task, TaskStatus, ToolCallTask

logger = logging.getLogger(__name__)


class ToolCallExecutor(TaskExecutor):
    """Executor for tool call tasks"""

    def __init__(self, tool_executor, cache_size: int = 100):
        self.tool_executor = tool_executor
        self.result_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_size = cache_size
        self.performance_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0
        }

    async def execute(self, task: Task) -> None:
        """Execute a tool call task and update its status"""
        if not isinstance(task, ToolCallTask):
            task.status = TaskStatus.FAILED
            task.error = f"Invalid task type: {type(task).__name__}"
            return

        start_time = time.time()
        self.performance_metrics["total_executions"] += 1

        try:
            # Check cache first
            cache_key = self._create_cache_key(task.tool_name, task.tool_args)
            if cache_key in self.result_cache:
                logger.debug(f"Using cached result for {task.tool_name}")
                task.result = self.result_cache[cache_key]
                task.status = TaskStatus.COMPLETED
                return

            # Execute tool call
            logger.info(f"Executing tool call: {task.tool_name}")
            result = await self._execute_tool_call(task.tool_name, task.tool_args)

            # Store result and update status
            task.result = result
            task.status = TaskStatus.COMPLETED

            # Cache successful results
            if result.get("success"):
                self._cache_result(cache_key, result)

            self.performance_metrics["successful_executions"] += 1
            logger.info(f"Tool call {task.tool_name} completed successfully")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self.performance_metrics["failed_executions"] += 1
            logger.error(f"Tool call {task.tool_name} failed: {e}")

        finally:
            # Update performance metrics
            execution_time = time.time() - start_time
            self._update_average_time(execution_time)

    async def _execute_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual tool call with retry logic"""
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                result = await self.tool_executor.execute_tool(tool_name, tool_args)
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Tool call attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise e

    def _create_cache_key(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Create a cache key for the tool call"""
        # Only cache read-only operations
        readonly_tools = {"workspace": ["read", "list"], "validation": ["tests", "file-length"]}

        if tool_name in readonly_tools:
            action = tool_args.get("action") or tool_args.get("operation")
            if action in readonly_tools[tool_name]:
                # Create simple hash of tool + args
                import hashlib
                key_data = f"{tool_name}:{str(sorted(tool_args.items()))}"
                return hashlib.md5(key_data.encode()).hexdigest()

        return ""  # Empty key means no caching

    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache a successful result"""
        if not cache_key:
            return

        # Manage cache size
        if len(self.result_cache) >= self.cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.result_cache))
            del self.result_cache[oldest_key]

        self.result_cache[cache_key] = result.copy()
        logger.debug(f"Cached result for key: {cache_key}")

    def _update_average_time(self, execution_time: float):
        """Update average execution time metric"""
        total = self.performance_metrics["total_executions"]
        current_avg = self.performance_metrics["average_execution_time"]
        new_avg = ((current_avg * (total - 1)) + execution_time) / total
        self.performance_metrics["average_execution_time"] = new_avg

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        total = self.performance_metrics["total_executions"]
        if total == 0:
            success_rate = 0.0
        else:
            success_rate = self.performance_metrics["successful_executions"] / total

        return {
            **self.performance_metrics,
            "success_rate": success_rate,
            "cache_hit_rate": len(self.result_cache) / max(total, 1),
            "cache_size": len(self.result_cache)
        }

    def clear_cache(self):
        """Clear the result cache"""
        self.result_cache.clear()
        logger.info("Tool call result cache cleared")

    def get_cached_results(self) -> Dict[str, Any]:
        """Get information about cached results"""
        return {
            "total_cached": len(self.result_cache),
            "cache_keys": list(self.result_cache.keys())
        }