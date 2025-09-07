# File: ~/Projects/local-llm-mcp/src/api/websocket/handler/handler.py
"""WebSocket Handler - Main Connection Management

Responsibilities:
- WebSocket connection lifecycle management
- Message dispatch to appropriate handlers
- Connection state tracking
- Error handling and cleanup
"""

import logging
import uuid
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from src.api.websocket.handler.connection_manager import ConnectionManager
from src.api.websocket.handler.message_handlers import WebSocketMessageHandlers
from src.core.agents.registry.registry import AgentRegistry
from src.core.llm.manager.manager import LLMManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Manages WebSocket connections for real-time agent interactions"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.connection_manager = ConnectionManager()
        self.message_handlers = WebSocketMessageHandlers(agent_registry, llm_manager)

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        await websocket.accept()
        connection_id = str(uuid.uuid4())[:8]

        self.connection_manager.add_connection(connection_id, websocket)
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

    async def _handle_websocket_message(self, websocket: WebSocket, connection_id: str, data: dict[str, Any]):
        """Handle incoming WebSocket message"""
        message_type = data.get("type", "unknown")

        try:
            await self.message_handlers.dispatch_message(message_type, websocket, connection_id, data)
        except Exception as e:
            logger.error(f"Error handling WebSocket message {message_type}: {e}")
            await self._send_error(websocket, f"Message handling error: {e!s}")

    async def _send_error(self, websocket: WebSocket, message: str):
        """Send error message to WebSocket"""
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": message,
                    "timestamp": self._get_timestamp(),
                }
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def _cleanup_connection(self, connection_id: str):
        """Clean up connection resources"""
        self.connection_manager.remove_connection(connection_id)
        logger.debug(f"Connection {connection_id} cleaned up")

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    # Broadcast methods for external use
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all active connections"""
        await self.connection_manager.broadcast_to_all(message)

    async def send_to_connection(self, connection_id: str, message: dict):
        """Send message to specific connection"""
        await self.connection_manager.send_to_connection(connection_id, message)

    def get_active_connections(self) -> list[str]:
        """Get list of active connection IDs"""
        return self.connection_manager.get_active_connections()
