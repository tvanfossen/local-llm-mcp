"""Task Queue for Async Agent Operations - Backward Compatibility Wrapper

This module provides backward compatibility while using the new generic task queue infrastructure.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.tasks.queue import TaskQueue as GenericTaskQueue, TaskStatus, AgentTask, TaskExecutor

logger = logging.getLogger(__name__)


class AgentTaskExecutor(TaskExecutor):
    """Executor for agent tasks using the agent registry"""

    def __init__(self, agent_registry):
        self.agent_registry = agent_registry

    async def execute(self, task):
        """Execute an agent task with comprehensive logging"""
        logger.debug(f"ENTRY AgentTaskExecutor.execute: task_id={task.task_id}, agent_id={task.agent_id}")

        try:
            task.status = TaskStatus.RUNNING
            logger.info(f"✅ Task {task.task_id} status changed: PENDING → RUNNING")

            # Get agent with explicit failure handling
            agent = self.agent_registry.get_agent(task.agent_id)
            if not agent:
                error = f"Agent not found: {task.agent_id}"
                logger.error(f"EXIT AgentTaskExecutor.execute: FAILED - {error}")
                raise ValueError(error)

            logger.info(f"🤖 Found agent: {agent.state.name} (ID: {task.agent_id})")

            # Process the request with logging
            from src.schemas.agents.agents import TaskType, create_standard_request

            task_type_map = {
                "conversation": TaskType.CONVERSATION,
                "file_edit": TaskType.FILE_EDIT,
                "code_generation": TaskType.CODE_GENERATION,
                "system_query": TaskType.SYSTEM_QUERY,
            }

            task_type = task_type_map.get(task.request.get("task_type", "conversation"), TaskType.CONVERSATION)
            request = create_standard_request(task.request.get("message", ""), task_type, task.agent_id)

            logger.info(f"📝 Processing {task_type} request: {request.message[:100]}...")

            # Execute and store result
            response = await agent.process_request(request)

            logger.info(f"🎯 Agent response: success={response.success}, content_len={len(response.content) if response.content else 0}")

            task.result = {
                "success": response.success,
                "content": response.content,
                "task_type": response.task_type.value,
                "timestamp": response.timestamp,
                "files_modified": response.files_modified or [],
            }
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Agent task {task.task_id} completed successfully")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Agent task {task.task_id} failed: {e}")


class TaskQueue:
    """Backward compatibility wrapper for agent task queue"""

    def __init__(self):
        self._task_queue = GenericTaskQueue(max_tasks=100)
        self._agent_executor = None

    async def start_worker(self, agent_registry):
        """Start the background worker for processing tasks"""
        if not self._agent_executor:
            self._agent_executor = AgentTaskExecutor(agent_registry)
            self._task_queue.register_executor("agent_operation", self._agent_executor)

        await self._task_queue.start_worker()
        logger.info("Agent task queue worker started")

    async def stop_worker(self):
        """Stop the background worker"""
        await self._task_queue.stop_worker()
        logger.info("Agent task queue worker stopped")

    def queue_task(self, agent_id: str, request: Dict[str, Any]) -> str:
        """Queue a new agent task for async execution"""
        task = AgentTask.create(agent_id=agent_id, request=request)
        return self._task_queue.queue_task(task)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        status = self._task_queue.get_task_status(task_id)
        if not status:
            return None

        # Convert to legacy format
        return {
            "task_id": status["task_id"],
            "status": status["status"],
            "agent_id": status.get("agent_id", ""),
            "created_at": status["created_at"],
            "completed_at": status["completed_at"],
            "has_result": status["result"] is not None,
            "error": status["error"],
        }

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result if completed"""
        return self._task_queue.get_task_result(task_id)

    def list_tasks(self, agent_id: Optional[str] = None) -> list:
        """List all tasks or tasks for specific agent"""
        tasks = self._task_queue.list_tasks(task_type="agent_operation", limit=20)

        if agent_id:
            tasks = [t for t in tasks if t.get("agent_id") == agent_id]

        return tasks
