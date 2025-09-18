"""Agent Operations Tool - Unified agent management operations with async queue

Responsibilities:
- List agents with details
- Get agent information
- Agent status and statistics
- Agent lifecycle operations
- Async task queue operations
"""

import logging
from typing import Any, Optional

from src.core.utils.utils import create_mcp_response, handle_exception

logger = logging.getLogger(__name__)


class AgentOperations:
    """Agent management operations handler with async task support"""

    def __init__(self, agent_registry=None):
        """Initialize with agent registry reference"""
        self.agent_registry = agent_registry

    def list_agents(self) -> dict[str, Any]:
        """List all agents with their details"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            agents = []
            agent_list = self.agent_registry.list_agents()

            for agent in agent_list:
                agent_info = {
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                    "description": agent.state.description,
                    "files_count": len(agent.state.managed_files),
                    "interactions": agent.state.interaction_count,
                    "success_rate": agent.state.success_rate,
                    "created_at": agent.state.created_at,
                    "last_updated": agent.state.last_updated,
                    "total_tasks": agent.state.total_tasks_completed,
                }
                agents.append(agent_info)

            # Format response text
            if not agents:
                response_text = "No agents found in the registry."
            else:
                response_text = f"**Found {len(agents)} agents:**\n\n"
                for agent in agents:
                    response_text += f"🤖 **{agent['name']}** (ID: {agent['id'][:12]}...)\n"
                    if agent["description"]:
                        response_text += f"   Description: {agent['description']}\n"
                    response_text += f"   Managing: {agent['files_count']} files\n"
                    response_text += f"   Interactions: {agent['interactions']}\n"
                    response_text += f"   Success Rate: {agent['success_rate']:.1%}\n\n"

            return {"success": True, "agents": agents, "count": len(agents), "response_text": response_text}

        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return {"success": False, "error": str(e)}

    def get_agent_info(self, agent_id: str) -> dict[str, Any]:
        """Get detailed information about a specific agent"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"success": False, "error": f"Agent not found: {agent_id}"}

            info = {
                "id": agent.state.agent_id,
                "name": agent.state.name,
                "description": agent.state.description,
                "files_count": len(agent.state.managed_files),
                "managed_files": list(agent.state.managed_files),
                "interactions": agent.state.interaction_count,
                "success_rate": agent.state.success_rate,
                "created_at": agent.state.created_at,
                "last_updated": agent.state.last_updated,
                "total_tasks": agent.state.total_tasks_completed,
            }

            return {"success": True, "agent": info}

        except Exception as e:
            logger.error(f"Failed to get agent info: {e}")
            return {"success": False, "error": str(e)}

    def get_registry_stats(self) -> dict[str, Any]:
        """Get agent registry statistics"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            stats = self.agent_registry.get_registry_stats()
            return {"success": True, "stats": stats}

        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {"success": False, "error": str(e)}

    def create_agent(self, name: str, description: str, specialized_files: list[str] = None) -> dict[str, Any]:
        """Create a new agent"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            agent = self.agent_registry.create_agent(name, description, specialized_files)

            response_text = "**Agent Created Successfully**\n\n"
            response_text += f"🤖 **Name:** {agent.state.name}\n"
            response_text += f"🆔 **ID:** {agent.state.agent_id}\n"
            response_text += f"📝 **Description:** {agent.state.description}\n"
            if agent.state.managed_files:
                response_text += f"📁 **Managed Files:** {', '.join(agent.state.managed_files)}\n"
            response_text += f"📅 **Created:** {agent.state.created_at}\n\n"
            response_text += "Agent is ready to receive tasks via the chat operation."

            return {"success": True, "agent": agent.to_dict(), "response_text": response_text}

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return {"success": False, "error": str(e)}

    async def debug_chat_with_agent(self, agent_id: str, message: str, task_type: str = "conversation") -> dict[str, Any]:
        """DEBUG ONLY: Direct chat with agent bypassing structured MCP architecture

        ⚠️  WARNING: This bypasses the MCP tool calling architecture and should only be used for:
        - Debugging agent issues
        - Troubleshooting when queue_task fails
        - Development/testing purposes

        For normal operations, use queue_task instead!
        """
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"success": False, "error": f"Agent not found: {agent_id}"}

            # Import task type enum
            from src.schemas.agents.agents import TaskType

            # Map string task type to enum
            task_type_map = {
                "conversation": TaskType.CONVERSATION,
                "file_edit": TaskType.FILE_EDIT,
                "code_generation": TaskType.CODE_GENERATION,
                "system_query": TaskType.SYSTEM_QUERY,
            }

            task_enum = task_type_map.get(task_type, TaskType.CONVERSATION)

            # Create agent request
            from src.schemas.agents.agents import create_standard_request

            request = create_standard_request(message, task_enum, agent_id)

            # Process the request through the agent
            response = await agent.process_request(request)

            return {
                "success": response.success,
                "content": response.content,
                "agent_id": response.agent_id,
                "task_type": response.task_type.value,
                "timestamp": response.timestamp,
                "files_modified": response.files_modified or [],
            }

        except Exception as e:
            logger.error(f"Failed to chat with agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}

    def queue_agent_task(self, agent_id: str, message: str, task_type: str = "conversation") -> dict[str, Any]:
        """Queue an agent task for async execution"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        try:
            # Check agent exists
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"success": False, "error": f"Agent not found: {agent_id}"}

            # Queue the task
            task_id = self.agent_registry.queue_task(agent_id, {"message": message, "task_type": task_type})

            return {
                "success": True,
                "task_id": task_id,
                "status": "queued",
                "message": f"Task {task_id} queued for agent {agent.state.name}",
            }

        except Exception as e:
            logger.error(f"Failed to queue task: {e}")
            return {"success": False, "error": str(e)}

    def check_task_status(self, task_id: str) -> dict[str, Any]:
        """Check status of a queued task"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        status = self.agent_registry.task_queue.get_task_status(task_id)
        if not status:
            return {"success": False, "error": f"Task not found: {task_id}"}

        return {"success": True, **status}

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        """Get result of a completed task"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        result = self.agent_registry.task_queue.get_task_result(task_id)
        if not result:
            return {"success": False, "error": f"Task not found or not completed: {task_id}"}

        if "error" in result and result.get("status") != "completed":
            return {"success": False, "error": result["error"], "status": result.get("status")}

        return {"success": True, "result": result}

    def list_queued_tasks(self, agent_id: Optional[str] = None) -> dict[str, Any]:
        """List queued/running tasks"""
        if not self.agent_registry:
            return {"success": False, "error": "Agent registry not available"}

        tasks = self.agent_registry.task_queue.list_tasks(agent_id)
        return {"success": True, "tasks": tasks, "count": len(tasks)}


# Global tool instance
_agent_operations_tool: Optional[AgentOperations] = None


def initialize_agent_operations_tool(agent_registry) -> None:
    """Initialize the agent operations tool with agent registry"""
    global _agent_operations_tool
    _agent_operations_tool = AgentOperations(agent_registry)


async def agent_operations_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Agent operations MCP tool interface

    STRUCTURED OPERATIONS (Use these for normal operations):
    - list: List all agents with details
    - info: Get detailed information about a specific agent
    - stats: Get agent registry statistics
    - create: Create a new agent with specified name, description, and managed files
    - queue_task: Queue a task for async execution (PREFERRED for agent interactions)
    - task_status: Check status of queued task
    - task_result: Get result of completed task
    - list_tasks: List all queued/running tasks

    DEBUG OPERATIONS (Use only for troubleshooting):
    - debug_chat: Direct chat bypassing MCP architecture (DEBUG ONLY - avoid in normal use)
    """
    operation = args.get("operation")

    if not operation:
        return create_mcp_response(
            False,
            "Operation parameter required. STRUCTURED: list, info, stats, create, queue_task, task_status, task_result, list_tasks. DEBUG: debug_chat",
        )

    if not _agent_operations_tool:
        return create_mcp_response(False, "Agent operations tool not initialized. Contact system administrator.")

    try:
        if operation == "list":
            result = _agent_operations_tool.list_agents()
            if result["success"]:
                return create_mcp_response(True, result["response_text"])
            else:
                return create_mcp_response(False, result.get("error", "Operation failed"))

        elif operation == "info":
            agent_id = args.get("agent_id", "")
            if not agent_id:
                return create_mcp_response(False, "agent_id parameter required for info operation")

            result = _agent_operations_tool.get_agent_info(agent_id)
            if result["success"]:
                agent = result["agent"]
                info_text = f"**Agent: {agent['name']}**\n"
                info_text += f"ID: {agent['id']}\n"
                if agent["description"]:
                    info_text += f"Description: {agent['description']}\n"
                info_text += f"Files: {agent['files_count']}\n"
                info_text += f"Interactions: {agent['interactions']}\n"
                info_text += f"Success Rate: {agent['success_rate']:.1%}\n"
                if "status" in agent:
                    info_text += f"Status: {agent['status']}\n"
                if agent["managed_files"]:
                    info_text += f"Managed Files: {', '.join(agent['managed_files'])}"
                return create_mcp_response(True, info_text)
            else:
                error_msg = result.get("error", "Failed to get agent info")
                return create_mcp_response(False, error_msg)

        elif operation == "stats":
            result = _agent_operations_tool.get_registry_stats()
            if result["success"]:
                stats = result["stats"]
                stats_text = "**Agent Registry Statistics:**\n"
                stats_text += f"Total Agents: {stats.get('total_agents', 0)}\n"
                stats_text += f"Managed Files: {stats.get('managed_files', 0)}\n"
                stats_text += f"Total Interactions: {stats.get('total_interactions', 0)}\n"
                stats_text += f"Queued Tasks: {stats.get('queued_tasks', 0)}\n"
                stats_text += f"Active Tasks: {stats.get('active_tasks', 0)}\n"
                stats_text += f"Registry Integrity: {'✅ Good' if stats.get('integrity', False) else '❌ Issues'}"
                return create_mcp_response(True, stats_text)
            else:
                return create_mcp_response(False, result.get("error", "Operation failed"))

        elif operation == "create":
            name = args.get("name", "")
            description = args.get("description", "")
            specialized_files = args.get("specialized_files", [])

            # Debug: Log what we received
            logger.info(
                f"CREATE AGENT DEBUG - specialized_files: {specialized_files} (type: {type(specialized_files)})"
            )

            # Fix: Ensure specialized_files is a proper list
            if isinstance(specialized_files, str):
                # If it's a JSON string, try to parse it
                if specialized_files.startswith("[") and specialized_files.endswith("]"):
                    try:
                        import json

                        specialized_files = json.loads(specialized_files)
                    except json.JSONDecodeError:
                        # If parsing fails, treat as single file
                        specialized_files = [specialized_files]
                else:
                    # If it's a regular string, treat as single file
                    specialized_files = [specialized_files]
            elif not isinstance(specialized_files, list):
                # If it's neither string nor list, make it an empty list
                specialized_files = []

            logger.info(f"CREATE AGENT DEBUG - specialized_files after fix: {specialized_files}")

            if not name:
                return create_mcp_response(False, "name parameter required for create operation")

            if not description:
                return create_mcp_response(False, "description parameter required for create operation")

            result = _agent_operations_tool.create_agent(name, description, specialized_files)

            if result["success"]:
                return create_mcp_response(True, result["response_text"])
            else:
                return create_mcp_response(False, result.get("error", "Operation failed"))

        elif operation == "debug_chat":
            agent_id = args.get("agent_id", "")
            message = args.get("message", "")
            task_type = args.get("task_type", "conversation")

            if not agent_id:
                return create_mcp_response(False, "agent_id parameter required for debug_chat operation")

            if not message:
                return create_mcp_response(False, "message parameter required for debug_chat operation")

            result = await _agent_operations_tool.debug_chat_with_agent(agent_id, message, task_type)

            if result["success"]:
                response_text = f"**🐛 DEBUG CHAT - Agent Response from {result['agent_id']}:**\n\n{result['content']}\n\n"
                response_text += f"**Task Type:** {result['task_type']}\n"
                response_text += f"**Timestamp:** {result['timestamp']}\n"
                if result["files_modified"]:
                    response_text += f"**Files Modified:** {', '.join(result['files_modified'])}\n\n"
                response_text += "⚠️  **Note:** This was a direct debug chat bypassing the MCP architecture. Use queue_task for normal operations."
                return create_mcp_response(True, response_text)
            else:
                error_msg = result.get("error", result.get("content", "Unknown error occurred"))
                return create_mcp_response(False, error_msg)

        elif operation == "queue_task":
            agent_id = args.get("agent_id", "")
            message = args.get("message", "")
            task_type = args.get("task_type", "conversation")

            if not agent_id:
                return create_mcp_response(False, "agent_id parameter required")
            if not message:
                return create_mcp_response(False, "message parameter required")

            result = _agent_operations_tool.queue_agent_task(agent_id, message, task_type)

            if result["success"]:
                response_text = "**Task Queued Successfully**\n\n"
                response_text += f"🎫 **Task ID:** {result['task_id']}\n"
                response_text += f"📊 **Status:** {result['status']}\n"
                response_text += f"💬 **Message:** {result['message']}"
                return create_mcp_response(True, response_text)
            else:
                return create_mcp_response(False, result.get("error", "Failed to queue task"))

        elif operation == "task_status":
            task_id = args.get("task_id", "")

            if not task_id:
                return create_mcp_response(False, "task_id parameter required")

            result = _agent_operations_tool.check_task_status(task_id)

            if result["success"]:
                response_text = f"**Task Status: {result['status']}**\n\n"
                response_text += f"🎫 Task ID: {result['task_id']}\n"
                response_text += f"🤖 Agent: {result['agent_id']}\n"
                response_text += f"📅 Created: {result['created_at']}\n"
                if result["completed_at"]:
                    response_text += f"✅ Completed: {result['completed_at']}\n"
                if result["error"]:
                    response_text += f"❌ Error: {result['error']}"
                return create_mcp_response(True, response_text)
            else:
                return create_mcp_response(False, result.get("error", "Failed to get status"))

        elif operation == "task_result":
            task_id = args.get("task_id", "")

            if not task_id:
                return create_mcp_response(False, "task_id parameter required")

            result = _agent_operations_tool.get_task_result(task_id)

            if result["success"]:
                task_result = result["result"]
                response_text = f"**Task Result**\n\n{task_result.get('content', 'No content')}\n\n"
                if task_result.get("files_modified"):
                    response_text += f"**Files Modified:** {', '.join(task_result['files_modified'])}"
                return create_mcp_response(True, response_text)
            else:
                return create_mcp_response(False, result.get("error", "Failed to get result"))

        elif operation == "list_tasks":
            agent_id = args.get("agent_id")  # Optional filter

            result = _agent_operations_tool.list_queued_tasks(agent_id)

            if result["success"]:
                tasks = result["tasks"]
                if not tasks:
                    return create_mcp_response(True, "No active tasks")

                response_text = f"**Active Tasks ({result['count']})**\n\n"
                for task in tasks[:10]:  # Show max 10
                    response_text += f"🎫 {task['task_id']} - {task['status']}\n"
                    response_text += f"   Agent: {task['agent_id'][:8]}...\n"
                    response_text += f"   Created: {task['created_at']}\n\n"

                return create_mcp_response(True, response_text)
            else:
                return create_mcp_response(False, result.get("error", "Failed to list tasks"))

        else:
            return create_mcp_response(
                False,
                f"Unknown operation '{operation}'. STRUCTURED: list, info, stats, create, queue_task, task_status, task_result, list_tasks. DEBUG: debug_chat",
            )

    except Exception as e:
        return handle_exception(e, "Agent Operations Tool")
