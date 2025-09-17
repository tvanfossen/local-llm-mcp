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

    def __init__(self, system_config: ConfigManager):
        self.system_config = system_config
        self.agents: Dict[str, Agent] = {}
        self.llm_manager = None  # Will be set via update_toolchain
        self.tool_executor = None  # Will be set via update_toolchain
        self.task_queue = TaskQueue(max_tasks=100, max_nesting_depth=3)
        self._agent_executor = AgentTaskExecutor(self)
        logger.info("Agent Registry initialized with unified task queue")

    async def initialize(self, llm_manager=None, tool_executor=None):
        """Initialize registry and load existing agents"""
        # Update toolchain
        self.update_toolchain(llm_manager, tool_executor)
        
        # Register agent executor
        self.task_queue.register_executor("agent_operation", self._agent_executor)
        
        # Start worker
        await self.task_queue.start_worker()
        
        # Load existing agents from disk
        agents_dir = self.system_config.workspace_root / ".mcp-agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir() and (agent_dir / "metadata.json").exists():
                    try:
                        agent = Agent.load_from_disk(
                            agent_dir.name, 
                            self.system_config, 
                            self.llm_manager,
                            self.tool_executor
                        )
                        self.agents[agent.state.agent_id] = agent
                        logger.info(f"Loaded agent {agent.state.name} from {agent_dir.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load agent from {agent_dir}: {e}")

        logger.info(f"Registry initialized with {len(self.agents)} agents")

    def update_toolchain(self, llm_manager=None, tool_executor=None):
        """Update the LLM manager and tool executor references
        
        Args:
            llm_manager: LLM manager instance
            tool_executor: Tool executor instance
        """
        if llm_manager:
            self.llm_manager = llm_manager
        if tool_executor:
            self.tool_executor = tool_executor
            # Update the tool executor in the task queue
            self.task_queue.tool_executor = tool_executor
            
        # Update all existing agents with new toolchain
        for agent in self.agents.values():
            if llm_manager:
                agent.llm_manager = llm_manager
            if tool_executor:
                agent.tool_executor = tool_executor
                
        logger.info(f"Updated toolchain for {len(self.agents)} agents")

    def create_agent(self, params: AgentCreateParams) -> Agent:
        """Create and register a new agent"""
        agent = Agent(self.system_config, params, self.llm_manager, self.tool_executor)
        self.agents[agent.state.agent_id] = agent
        agent.save_to_disk()
        logger.info(f"Created agent {agent.state.name} with ID {agent.state.agent_id}")
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Dict]:
        """List all registered agents"""
        return [agent.to_dict() for agent in self.agents.values()]

    def remove_agent(self, agent_id: str) -> bool:
        """Remove agent from registry"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # Clean up agent directory if it exists
            agent_dir = self.system_config.workspace_root / ".mcp-agents" / agent_id
            if agent_dir.exists():
                shutil.rmtree(agent_dir)
            del self.agents[agent_id]
            logger.info(f"Removed agent {agent_id}")
            return True
        return False

    def get_agent_by_file(self, file_path: str) -> Optional[Agent]:
        """Get agent that manages a specific file"""
        for agent in self.agents.values():
            if file_path in agent.state.managed_files:
                return agent
        return None

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
            for file_path in agent.state.managed_files:
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
            for agent in self.agents.values():
                agent.save_to_disk()

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

    def get_registry_stats(self) -> Dict:
        """Get registry statistics

        Returns:
            Dictionary containing registry stats
        """
        total_tasks = len(self.task_queue.tasks)
        completed_tasks = sum(1 for t in self.task_queue.tasks.values()
                              if t.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for t in self.task_queue.tasks.values()
                           if t.status == TaskStatus.FAILED)

        # Calculate backward-compatible fields
        total_managed_files = sum(len(agent.state.managed_files) for agent in self.agents.values())
        total_interactions = sum(agent.state.interaction_count for agent in self.agents.values())

        # Calculate average success rate
        success_rates = [
            agent.state.success_rate for agent in self.agents.values()
            if agent.state.interaction_count > 0
        ]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

        # Find most active agent
        most_active = max(self.agents.values(), key=lambda a: a.state.interaction_count, default=None)

        return {
            "total_agents": len(self.agents),
            "managed_files": total_managed_files,
            "total_interactions": total_interactions,
            "average_success_rate": avg_success_rate,
            "most_active_agent": most_active.state.name if most_active else None,
            "queued_tasks": len(self.task_queue.tasks),
            "active_tasks": sum(1 for t in self.task_queue.tasks.values() if t.status == TaskStatus.RUNNING),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": total_tasks - completed_tasks - failed_tasks,
            "agents": [
                {
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                    "files": len(agent.state.managed_files),
                    "interactions": agent.state.interaction_count
                }
                for agent in self.agents.values()
            ]
        }

    async def shutdown(self):
        """Shutdown registry and task queue"""
        await self.task_queue.stop_worker()
        self.save_registry()
        logger.info("Agent registry shutdown complete")