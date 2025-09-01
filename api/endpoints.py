# File: ~/Projects/local-llm-mcp/api/endpoints.py
"""API Endpoints for HTTP interface

Responsibilities:
- HTTP REST API endpoints for agent management
- Request/response handling and validation
- Integration with agent registry and LLM manager
- JSON response formatting
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
    """HTTP API endpoints for agent management"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

    async def list_agents(self, request: Request) -> JSONResponse:
        """GET /api/agents - List all agents"""
        try:
            agents = self.agent_registry.list_agents()
            agents_data = [
                {
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                    "description": agent.state.description,
                    "managed_file": agent.state.managed_file,
                    "last_activity": agent.state.last_activity,
                    "total_interactions": agent.state.total_interactions,
                    "success_rate": agent.state.success_rate,
                }
                for agent in agents
            ]

            return JSONResponse(
                {
                    "agents": agents_data,
                    "count": len(agents_data),
                    "file_ownership": self.agent_registry.get_file_ownership_map(),
                }
            )

        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return JSONResponse({"error": f"Failed to list agents: {e!s}"}, status_code=500)

    async def create_agent(self, request: Request) -> JSONResponse:
        """POST /api/agents - Create new agent"""
        try:
            data = await request.json()

            # Validate required fields
            validation_result = self._validate_create_agent_request(data)
            if validation_result["error"]:
                return JSONResponse({"error": validation_result["message"]}, status_code=validation_result["status"])

            # Create agent
            success, agent, error = self.agent_registry.create_agent(
                name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
                managed_file=data["managed_file"],
                initial_context=data.get("initial_context", ""),
            )

            # Return result based on success
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
                response_data = {"error": f"Agent creation failed: {error}"}
                status_code = 400

            return JSONResponse(response_data, status_code=status_code)

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return JSONResponse({"error": f"Failed to create agent: {e!s}"}, status_code=500)

    def _validate_create_agent_request(self, data: dict) -> dict:
        """Validate create agent request data"""
        required_fields = ["name", "description", "system_prompt", "managed_file"]
        for field in required_fields:
            if field not in data:
                return {"error": True, "message": f"Missing required field: {field}", "status": 400}

        return {"error": False}

    async def get_agent(self, request: Request) -> JSONResponse:
        """GET /api/agents/{agent_id} - Get agent details"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return JSONResponse({"error": f"Agent {agent_id} not found"}, status_code=404)

            summary = agent.get_summary()
            return JSONResponse(
                {
                    "agent": {
                        "id": agent.state.agent_id,
                        "name": agent.state.name,
                        "description": agent.state.description,
                        "managed_file": agent.state.managed_file,
                        "system_prompt": agent.state.system_prompt,
                        "context": agent.state.context,
                        "created_at": agent.state.created_at,
                        "last_activity": agent.state.last_activity,
                        "total_interactions": agent.state.total_interactions,
                        "success_rate": agent.state.success_rate,
                    },
                    "summary": summary,
                }
            )

        except Exception as e:
            logger.error(f"Failed to get agent: {e}")
            return JSONResponse({"error": f"Failed to get agent: {e!s}"}, status_code=500)

    async def delete_agent(self, request: Request) -> JSONResponse:
        """DELETE /api/agents/{agent_id} - Delete agent"""
        try:
            agent_id = request.path_params["agent_id"]
            success, error = self.agent_registry.delete_agent(agent_id)

            if success:
                return JSONResponse({"success": True, "message": f"Agent {agent_id} deleted"})

            return JSONResponse({"error": f"Deletion failed: {error}"}, status_code=400)

        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            return JSONResponse({"error": f"Failed to delete agent: {e!s}"}, status_code=500)

    async def chat_with_agent(self, request: Request) -> JSONResponse:
        """POST /api/agents/{agent_id}/chat - Chat with agent"""
        try:
            agent_id = request.path_params["agent_id"]
            data = await request.json()

            # Validate prerequisites
            validation_result = self._validate_chat_request(agent_id, data)
            if validation_result["error"]:
                return JSONResponse({"error": validation_result["message"]}, status_code=validation_result["status"])

            agent = validation_result["agent"]

            # Process chat
            chat_result = await self._process_agent_chat(agent, data)
            return JSONResponse(chat_result)

        except Exception as e:
            logger.error(f"Chat with agent failed: {e}")
            return JSONResponse({"error": f"Chat failed: {e!s}"}, status_code=500)

    def _validate_chat_request(self, agent_id: str, data: dict) -> dict:
        """Validate chat request - consolidated validation"""
        # Check for missing message
        message = data.get("message")
        if not message:
            return {"error": True, "message": "Missing message", "status": 400}

        # Check agent existence and model loading in single validation flow
        validation_issues = []

        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            validation_issues.append((f"Agent {agent_id} not found", 404))

        if not self.llm_manager.model_loaded:
            validation_issues.append(("Model not loaded", 503))

        # Return first validation issue if any exist
        if validation_issues:
            error_msg, status = validation_issues[0]
            return {"error": True, "message": error_msg, "status": status}

        return {"error": False, "agent": agent}

    async def _process_agent_chat(self, agent, data: dict) -> dict:
        """Process agent chat and return result"""
        # Create standardized request
        agent_request = create_standard_request(
            task_type=TaskType(data.get("task_type", "update")),
            instruction=data["message"],
            context=data.get("context"),
            parameters=data.get("parameters", {}),
        )

        # Generate response
        prompt = agent.build_context_prompt(agent_request)
        agent_response, metrics = self.llm_manager.generate_response(prompt)

        # Handle file content
        if agent_response.file_content and agent_response.status == ResponseStatus.SUCCESS:
            self._handle_file_content(agent, agent_response)

        # Update agent state
        self._update_agent_state(agent, agent_request, agent_response)

        return {
            "success": True,
            "agent_id": agent.state.agent_id,
            "response": agent_response.model_dump(),
            "performance": metrics,
        }

    def _handle_file_content(self, agent, agent_response):
        """Handle file content writing"""
        try:
            if agent_response.file_content.filename == agent.state.managed_file:
                success = agent.write_managed_file(agent_response.file_content.content)
                if success:
                    logger.info(f"Agent {agent.state.agent_id} wrote file: {agent.state.managed_file}")
                    agent_response.changes_made.append("File written to disk")
                else:
                    logger.error(f"Agent {agent.state.agent_id} failed to write file")
                    agent_response.warnings.append("File content generated but disk write failed")
            else:
                agent_response.warnings.append(
                    f"Filename mismatch: generated {agent_response.file_content.filename}, "
                    f"manages {agent.state.managed_file}"
                )
        except Exception as e:
            logger.error(f"File writing error for agent {agent.state.agent_id}: {e}")
            agent_response.warnings.append(f"File write failed: {e!s}")

    def _update_agent_state(self, agent, agent_request, agent_response):
        """Update agent state after processing"""
        agent.update_activity(agent_request.task_type)
        agent.update_success_rate(agent_response.status.value == "success")
        agent.add_conversation(agent_request, agent_response)
        self.agent_registry.save_registry()

    async def get_agent_file(self, request: Request) -> JSONResponse:
        """GET /api/agents/{agent_id}/file - Get agent's managed file content"""
        try:
            agent_id = request.path_params["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return JSONResponse({"error": f"Agent {agent_id} not found"}, status_code=404)

            file_content = agent.read_managed_file()
            return JSONResponse(
                {
                    "agent_id": agent_id,
                    "filename": agent.state.managed_file,
                    "content": file_content,
                    "exists": file_content is not None,
                    "size": len(file_content) if file_content else 0,
                }
            )

        except Exception as e:
            logger.error(f"Failed to get agent file: {e}")
            return JSONResponse({"error": f"Failed to get file: {e!s}"}, status_code=500)

    async def system_status(self, request: Request) -> JSONResponse:
        """GET /api/system/status - Get system status"""
        try:
            # Get model info
            model_info = self.llm_manager.get_model_info()
            performance = self.llm_manager.get_performance_summary()

            # Get registry stats
            registry_stats = self.agent_registry.get_registry_stats()

            return JSONResponse(
                {
                    "system": {
                        "status": "healthy",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    "model": {
                        "loaded": model_info["model_loaded"],
                        "path": model_info.get("model_path"),
                        "performance": performance,
                        "configuration": model_info.get("configuration", {}),
                    },
                    "agents": {
                        "total": registry_stats["total_agents"],
                        "managed_files": registry_stats["managed_files"],
                        "total_interactions": registry_stats["total_interactions"],
                        "average_success_rate": registry_stats["average_success_rate"],
                        "most_active": registry_stats.get("most_active_agent"),
                    },
                }
            )

        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return JSONResponse({"error": f"System status failed: {e!s}"}, status_code=500)
