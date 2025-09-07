# File: ~/Projects/local-llm-mcp/src/api/websocket/handler/connection_manager.py
"""WebSocket Connection Manager

Responsibilities:
- Track active WebSocket connections
- Manage connection-to-agent associations
- Provide broadcast capabilities
- Handle connection cleanup
"""

import logging
from typing import Dict, List, Optional

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and their associated agents"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_agents: Dict[str, str] = {}  # connection_id -> agent_id

    def add_connection(self, connection_id: str, websocket: WebSocket):
        """Add a new WebSocket connection"""
        self.active_connections[connection_id] = websocket
        logger.debug(f"Added connection: {connection_id}")

    def remove_connection(self, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if connection_id in self.connection_agents:
            del self.connection_agents[connection_id]

        logger.debug(f"Removed connection: {connection_id}")

    def associate_agent(self, connection_id: str, agent_id: str):
        """Associate a connection with an agent"""
        if connection_id in self.active_connections:
            self.connection_agents[connection_id] = agent_id
            logger.debug(f"Associated connection {connection_id} with agent {agent_id}")

    def get_agent_for_connection(self, connection_id: str) -> Optional[str]:
        """Get the agent ID associated with a connection"""
        return self.connection_agents.get(connection_id)

    def get_connections_for_agent(self, agent_id: str) -> List[str]:
        """Get all connection IDs associated with an agent"""
        return [conn_id for conn_id, associated_agent in self.connection_agents.items() if associated_agent == agent_id]

    def get_active_connections(self) -> List[str]:
        """Get list of all active connection IDs"""
        return list(self.active_connections.keys())

    def get_connection(self, connection_id: str) -> Optional[WebSocket]:
        """Get WebSocket for a specific connection ID"""
        return self.active_connections.get(connection_id)

    async def send_to_connection(self, connection_id: str, message: dict):
        """Send message to a specific connection"""
        websocket = self.get_connection(connection_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                # Remove broken connection
                self.remove_connection(connection_id)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all active connections"""
        disconnected_connections = []

        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection_id}: {e}")
                disconnected_connections.append(connection_id)

        # Clean up broken connections
        for connection_id in disconnected_connections:
            self.remove_connection(connection_id)

    async def broadcast_to_agent_connections(self, agent_id: str, message: dict):
        """Broadcast message to all connections associated with an agent"""
        agent_connections = self.get_connections_for_agent(agent_id)

        for connection_id in agent_connections:
            await self.send_to_connection(connection_id, message)

    def get_connection_stats(self) -> dict:
        """Get statistics about active connections"""
        return {
            "total_connections": len(self.active_connections),
            "connections_with_agents": len(self.connection_agents),
            "agents_in_use": len(set(self.connection_agents.values())),
            "connection_ids": list(self.active_connections.keys()),
        }
