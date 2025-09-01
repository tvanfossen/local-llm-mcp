# File: ~/Projects/local-llm-mcp/api/endpoints.py
"""HTTP API Endpoints

Responsibilities:
- Direct HTTP API endpoints (for testing/debugging)
- JSON request/response handling
- Input validation and error handling
- Performance monitoring endpoints
"""

import logging
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import ResponseStatus, TaskType, create_standard_request

logger = logging.getLogger(__name__)


class APIEndpoints:
    """HTTP API endpoints for direct server interaction

    These endpoints provide a RESTful interface for testing and debugging,
    complementing the MCP interface used by Claude Code.
    """

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

    async def create_agent(self, request: Request) -> JSONResponse:
        """Create a new agent via HTTP API"""
        try:
            data = await request.json()

            # Validate required fields
            required_fields = ["name", "description", "system_prompt", "managed_file"]
            missing_field = next((field for field in required_fields if field not in data), None)

            if missing_field:
                return JSONResponse(
                    {"error": f"Missing required field: {missing_field}"},
                    status_code=400,
                )

            success, agent, error = self.agent_registry.create_agent(
                name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
                managed_file=data["managed_file"],
                initial_context=data.get("initial_context", ""),
            )

            if success:
                response_data = {
                    "success": True,
                    "agent": {
                        "id": agent.state.agent_id,
                        "name": agent.state.name,
                        "description": agent.state.description,
                        "managed_file": agent.state.managed_file,
                        "created_at": agent.state.created_at,
                    },
                }
                status_code = 201
            else:
                response_data = {"error": error}
                status_code = 409 if "conflict" in error.lower() else 400

            return JSONResponse(response_data, status_code=status_code)

        except Exception as e:
            logger.error(f"Create agent API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    async def list_agents(self, request: Request) -> JSONResponse:
        """List all agents via HTTP API"""
        try:
            agents = self.agent_registry.list_agents()

            agents_data = []
            for agent in agents:
                summary = agent.get_summary()
                agents_data.append(
                    {
                        "id": summary["agent_id"],
                        "name": summary["name"],
                        "description": summary["description"],
                        "managed_file": summary["managed_file"],
                        "file_exists": summary["file_exists"],
                        "file_size": summary["file_size"],
                        "total_interactions": summary["total_interactions"],
                        "success_rate": summary["success_rate"],
                        "last_activity": summary["last_activity"],
                    }
                )

            # Get registry stats
            stats = self.agent_registry.get_registry_stats()
            file_map = self.agent_registry.get_file_ownership_map()

            return JSONResponse(
                {
                    "success": True,
                    "agents": agents_data,
                    "statistics": {
                        "total_agents": stats["total_agents"],
                        "managed_files": stats["managed_files"],
                        "total_interactions": stats["total_interactions"],
                        "average_success_rate": stats["average_success_rate"],
                    },
                    "file_ownership": file_map,
                }
            )

        except Exception as e:
            logger.error(f"List agents API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    async def get_agent(self, request: Request) -> JSONResponse:
        """Get specific agent information via HTTP API"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404,
                )

            summary = agent.get_summary()

            # Get conversation history (last 10 entries)
            recent_conversations = []
            for entry in agent.conversation_history[-10:]:
                recent_conversations.append(
                    {
                        "timestamp": entry.timestamp,
                        "task_type": entry.request.task_type.value,
                        "instruction": (
                            entry.request.instruction[:100] + "..."
                            if len(entry.request.instruction) > 100
                            else entry.request.instruction
                        ),
                        "status": entry.response.status.value,
                        "tokens_used": entry.response.tokens_used,
                    }
                )

            return JSONResponse(
                {
                    "success": True,
                    "agent": {
                        "id": agent.state.agent_id,
                        "name": agent.state.name,
                        "description": agent.state.description,
                        "system_prompt": agent.state.system_prompt,
                        "managed_file": agent.state.managed_file,
                        "context": agent.state.context,
                        "created_at": agent.state.created_at,
                        "last_activity": agent.state.last_activity,
                        "total_interactions": agent.state.total_interactions,
                        "success_rate": agent.state.success_rate,
                        "workspace_path": str(agent.workspace_dir),
                    },
                    "file_info": {
                        "exists": summary["file_exists"],
                        "size": summary["file_size"],
                        "path": str(agent.get_managed_file_path()),
                    },
                    "recent_conversations": recent_conversations,
                }
            )

        except Exception as e:
            logger.error(f"Get agent API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    async def delete_agent(self, request: Request) -> JSONResponse:
        """Delete an agent via HTTP API"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404,
                )

            agent_name = agent.state.name
            managed_file = agent.state.managed_file

            success, error = self.agent_registry.delete_agent(agent_id)

            if success:
                response_data = {
                    "success": True,
                    "message": f"Agent {agent_name} deleted successfully",
                    "freed_file": managed_file,
                }
                status_code = 200
            else:
                response_data = {"error": error}
                status_code = 500

            return JSONResponse(response_data, status_code=status_code)

        except Exception as e:
            logger.error(f"Delete agent API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    async def chat_with_agent(self, request: Request) -> JSONResponse:
        """Chat with agent via HTTP API"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            # Validate agent existence and model status
            error_response = self._validate_agent_and_model(agent_id, agent)
            if error_response:
                return error_response

            data = await request.json()
            if "message" not in data:
                return JSONResponse(
                    {"error": "Missing required field: message"},
                    status_code=400,
                )

            # Process the chat request
            return await self._process_chat_request(agent, data)

        except Exception as e:
            logger.error(f"Chat with agent API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    def _validate_agent_and_model(self, agent_id: str, agent) -> JSONResponse | None:
        """Validate agent existence and model status"""
        if not agent:
            return JSONResponse(
                {"error": f"Agent {agent_id} not found"},
                status_code=404,
            )

        if not self.llm_manager.model_loaded:
            return JSONResponse(
                {"error": "Model not loaded"},
                status_code=503,
            )

        return None

    async def _process_chat_request(self, agent, data: dict) -> JSONResponse:
        """Process the actual chat request"""
        # Create standardized request
        agent_request = create_standard_request(
            task_type=TaskType(data.get("task_type", "update")),
            instruction=data["message"],
            context=data.get("context"),
            parameters=data.get("parameters", {}),
        )

        # Generate response
        prompt = agent.build_context_prompt(agent_request)
        agent_response, metrics = self.llm_manager.generate_response(
            prompt,
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p"),
            repeat_penalty=data.get("repeat_penalty"),
        )

        # Handle file content if present
        self._handle_file_content(agent, agent_response)

        # Update agent
        agent.update_activity(agent_request.task_type)
        agent.update_success_rate(agent_response.status.value == "success")
        agent.add_conversation(agent_request, agent_response)

        # Save state
        self.agent_registry.save_registry()

        return JSONResponse(
            {
                "success": True,
                "agent": {
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                },
                "request": {
                    "task_type": agent_request.task_type.value,
                    "instruction": agent_request.instruction,
                },
                "response": agent_response.model_dump(),
                "performance": metrics,
            }
        )

    def _handle_file_content(self, agent, agent_response):
        """Handle file content writing if present"""
        if agent_response.file_content and agent_response.status == ResponseStatus.SUCCESS:
            try:
                agent_response.file_content.filename = agent.state.managed_file
                success = agent.write_managed_file(agent_response.file_content.content)

                if success:
                    logger.info(
                        f"✅ Agent {agent.state.agent_id} wrote file: {agent.state.managed_file}"
                    )
                    agent_response.changes_made.append("File written to disk")
                    content = agent_response.file_content.content
                    logger.info(
                        f"File written: {len(content)} chars, {len(content.split(chr(10)))} lines"
                    )
                else:
                    logger.error(f"❌ Agent {agent.state.agent_id} failed to write file")
                    agent_response.warnings.append("File content generated but disk write failed")

            except Exception as e:
                logger.error(f"File writing error for agent {agent.state.agent_id}: {e}")
                agent_response.warnings.append(f"File write failed: {e!s}")

    async def get_agent_file(self, request: Request) -> JSONResponse:
        """Get agent's managed file content via HTTP API"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404,
                )

            file_content = agent.read_managed_file()
            file_path = agent.get_managed_file_path()

            return JSONResponse(
                {
                    "success": True,
                    "agent": {
                        "id": agent.state.agent_id,
                        "name": agent.state.name,
                        "managed_file": agent.state.managed_file,
                    },
                    "file": {
                        "name": agent.state.managed_file,
                        "path": str(file_path),
                        "exists": file_content is not None,
                        "size": len(file_content) if file_content else 0,
                        "content": file_content,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Get agent file API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )

    async def system_status(self, request: Request) -> JSONResponse:
        """Get comprehensive system status via HTTP API"""
        try:
            # Get model information
            model_info = self.llm_manager.get_model_info()
            performance = self.llm_manager.get_performance_summary()
            health = self.llm_manager.health_check()

            # Get agent registry information
            registry_stats = self.agent_registry.get_registry_stats()
            integrity_issues = self.agent_registry.validate_registry_integrity()

            return JSONResponse(
                {
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": {
                        "loaded": model_info["model_loaded"],
                        "path": model_info["model_path"],
                        "configuration": model_info["configuration"],
                        "performance": performance,
                        "health": health,
                    },
                    "agents": {
                        "statistics": registry_stats,
                        "integrity_issues": integrity_issues,
                        "file_ownership_map": self.agent_registry.get_file_ownership_map(),
                    },
                    "system": {
                        "cuda_optimized": True,
                        "json_schema_validation": True,
                        "one_agent_per_file": True,
                    },
                }
            )

        except Exception as e:
            logger.error(f"System status API error: {e}")
            return JSONResponse(
                {"error": f"Internal server error: {e!s}"},
                status_code=500,
            )
