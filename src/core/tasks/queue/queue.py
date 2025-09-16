"""Generic Task Queue for Async Operations

Provides a generic task queue that can handle different types of tasks
including agent operations and MCP tool calls.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

from .task import Task, TaskStatus, ToolCallTask
from src.core.exceptions import MaxDepthExceeded, TaskQueueFull

logger = logging.getLogger(__name__)


class TaskExecutor(Protocol):
    """Protocol for task executors"""
    async def execute(self, task: Task) -> None:
        """Execute a task and update its status"""
        ...


class ToolCallExecutor(TaskExecutor):
    """Executor for MCP tool call tasks"""

    def __init__(self, tool_executor):
        self.tool_executor = tool_executor

    async def execute(self, task: ToolCallTask) -> None:
        """Execute a tool call task with comprehensive logging"""
        logger.debug(f"ENTRY ToolCallExecutor.execute: task_id={task.task_id}, tool={task.tool_name}")

        try:
            task.status = TaskStatus.RUNNING
            logger.info(f"🔧 Tool call {task.task_id} status changed: QUEUED → RUNNING")

            # Execute tool through the tool executor
            logger.info(f"🛠️ Executing tool: {task.tool_name} with args: {task.tool_args}")

            result = await self.tool_executor.execute_tool(task.tool_name, task.tool_args)

            # Ensure result has success field
            if not isinstance(result, dict):
                result = {"success": True, "result": result}

            logger.info(f"🎯 Tool call response: success={result.get('success', False)}")

            # Store result
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Tool call {task.task_id} completed successfully")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Tool call {task.task_id} failed: {e}")

        logger.debug(f"EXIT ToolCallExecutor.execute: status={task.status.value}")


class TaskQueue:
    """Generic async task queue with priority support"""

    def __init__(self, max_tasks: int = 100, max_nesting_depth: int = 3):
        self.tasks: Dict[str, Task] = {}
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.max_tasks = max_tasks
        self.max_nesting_depth = max_nesting_depth
        self.task_depth_tracking: Dict[str, int] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._executors: Dict[str, TaskExecutor] = {}

    def register_executor(self, task_type: str, executor: TaskExecutor):
        """Register an executor for a specific task type"""
        self._executors[task_type] = executor
        logger.debug(f"Registered executor for task type: {task_type}")

    async def start_worker(self):
        """Start the background worker for processing tasks"""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._process_tasks())
            logger.info("Generic task queue worker started")

    async def stop_worker(self):
        """Stop the background worker"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Generic task queue worker stopped")

    async def _process_tasks(self):
        """Background worker to process queued tasks"""
        while True:
            try:
                # Priority queue returns (priority, task)
                # We use negative priority for max-heap behavior
                _, task = await self.queue.get()
                await self._execute_task(task)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task processing error: {e}")

    async def _execute_task(self, task: Task):
        """Execute a single task using the appropriate executor"""
        try:
            task.status = TaskStatus.RUNNING
            logger.info(f"Executing task {task.task_id} of type {task.task_type}")

            executor = self._executors.get(task.task_type)
            if not executor:
                raise ValueError(f"No executor registered for task type: {task.task_type}")

            await executor.execute(task)

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.COMPLETED

            logger.info(f"Task {task.task_id} completed successfully")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Task {task.task_id} failed: {e}")

    def queue_task(self, task: Task, parent_task_id: Optional[str] = None) -> str:
        """Queue a task for async execution with nesting control"""
        # Check nesting depth
        if parent_task_id:
            parent_depth = self.task_depth_tracking.get(parent_task_id, 0)
            if parent_depth >= self.max_nesting_depth:
                raise MaxDepthExceeded(parent_depth + 1, self.max_nesting_depth)
            self.task_depth_tracking[task.task_id] = parent_depth + 1
        else:
            self.task_depth_tracking[task.task_id] = 0

        # Clean up old tasks if needed
        if len(self.tasks) >= self.max_tasks:
            self._cleanup_old_tasks()

        # Store task
        self.tasks[task.task_id] = task

        # Queue with priority (negative for max-heap)
        priority_value = -task.priority
        asyncio.create_task(self.queue.put((priority_value, task)))

        logger.info(f"Queued task {task.task_id} of type {task.task_type} with priority {task.priority}")
        return task.task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        task = self.tasks.get(task_id)
        return task.to_dict() if task else None

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result if completed"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        if task.status != TaskStatus.COMPLETED:
            return {
                "error": f"Task not completed. Status: {task.status.value}",
                "status": task.status.value
            }

        return task.result

    def list_tasks(self, task_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List all tasks or tasks of specific type"""
        tasks = []
        for task in self.tasks.values():
            if task_type and task.task_type != task_type:
                continue
            tasks.append(task.to_dict())

        # Sort by created_at descending
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return tasks[:limit]

    def _cleanup_old_tasks(self):
        """Remove old completed/failed tasks"""
        completed_tasks = [
            (t.task_id, t.completed_at)
            for t in self.tasks.values()
            if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        ]

        if len(completed_tasks) > 50:
            completed_tasks.sort(key=lambda x: x[1] or "")
            for task_id, _ in completed_tasks[:-50]:
                if task_id in self.task_depth_tracking:
                    del self.task_depth_tracking[task_id]
                del self.tasks[task_id]

            logger.debug(f"Cleaned up {len(completed_tasks) - 50} old tasks")