"""WebSocket Message Handlers

Responsibilities:
- Handle different types of WebSocket messages
- Dispatch messages to appropriate handlers
- Manage WebSocket message routing
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WebSocketMessageHandlers:
    """Handles different types of WebSocket messages"""

    def __init__(self, agent_registry, llm_manager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

    async def dispatch_message(self, message_type: str, websocket, connection_id: str, data: dict):
        """Dispatch message to appropriate handler"""
        handler_map = {
            "ping": self._handle_ping,
            "list_agents": self._handle_list_agents,
            "get_agent_info": self._handle_get_agent_info,
        }

        handler = handler_map.get(message_type)
        if handler:
            await handler(websocket, connection_id, data)
        else:
            await self._handle_unknown(websocket, connection_id, message_type)

    async def _handle_ping(self, websocket, connection_id: str, data: dict):
        """Handle ping message"""
        await websocket.send_json({"type": "pong", "connection_id": connection_id, "timestamp": data.get("timestamp")})

    async def _handle_list_agents(self, websocket, connection_id: str, data: dict):
        """Handle list agents request"""
        agents = self.agent_registry.list_agents()
        await websocket.send_json({"type": "agents_list", "agents": [agent.to_dict() for agent in agents]})

    async def _handle_get_agent_info(self, websocket, connection_id: str, data: dict):
        """Handle get agent info request"""
        agent_id = data.get("agent_id")
        agent = self.agent_registry.get_agent(agent_id)

        if agent:
            await websocket.send_json({"type": "agent_info", "agent": agent.to_dict()})
        else:
            await websocket.send_json({"type": "error", "message": f"Agent not found: {agent_id}"})

    async def _handle_unknown(self, websocket, connection_id: str, message_type: str):
        """Handle unknown message type"""
        await websocket.send_json({"type": "error", "message": f"Unknown message type: {message_type}"})
