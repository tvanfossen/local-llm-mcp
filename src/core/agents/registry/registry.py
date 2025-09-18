"""Agent Registry - Centralized Agent Management with Unified Task Queue

Responsibilities:
- Track and manage all active agents  
- Load agents from disk on startup
- Provide agent lookup and statistics
- Handle agent creation and removal
- Use unified task queue for all operations
"""

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.core.agents.agent.agent import Agent, AgentCreateParams
from src.core.config.manager.manager import ConfigManager
from src.core.tasks.queue import AgentTask, TaskExecutor, TaskQueue, TaskStatus
from src.schemas.agents.agents import TaskType, create_standard_request

logger = logging.getLogger(__name__)


class AgentTaskExecutor(TaskExecutor):
    """Executor for agent tasks in the unified queue system"""

    def __init__(self, agent_registry):
        self.agent_registry = agent_registry

    async def execute(self, task: AgentTask):
        """Execute an agent task"""
        try:
            logger.info(f"🤖 Executing agent task {task.task_id}")
            task.status = TaskStatus.RUNNING

            # Get agent
            agent = self.agent_registry.agents.get(task.agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {task.agent_id}")

            logger.info(f"🤖 Found agent: {agent.state.name} (ID: {task.agent_id})")

            # Map task type string to enum
            task_type_map = {
                "conversation": TaskType.CONVERSATION,
                "file_edit": TaskType.FILE_EDIT,
                "code_generation": TaskType.CODE_GENERATION,
                "system_query": TaskType.SYSTEM_QUERY,
            }

            task_type = task_type_map.get(
                task.request.get("task_type", "conversation"),
                TaskType.CONVERSATION
            )

            # Create standard request if needed
            if isinstance(task.request, dict):
                request = create_standard_request(
                    task.request.get("message", ""),
                    task_type,
                    task.agent_id
                )
            else:
                # Request is already a proper AgentRequest object
                request = task.request

            # Process request
            response = await agent.process_request(request)

            logger.info(
                f"🎯 Agent response: success={response.success}, "
                f"content_len={len(response.content) if response.content else 0}"
            )

            # Store result
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


class AgentRegistry:
    """Central registry for managing all agents"""

    def __init__(self, config_manager: ConfigManager, llm_manager=None, tool_executor=None):
        self.config_manager = config_manager
        self.llm_manager = llm_manager
        self.tool_executor = tool_executor
        self.agents: Dict[str, Agent] = {}
        self.system_config = config_manager.system
        self.task_queue = TaskQueue(max_tasks=100, tool_executor=tool_executor)

        # Create and register agent task executor
        agent_executor = AgentTaskExecutor(self)
        self.task_queue.register_executor("agent_operation", agent_executor)

        # Load existing agents from disk
        self._load_agents_from_disk()

        # Start task queue worker
        asyncio.create_task(self.task_queue.start_worker())

    def _load_agents_from_disk(self):
        """Load all agents from the agents directory"""
        if not self.system_config.agents_dir.exists():
            logger.info("No agents directory found, starting with empty registry")
            return

        loaded_count = 0
        for agent_dir in self.system_config.agents_dir.iterdir():
            if agent_dir.is_dir():
                try:
                    agent = Agent.load_from_disk(
                        agent_dir.name, self.system_config, self.llm_manager, self.tool_executor
                    )
                    self.agents[agent.state.agent_id] = agent
                    loaded_count += 1
                except Exception as e:
                    logger.warning(f"Failed to load agent from {agent_dir}: {e}")

        logger.info(f"Loaded {loaded_count} agents from disk")

    def update_toolchain(self, llm_manager=None, tool_executor=None):
        """Update all agents with new LLM manager and tool executor"""
        self.llm_manager = llm_manager or self.llm_manager
        self.tool_executor = tool_executor or self.tool_executor

        # Update task queue tool executor
        if self.tool_executor:
            self.task_queue.tool_executor = self.tool_executor
            logger.info("✅ Updated TaskQueue with consolidated tool executor")

        # Update existing agents
        for agent in self.agents.values():
            agent.llm_manager = self.llm_manager
            agent.tool_executor = self.tool_executor

        logger.info(f"Updated {len(self.agents)} agents with consolidated toolchain")

    def create_agent(self, name: str, description: str, specialized_files: list[str] = None) -> Agent:
        """Create a new agent and register it"""
        params = AgentCreateParams(
            name=name,
            description=description,
            system_config=self.system_config,
            specialized_files=specialized_files or [],
        )

        agent = Agent.create(params, self.llm_manager, self.tool_executor)
        self.agents[agent.state.agent_id] = agent

        logger.info(f"Created new agent: {name} (ID: {agent.state.agent_id})")
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get agent by name (returns first match)"""
        for agent in self.agents.values():
            if agent.state.name == name:
                return agent
        return None

    def list_agents(self) -> list[Agent]:
        """Get list of all registered agents"""
        return list(self.agents.values())

    def remove_agent(self, agent_id: str) -> bool:
        """Remove agent from registry"""
        if agent_id in self.agents:
            agent = self.agents.pop(agent_id)
            logger.info(f"Removed agent: {agent.state.name} (ID: {agent_id})")
            return True
        return False

    def get_agents_for_file(self, file_path: str) -> list[Agent]:
        """Get all agents that manage a specific file"""
        return [agent for agent in self.agents.values() if file_path in agent.managed_files]

    def assign_file_to_agent(self, agent_id: str, file_path: str) -> bool:
        """Assign a file to an agent"""
        agent = self.get_agent(agent_id)
        if agent:
            agent.add_managed_file(file_path)
            return True
        return False

    def unassign_file_from_agent(self, agent_id: str, file_path: str) -> bool:
        """Unassign a file from an agent"""
        agent = self.get_agent(agent_id)
        if agent:
            agent.remove_managed_file(file_path)
            return True
        return False

    def cleanup_invalid_files(self) -> int:
        """Remove references to files that no longer exist"""
        workspace_root = self.system_config.workspace_root
        cleanup_count = 0

        for agent in self.agents.values():
            files_to_remove = []
            for file_path in agent.managed_files:
                full_path = workspace_root / file_path
                if not full_path.exists():
                    files_to_remove.append(file_path)

            for file_path in files_to_remove:
                agent.remove_managed_file(file_path)
                cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} invalid file references")

        return cleanup_count

    def save_registry(self):
        """Save registry state to disk"""
        try:
            # Each agent already saves its own state
            # This method ensures all agents persist their current state
            for agent in self.agents.values():
                agent._save_metadata()
                agent._save_conversation_history()

            logger.info(f"Saved registry with {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def queue_task(self, agent_id: str, request: Dict) -> str:
        """Queue a new agent task for async execution
        
        Args:
            agent_id: ID of the agent to execute the task
            request: Dictionary containing message and task_type
            
        Returns:
            Task ID string
        """
        # Ensure request is a dictionary
        if not isinstance(request, dict):
            raise TypeError(f"Request must be a dictionary, got {type(request)}")
            
        # Create the AgentTask with proper structure
        task = AgentTask.create(agent_id=agent_id, request=request)
        
        # Queue the task - task.task_id is guaranteed to be a string from create()
        return self.task_queue.queue_task(task)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status"""
        return self.task_queue.get_task_status(task_id)

    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """Get task result"""
        return self.task_queue.get_task_result(task_id)

    def list_tasks(self, agent_id: Optional[str] = None) -> List[Dict]:
        """List tasks, optionally filtered by agent"""
        all_tasks = self.task_queue.list_tasks(task_type="agent_operation", limit=100)
        if agent_id:
            return [t for t in all_tasks if t.get("agent_id") == agent_id]
        return all_tasks

    def get_registry_stats(self) -> dict:
        """Get statistics about the agent registry including task queue"""
        if not self.agents:
            return {
                "total_agents": 0,
                "managed_files": 0,
                "total_interactions": 0,
                "average_success_rate": 0.0,
                "most_active_agent": None,
                "queued_tasks": len(self.task_queue.tasks),
                "active_tasks": sum(1 for t in self.task_queue.tasks.values() if t.status.value == "running"),
            }

        total_interactions = sum(agent.state.interaction_count for agent in self.agents.values())
        total_files = sum(len(agent.managed_files) for agent in self.agents.values())

        # Calculate average success rate
        success_rates = [
            agent.state.success_rate for agent in self.agents.values() if agent.state.interaction_count > 0
        ]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

        # Find most active agent
        most_active = max(self.agents.values(), key=lambda a: a.state.interaction_count, default=None)

        return {
            "total_agents": len(self.agents),
            "managed_files": total_files,
            "total_interactions": total_interactions,
            "average_success_rate": round(avg_success_rate, 3),
            "most_active_agent": most_active.state.name if most_active else None,
            "queued_tasks": len(self.task_queue.tasks),
            "active_tasks": sum(1 for t in self.task_queue.tasks.values() if t.status.value == "running"),
        }

    async def shutdown(self):
        """Shutdown registry and task queue"""
        await self.task_queue.stop_worker()
        self.save_registry()