# File: ~/Projects/local-llm-mcp/api/websocket_handler.py
"""WebSocket Handler for Real-time Communication

Responsibilities:
- WebSocket connection management
- Real-time agent communication
- Streaming response handling
- Connection state management
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import ResponseStatus, TaskType, create_standard_request

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Manages WebSocket connections for real-time agent interactions"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_agents: dict[str, str] = {}  # connection_id -> agent_id

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        await websocket.accept()
        connection_id = str(uuid.uuid4())[:8]
        self.active_connections[connection_id] = websocket

        logger.info(f"WebSocket connected: {connection_id}")

        try:
            # Send connection confirmation
            await self._send_connection_established(websocket, connection_id)

            # Handle messages in main loop
            await self._message_loop(websocket, connection_id)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {connection_id}: {e}")
            await self._send_error(websocket, f"Connection error: {e!s}")
        finally:
            await self._cleanup_connection(connection_id)

    async def _send_connection_established(self, websocket: WebSocket, connection_id: str):
        """Send connection established message"""
        await websocket.send_json(
            {
                "type": "connection_established",
                "connection_id": connection_id,
                "message": "Connected to Standardized Agent LLM Server",
                "features": ["real_time_chat", "streaming_responses", "agent_management"],
                "agents_available": len(self.agent_registry.agents),
            }
        )

    async def _message_loop(self, websocket: WebSocket, connection_id: str):
        """Main message handling loop"""
        while True:
            data = await websocket.receive_json()
            await self._handle_websocket_message(websocket, connection_id, data)

    async def _handle_websocket_message(
        self, websocket: WebSocket, connection_id: str, data: dict[str, Any]
    ):
        """Handle incoming WebSocket message - simplified dispatch with reduced complexity"""
        message_type = data.get("type", "unknown")

        try:
            # Use dictionary dispatch for known message types
            message_handlers = {
                "ping": self._handle_ping,
                "list_agents": self._ws_list_agents,
                "get_agent_info": self._ws_get_agent_info,
                "chat_agent": self._ws_chat_agent,
                "stream_chat_agent": self._ws_stream_chat_agent,
                "create_agent": self._ws_create_agent,
            }

            handler = message_handlers.get(message_type)

            if handler:
                await self._execute_message_handler(
                    handler, websocket, connection_id, data, message_type
                )
            else:
                await self._send_error(websocket, f"Unknown message type: {message_type}")

        except Exception as e:
            logger.error(f"Error handling WebSocket message {message_type}: {e}")
            await self._send_error(websocket, f"Message handling error: {e!s}")

    async def _execute_message_handler(self, handler, websocket, connection_id, data, message_type):
        """Execute message handler with appropriate parameters"""
        if message_type == "ping":
            await handler(websocket, data)
        else:
            await handler(websocket, connection_id, data)

    async def _handle_ping(self, websocket: WebSocket, data: dict[str, Any]):
        """Handle ping message"""
        await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})

    async def _ws_list_agents(self, websocket: WebSocket, connection_id: str, data: dict[str, Any]):
        """List agents via WebSocket"""
        try:
            agents = self.agent_registry.list_agents()
            agents_data = self._build_agents_data(agents)

            await websocket.send_json(
                {
                    "type": "agents_list",
                    "agents": agents_data,
                    "file_ownership": self.agent_registry.get_file_ownership_map(),
                }
            )

        except Exception as e:
            await self._send_error(websocket, f"Failed to list agents: {e!s}")

    def _build_agents_data(self, agents) -> list[dict]:
        """Build agents data for list response"""
        agents_data = []
        for agent in agents:
            agents_data.append(
                {
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                    "description": agent.state.description,
                    "managed_file": agent.state.managed_file,
                    "last_activity": agent.state.last_activity,
                    "total_interactions": agent.state.total_interactions,
                }
            )
        return agents_data

    async def _ws_get_agent_info(
        self, websocket: WebSocket, connection_id: str, data: dict[str, Any]
    ):
        """Get agent info via WebSocket"""
        agent_id = data.get("agent_id")
        if not agent_id:
            await self._send_error(websocket, "Missing agent_id")
            return

        try:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                await self._send_error(websocket, f"Agent {agent_id} not found")
                return

            summary = agent.get_summary()

            await websocket.send_json(
                {
                    "type": "agent_info",
                    "agent_id": agent_id,
                    "info": summary,
                }
            )

        except Exception as e:
            await self._send_error(websocket, f"Failed to get agent info: {e!s}")

    async def _ws_chat_agent(self, websocket: WebSocket, connection_id: str, data: dict[str, Any]):
        """Non-streaming chat with agent via WebSocket"""
        try:
            # Validate inputs
            validation_result = self._validate_chat_inputs(data)
            if validation_result["error"]:
                await self._send_error(websocket, validation_result["message"])
                return

            agent = validation_result["agent"]

            # Process chat
            chat_result = await self._process_agent_chat(agent, data)

            # Send response
            await websocket.send_json(chat_result)

        except Exception as e:
            await self._send_error(websocket, f"Chat failed: {e!s}")

    def _validate_chat_inputs(self, data: dict[str, Any]) -> dict:
        """Validate chat inputs and return validation result"""
        agent_id = data.get("agent_id")
        message = data.get("message")

        # Consolidated validation checks
        if not agent_id or not message:
            return {"error": True, "message": "Missing agent_id or message", "agent": None}

        # Check agent and model in single flow
        validation_issues = []

        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            validation_issues.append(f"Agent {agent_id} not found")

        if not self.llm_manager.model_loaded:
            validation_issues.append("Model not loaded")

        # Return first issue if any exist
        if validation_issues:
            return {"error": True, "message": validation_issues[0], "agent": None}

        return {"error": False, "message": None, "agent": agent}

    async def _process_agent_chat(self, agent, data: dict[str, Any]) -> dict:
        """Process agent chat and return formatted result"""
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

        # Handle file content if present
        self._handle_agent_file_content(agent, agent_response)

        # Update agent state
        self._update_agent_state(agent, agent_request, agent_response)

        return {
            "type": "chat_response",
            "agent_id": agent.state.agent_id,
            "agent_name": agent.state.name,
            "response": agent_response.model_dump(),
            "performance": metrics,
        }

    def _handle_agent_file_content(self, agent, agent_response):
        """Handle file content processing for agent"""
        if agent_response.file_content and agent_response.status == ResponseStatus.SUCCESS:
            try:
                if agent_response.file_content.filename == agent.state.managed_file:
                    success = agent.write_managed_file(agent_response.file_content.content)
                    if success:
                        logger.info(
                            f"✅ WebSocket: Agent {agent.state.agent_id} wrote file: {agent.state.managed_file}"
                        )
                        agent_response.changes_made.append("File written to disk")
                    else:
                        logger.error(
                            f"❌ WebSocket: Agent {agent.state.agent_id} failed to write file"
                        )
                        agent_response.warnings.append(
                            "File content generated but disk write failed"
                        )
                else:
                    filename_mismatch_msg = (
                        f"Filename mismatch: generated {agent_response.file_content.filename}, "
                        f"manages {agent.state.managed_file}"
                    )
                    agent_response.warnings.append(filename_mismatch_msg)
            except Exception as e:
                logger.error(f"WebSocket file writing error for agent {agent.state.agent_id}: {e}")
                agent_response.warnings.append(f"File write failed: {e!s}")

    def _update_agent_state(self, agent, agent_request, agent_response):
        """Update agent state after processing"""
        agent.update_activity(agent_request.task_type)
        agent.update_success_rate(agent_response.status.value == "success")
        agent.add_conversation(agent_request, agent_response)
        self.agent_registry.save_registry()

    async def _ws_stream_chat_agent(
        self, websocket: WebSocket, connection_id: str, data: dict[str, Any]
    ):
        """Streaming chat with agent via WebSocket"""
        try:
            # Validate inputs
            validation_result = self._validate_chat_inputs(data)
            if validation_result["error"]:
                await self._send_error(websocket, validation_result["message"])
                return

            agent = validation_result["agent"]

            # Store agent association for this connection
            self.connection_agents[connection_id] = agent.state.agent_id

            # Process streaming chat
            await self._process_streaming_chat(websocket, agent, data)

        except Exception as e:
            await self._send_error(websocket, f"Streaming chat failed: {e!s}")

    async def _process_streaming_chat(self, websocket: WebSocket, agent, data: dict[str, Any]):
        """Process streaming chat with agent"""
        # Create request
        agent_request = create_standard_request(
            task_type=TaskType(data.get("task_type", "update")),
            instruction=data["message"],
            context=data.get("context"),
            parameters=data.get("parameters", {}),
        )

        # Send start notification
        await websocket.send_json(
            {
                "type": "stream_start",
                "agent_id": agent.state.agent_id,
                "agent_name": agent.state.name,
                "task_type": agent_request.task_type.value,
            }
        )

        # Build prompt
        prompt = agent.build_context_prompt(agent_request)

        # Stream response
        await self._handle_streaming_response(websocket, agent, agent_request, prompt, data)

    async def _handle_streaming_response(
        self, websocket: WebSocket, agent, agent_request, prompt: str, data: dict[str, Any]
    ):
        """Handle the streaming response from LLM"""
        async for stream_data in self.llm_manager.generate_streaming_response(
            prompt,
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
        ):
            await self._process_stream_chunk(websocket, agent, agent_request, stream_data)

    async def _process_stream_chunk(
        self, websocket: WebSocket, agent, agent_request, stream_data: dict
    ):
        """Process individual stream chunk"""
        if stream_data["type"] == "chunk":
            await websocket.send_json(
                {
                    "type": "stream_chunk",
                    "agent_id": agent.state.agent_id,
                    "content": stream_data["content"],
                    "tokens_so_far": stream_data.get("tokens_so_far", 0),
                }
            )

        elif stream_data["type"] == "complete":
            agent_response = stream_data["response"]
            metrics = stream_data["metrics"]

            # Update agent
            self._update_agent_state(agent, agent_request, agent_response)

            await websocket.send_json(
                {
                    "type": "stream_complete",
                    "agent_id": agent.state.agent_id,
                    "response": agent_response.model_dump(),
                    "performance": metrics,
                }
            )

        elif stream_data["type"] == "error":
            await self._send_error(websocket, stream_data["message"])

    async def _ws_create_agent(
        self, websocket: WebSocket, connection_id: str, data: dict[str, Any]
    ):
        """Create agent via WebSocket"""
        try:
            # Validate required fields
            required_fields = ["name", "description", "system_prompt", "managed_file"]
            for field in required_fields:
                if field not in data:
                    await self._send_error(websocket, f"Missing required field: {field}")
                    return

            success, agent, error = self.agent_registry.create_agent(
                name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
                managed_file=data["managed_file"],
                initial_context=data.get("initial_context", ""),
            )

            if success:
                await websocket.send_json(
                    {
                        "type": "agent_created",
                        "agent": {
                            "id": agent.state.agent_id,
                            "name": agent.state.name,
                            "description": agent.state.description,
                            "managed_file": agent.state.managed_file,
                            "created_at": agent.state.created_at,
                        },
                    }
                )
            else:
                await self._send_error(websocket, f"Agent creation failed: {error}")

        except Exception as e:
            await self._send_error(websocket, f"Failed to create agent: {e!s}")

    async def _send_error(self, websocket: WebSocket, message: str):
        """Send error message via WebSocket"""
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket error: {e}")

    async def _cleanup_connection(self, connection_id: str):
        """Clean up WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if connection_id in self.connection_agents:
            del self.connection_agents[connection_id]

        logger.info(f"WebSocket connection cleaned up: {connection_id}")

    async def broadcast_to_all(self, message: dict[str, Any]):
        """Broadcast message to all active WebSocket connections"""
        if not self.active_connections:
            return

        disconnected = []

        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection {connection_id}: {e}")
                disconnected.append(connection_id)

        # Clean up disconnected connections
        for connection_id in disconnected:
            await self._cleanup_connection(connection_id)

    def get_connection_stats(self) -> dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            "active_connections": len(self.active_connections),
            "connections_with_agents": len(self.connection_agents),
            "connection_ids": list(self.active_connections.keys()),
        }
