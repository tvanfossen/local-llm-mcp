# File: ~/Projects/local-llm-mcp/api/websocket_handler.py
"""
WebSocket Handler for Real-time Communication

Responsibilities:
- WebSocket connection management
- Real-time agent communication
- Streaming response handling
- Connection state management
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Set

from starlette.websockets import WebSocket, WebSocketDisconnect

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import TaskType, create_standard_request, ResponseStatus

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """
    Manages WebSocket connections for real-time agent interactions
    
    Provides real-time streaming communication with agents,
    connection management, and broadcast capabilities.
    """
    
    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_agents: Dict[str, str] = {}  # connection_id -> agent_id
    
    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        await websocket.accept()
        connection_id = str(uuid.uuid4())[:8]
        self.active_connections[connection_id] = websocket
        
        logger.info(f"WebSocket connected: {connection_id}")
        
        try:
            # Send connection confirmation
            await websocket.send_json({
                "type": "connection_established",
                "connection_id": connection_id,
                "message": "Connected to Standardized Agent LLM Server",
                "features": ["real_time_chat", "streaming_responses", "agent_management"],
                "agents_available": len(self.agent_registry.agents)
            })
            
            # Handle messages
            while True:
                data = await websocket.receive_json()
                await self._handle_websocket_message(websocket, connection_id, data)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {connection_id}: {e}")
            await self._send_error(websocket, f"Connection error: {str(e)}")
        finally:
            await self._cleanup_connection(connection_id)
    
    async def _handle_websocket_message(self, websocket: WebSocket, connection_id: str, data: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        message_type = data.get("type", "unknown")
        
        try:
            if message_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})
            
            elif message_type == "list_agents":
                await self._ws_list_agents(websocket)
            
            elif message_type == "get_agent_info":
                await self._ws_get_agent_info(websocket, data)
            
            elif message_type == "chat_agent":
                await self._ws_chat_agent(websocket, connection_id, data)
            
            elif message_type == "stream_chat_agent":
                await self._ws_stream_chat_agent(websocket, connection_id, data)
            
            elif message_type == "create_agent":
                await self._ws_create_agent(websocket, data)
            
            else:
                await self._send_error(websocket, f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message {message_type}: {e}")
            await self._send_error(websocket, f"Message handling error: {str(e)}")
    
    async def _ws_list_agents(self, websocket: WebSocket):
        """List agents via WebSocket"""
        try:
            agents = self.agent_registry.list_agents()
            agents_data = []
            
            for agent in agents:
                agents_data.append({
                    "id": agent.state.agent_id,
                    "name": agent.state.name,
                    "description": agent.state.description,
                    "managed_file": agent.state.managed_file,
                    "last_activity": agent.state.last_activity,
                    "total_interactions": agent.state.total_interactions
                })
            
            await websocket.send_json({
                "type": "agents_list",
                "agents": agents_data,
                "file_ownership": self.agent_registry.get_file_ownership_map()
            })
            
        except Exception as e:
            await self._send_error(websocket, f"Failed to list agents: {str(e)}")
    
    async def _ws_get_agent_info(self, websocket: WebSocket, data: Dict[str, Any]):
        """Get agent info via WebSocket"""
        try:
            agent_id = data.get("agent_id")
            if not agent_id:
                await self._send_error(websocket, "Missing agent_id")
                return
            
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                await self._send_error(websocket, f"Agent {agent_id} not found")
                return
            
            summary = agent.get_summary()
            
            await websocket.send_json({
                "type": "agent_info",
                "agent_id": agent_id,
                "info": summary
            })
            
        except Exception as e:
            await self._send_error(websocket, f"Failed to get agent info: {str(e)}")
    
    async def _ws_chat_agent(self, websocket: WebSocket, connection_id: str, data: Dict[str, Any]):
        """Non-streaming chat with agent via WebSocket"""
        try:
            agent_id = data.get("agent_id")
            message = data.get("message")
            
            if not agent_id or not message:
                await self._send_error(websocket, "Missing agent_id or message")
                return
            
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                await self._send_error(websocket, f"Agent {agent_id} not found")
                return
            
            if not self.llm_manager.model_loaded:
                await self._send_error(websocket, "Model not loaded")
                return
            
            # Create request
            agent_request = create_standard_request(
                task_type=TaskType(data.get("task_type", "update")),
                instruction=message,
                context=data.get("context"),
                parameters=data.get("parameters", {})
            )
            
            # Generate response
            prompt = agent.build_context_prompt(agent_request)
            agent_response, metrics = self.llm_manager.generate_response(prompt)
            
            if agent_response.file_content and agent_response.status == ResponseStatus.SUCCESS:
                try:
                    if agent_response.file_content.filename == agent.state.managed_file:
                        success = agent.write_managed_file(agent_response.file_content.content)
                        if success:
                            logger.info(f"✅ WebSocket: Agent {agent.state.agent_id} wrote file: {agent.state.managed_file}")
                            agent_response.changes_made.append("File written to disk")
                        else:
                            logger.error(f"❌ WebSocket: Agent {agent.state.agent_id} failed to write file")
                            agent_response.warnings.append("File content generated but disk write failed")
                    else:
                        agent_response.warnings.append(f"Filename mismatch: generated {agent_response.file_content.filename}, manages {agent.state.managed_file}")
                except Exception as e:
                    logger.error(f"WebSocket file writing error for agent {agent.state.agent_id}: {e}")
                    agent_response.warnings.append(f"File write failed: {str(e)}")


            # Update agent
            agent.update_activity(agent_request.task_type)
            agent.update_success_rate(agent_response.status.value == "success")
            agent.add_conversation(agent_request, agent_response)
            
            # Save state
            self.agent_registry.save_registry()
            
            # Send response
            await websocket.send_json({
                "type": "chat_response",
                "agent_id": agent_id,
                "agent_name": agent.state.name,
                "response": agent_response.model_dump(),
                "performance": metrics
            })
            
        except Exception as e:
            await self._send_error(websocket, f"Chat failed: {str(e)}")
    
    async def _ws_stream_chat_agent(self, websocket: WebSocket, connection_id: str, data: Dict[str, Any]):
        """Streaming chat with agent via WebSocket"""
        try:
            agent_id = data.get("agent_id")
            message = data.get("message")
            
            if not agent_id or not message:
                await self._send_error(websocket, "Missing agent_id or message")
                return
            
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                await self._send_error(websocket, f"Agent {agent_id} not found")
                return
            
            if not self.llm_manager.model_loaded:
                await self._send_error(websocket, "Model not loaded")
                return
            
            # Store agent association for this connection
            self.connection_agents[connection_id] = agent_id
            
            # Create request
            agent_request = create_standard_request(
                task_type=TaskType(data.get("task_type", "update")),
                instruction=message,
                context=data.get("context"),
                parameters=data.get("parameters", {})
            )
            
            # Send start notification
            await websocket.send_json({
                "type": "stream_start",
                "agent_id": agent_id,
                "agent_name": agent.state.name,
                "task_type": agent_request.task_type.value
            })
            
            # Build prompt
            prompt = agent.build_context_prompt(agent_request)
            
            # Stream response
            async for stream_data in self.llm_manager.generate_streaming_response(
                prompt,
                temperature=data.get("temperature"),
                max_tokens=data.get("max_tokens")
            ):
                if stream_data["type"] == "chunk":
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "agent_id": agent_id,
                        "content": stream_data["content"],
                        "tokens_so_far": stream_data.get("tokens_so_far", 0)
                    })
                
                elif stream_data["type"] == "complete":
                    agent_response = stream_data["response"]
                    metrics = stream_data["metrics"]
                    
                    # Update agent
                    agent.update_activity(agent_request.task_type)
                    agent.update_success_rate(agent_response.status.value == "success")
                    agent.add_conversation(agent_request, agent_response)
                    
                    # Save state
                    self.agent_registry.save_registry()
                    
                    await websocket.send_json({
                        "type": "stream_complete",
                        "agent_id": agent_id,
                        "response": agent_response.model_dump(),
                        "performance": metrics
                    })
                    break
                
                elif stream_data["type"] == "error":
                    await self._send_error(websocket, stream_data["message"])
                    break
            
        except Exception as e:
            await self._send_error(websocket, f"Streaming chat failed: {str(e)}")
    
    async def _ws_create_agent(self, websocket: WebSocket, data: Dict[str, Any]):
        """Create agent via WebSocket"""
        try:
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
                initial_context=data.get("initial_context", "")
            )
            
            if success:
                await websocket.send_json({
                    "type": "agent_created",
                    "agent": {
                        "id": agent.state.agent_id,
                        "name": agent.state.name,
                        "description": agent.state.description,
                        "managed_file": agent.state.managed_file,
                        "created_at": agent.state.created_at
                    }
                })
            else:
                await self._send_error(websocket, f"Agent creation failed: {error}")
                
        except Exception as e:
            await self._send_error(websocket, f"Failed to create agent: {str(e)}")
    
    async def _send_error(self, websocket: WebSocket, message: str):
        """Send error message via WebSocket"""
        try:
            await websocket.send_json({
                "type": "error",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to send WebSocket error: {e}")
    
    async def _cleanup_connection(self, connection_id: str):
        """Clean up WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if connection_id in self.connection_agents:
            del self.connection_agents[connection_id]
        
        logger.info(f"WebSocket connection cleaned up: {connection_id}")
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
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
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            "active_connections": len(self.active_connections),
            "connections_with_agents": len(self.connection_agents),
            "connection_ids": list(self.active_connections.keys())
        }