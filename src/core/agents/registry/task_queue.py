"""Task Queue for Async Agent Operations

Responsibilities:
- Queue agent tasks for async execution
- Track task status and results
- Manage task lifecycle
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentTask:
    """Represents a queued agent task"""

    task_id: str
    agent_id: str
    status: TaskStatus
    created_at: str
    completed_at: Optional[str] = None
    request: dict[str, Any] = field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "request": self.request,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Manages async task queue for agent operations"""

    def __init__(self):
        self.tasks: dict[str, AgentTask] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_tasks = 100  # Prevent memory issues
        self._worker_task = None

    async def start_worker(self, agent_registry):
        """Start the background worker for processing tasks"""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._process_tasks(agent_registry))
            logger.info("Task queue worker started")

    async def stop_worker(self):
        """Stop the background worker"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Task queue worker stopped")

    async def _process_tasks(self, agent_registry):
        """Background worker to process queued tasks"""
        while True:
            try:
                task = await self.queue.get()
                await self._execute_task(task, agent_registry)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task processing error: {e}")

    async def _execute_task(self, task: AgentTask, agent_registry):
        """Execute a single task"""
        try:
            # Update status to running
            task.status = TaskStatus.RUNNING
            logger.info(f"Executing task {task.task_id} for agent {task.agent_id}")

            # Get agent and execute
            agent = agent_registry.get_agent(task.agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {task.agent_id}")

            # Process the request
            from src.schemas.agents.agents import TaskType, create_standard_request

            task_type_map = {
                "conversation": TaskType.CONVERSATION,
                "file_edit": TaskType.FILE_EDIT,
                "code_generation": TaskType.CODE_GENERATION,
                "system_query": TaskType.SYSTEM_QUERY,
            }

            task_type = task_type_map.get(task.request.get("task_type", "conversation"), TaskType.CONVERSATION)

            request = create_standard_request(task.request.get("message", ""), task_type, task.agent_id)

            # Execute and store result
            response = await agent.process_request(request)

            task.result = {
                "success": response.success,
                "content": response.content,
                "task_type": response.task_type.value,
                "timestamp": response.timestamp,
                "files_modified": response.files_modified or [],
            }
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Task {task.task_id} completed successfully")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Task {task.task_id} failed: {e}")

    def queue_task(self, agent_id: str, request: dict[str, Any]) -> str:
        """Queue a new task for async execution"""
        # Clean up old tasks if needed
        if len(self.tasks) >= self.max_tasks:
            self._cleanup_old_tasks()

        # Create new task
        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            status=TaskStatus.QUEUED,
            created_at=datetime.now(timezone.utc).isoformat(),
            request=request,
        )

        # Store and queue
        self.tasks[task_id] = task
        asyncio.create_task(self.queue.put(task))

        logger.info(f"Queued task {task_id} for agent {agent_id}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get task status"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "agent_id": task.agent_id,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
            "has_result": task.result is not None,
            "error": task.error,
        }

    def get_task_result(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get task result if completed"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        if task.status != TaskStatus.COMPLETED:
            return {"error": f"Task not completed. Status: {task.status.value}", "status": task.status.value}

        return task.result

    def list_tasks(self, agent_id: Optional[str] = None) -> list:
        """List all tasks or tasks for specific agent"""
        tasks = []
        for task in self.tasks.values():
            if agent_id and task.agent_id != agent_id:
                continue
            tasks.append(task.to_dict())

        # Sort by created_at descending
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return tasks[:20]  # Limit to 20 most recent

    def _cleanup_old_tasks(self):
        """Remove old completed/failed tasks"""
        # Keep only last 50 completed/failed tasks
        completed_tasks = [
            (t.task_id, t.completed_at)
            for t in self.tasks.values()
            if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        ]

        if len(completed_tasks) > 50:
            # Sort by completion time and remove oldest
            completed_tasks.sort(key=lambda x: x[1] or "")
            for task_id, _ in completed_tasks[:-50]:
                del self.tasks[task_id]

            logger.debug(f"Cleaned up {len(completed_tasks) - 50} old tasks")
