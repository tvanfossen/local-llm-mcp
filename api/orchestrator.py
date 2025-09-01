# File: ~/Projects/local-llm-mcp/api/orchestrator.py
"""
Orchestrator API Endpoints

Responsibilities:
- Authentication endpoints
- Test coverage validation endpoints
- Deployment management endpoints
- WebSocket support for real-time updates
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from starlette.websockets import WebSocket

from core.agent_registry import AgentRegistry
from core.security import SecurityManager
from core.deployment import DeploymentManager

logger = logging.getLogger(__name__)

class OrchestratorAPI:
    """
    API endpoints for the secure orchestration interface
    
    Provides authentication, testing, and deployment capabilities
    with real-time WebSocket updates.
    """
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        security_manager: SecurityManager,
        deployment_manager: DeploymentManager
    ):
        self.agent_registry = agent_registry
        self.security_manager = security_manager
        self.deployment_manager = deployment_manager
        self.active_websockets: Dict[str, WebSocket] = {}
        
    async def serve_orchestrator_ui(self, request: Request) -> FileResponse:
        """Serve the orchestrator HTML interface"""
        ui_path = Path(__file__).parent.parent / "static" / "orchestrator.html"
        if ui_path.exists():
            return FileResponse(ui_path)
        else:
            return JSONResponse(
                {"error": "Orchestrator UI not found"},
                status_code=404
            )
    
    async def generate_keys(self, request: Request) -> JSONResponse:
        """Generate new RSA key pair for client"""
        try:
            data = await request.json()
            client_name = data.get("client_name", "default_client")
            
            private_key, public_key = self.security_manager.generate_client_keys(client_name)
            
            return JSONResponse({
                "success": True,
                "client_name": client_name,
                "private_key": private_key,
                "public_key": public_key,
                "instructions": (
                    "Save the private key securely. You'll need it to authenticate. "
                    "The public key has been added to the server's authorized keys."
                )
            })
            
        except Exception as e:
            logger.error(f"Key generation failed: {e}")
            return JSONResponse(
                {"error": f"Key generation failed: {str(e)}"},
                status_code=500
            )
    
    async def authenticate(self, request: Request) -> JSONResponse:
        """Authenticate with private key"""
        try:
            data = await request.json()
            private_key = data.get("private_key")
            
            if not private_key:
                return JSONResponse(
                    {"error": "Private key required"},
                    status_code=400
                )
            
            success, session_token, error = self.security_manager.authenticate_with_private_key(private_key)
            
            if success:
                return JSONResponse({
                    "success": True,
                    "session_token": session_token,
                    "expires_in": 14400  # 4 hours
                })
            else:
                return JSONResponse(
                    {"error": f"Authentication failed: {error}"},
                    status_code=401
                )
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return JSONResponse(
                {"error": f"Authentication error: {str(e)}"},
                status_code=500
            )
    
    async def validate_session(self, request: Request) -> JSONResponse:
        """Validate current session"""
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Invalid authorization header"},
                    status_code=401
                )
            
            session_token = auth_header[7:]  # Remove "Bearer " prefix
            valid, session = self.security_manager.validate_session(session_token)
            
            if valid:
                return JSONResponse({
                    "valid": True,
                    "client": session["client_name"],
                    "authenticated_at": session["authenticated_at"],
                    "expires_at": session["expires_at"]
                })
            else:
                return JSONResponse(
                    {"valid": False},
                    status_code=401
                )
                
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return JSONResponse(
                {"error": f"Validation error: {str(e)}"},
                status_code=500
            )
    
    async def test_agent(self, request: Request) -> JSONResponse:
        """Run tests for an agent's file"""
        try:
            agent_id = request.path_params["agent_id"]
            
            # Validate session
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401
                )
            
            session_token = auth_header[7:]
            valid, session = self.security_manager.validate_session(session_token)
            if not valid:
                return JSONResponse(
                    {"error": "Invalid or expired session"},
                    status_code=401
                )
            
            # Get agent
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404
                )
            
            # Run test coverage validation
            logger.info(f"Running tests for agent {agent_id}")
            coverage_ok, coverage_percent, report = self.deployment_manager.validate_test_coverage(agent)
            
            # Broadcast to WebSocket clients
            await self._broadcast_ws({
                "type": "coverage_update",
                "agent_id": agent_id,
                "coverage": coverage_percent,
                "passed": coverage_ok
            })
            
            return JSONResponse({
                "success": True,
                "agent_id": agent_id,
                "agent_name": agent.state.name,
                "file": agent.state.managed_file,
                "coverage": coverage_percent,
                "coverage_ok": coverage_ok,
                "report": report
            })
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return JSONResponse(
                {"error": f"Test failed: {str(e)}"},
                status_code=500
            )
    
    async def stage_deployment(self, request: Request) -> JSONResponse:
        """Stage a deployment for approval"""
        try:
            data = await request.json()
            
            # Validate session
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401
                )
            
            session_token = auth_header[7:]
            
            # Get parameters
            agent_id = data.get("agent_id")
            target_path = data.get("target_path")
            
            if not agent_id or not target_path:
                return JSONResponse(
                    {"error": "agent_id and target_path required"},
                    status_code=400
                )
            
            # Get agent
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404
                )
            
            # Stage deployment
            success, deployment_id, deployment_info = self.deployment_manager.stage_deployment(
                agent,
                Path(target_path),
                session_token
            )
            
            if success:
                return JSONResponse({
                    "success": True,
                    "deployment_id": deployment_id,
                    "deployment": deployment_info
                })
            else:
                return JSONResponse(
                    {"error": deployment_info.get("error", "Staging failed")},
                    status_code=400
                )
                
        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return JSONResponse(
                {"error": f"Staging failed: {str(e)}"},
                status_code=500
            )
    
    async def deploy(self, request: Request) -> JSONResponse:
        """Execute a deployment"""
        try:
            data = await request.json()
            
            # Validate session
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401
                )
            
            session_token = auth_header[7:]
            
            # Get parameters
            agent_id = data.get("agent_id")
            target_path = data.get("target_path")
            file_path = data.get("file_path")
            
            if not all([agent_id, target_path, file_path]):
                return JSONResponse(
                    {"error": "agent_id, target_path, and file_path required"},
                    status_code=400
                )
            
            # Get agent
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return JSONResponse(
                    {"error": f"Agent {agent_id} not found"},
                    status_code=404
                )
            
            # Stage deployment first
            success, deployment_id, deployment_info = self.deployment_manager.stage_deployment(
                agent,
                Path(target_path),
                session_token
            )
            
            if not success:
                return JSONResponse(
                    {"error": deployment_info.get("error", "Staging failed")},
                    status_code=400
                )
            
            # Check coverage requirement
            if not deployment_info.get("coverage_ok", False):
                return JSONResponse(
                    {"error": f"Coverage requirement not met: {deployment_info.get('coverage_percent', 0)}%"},
                    status_code=400
                )
            
            # Execute deployment
            success, message = self.deployment_manager.execute_deployment(
                deployment_id,
                session_token
            )
            
            if success:
                # Broadcast success
                await self._broadcast_ws({
                    "type": "deployment_complete",
                    "agent_id": agent_id,
                    "file": file_path,
                    "status": "success"
                })
                
                return JSONResponse({
                    "success": True,
                    "message": message,
                    "deployment_id": deployment_id
                })
            else:
                return JSONResponse(
                    {"error": message},
                    status_code=400
                )
                
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return JSONResponse(
                {"error": f"Deployment failed: {str(e)}"},
                status_code=500
            )
    
    async def rollback(self, request: Request) -> JSONResponse:
        """Rollback a deployment"""
        try:
            data = await request.json()
            
            # Validate session
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401
                )
            
            session_token = auth_header[7:]
            deployment_id = data.get("deployment_id")
            
            if not deployment_id:
                return JSONResponse(
                    {"error": "deployment_id required"},
                    status_code=400
                )
            
            # Execute rollback
            success, message = self.deployment_manager.rollback_deployment(
                deployment_id,
                session_token
            )
            
            if success:
                return JSONResponse({
                    "success": True,
                    "message": message
                })
            else:
                return JSONResponse(
                    {"error": message},
                    status_code=400
                )
                
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return JSONResponse(
                {"error": f"Rollback failed: {str(e)}"},
                status_code=500
            )
    
    async def get_deployment_history(self, request: Request) -> JSONResponse:
        """Get deployment history"""
        try:
            # Validate session
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401
                )
            
            session_token = auth_header[7:]
            valid, session = self.security_manager.validate_session(session_token)
            if not valid:
                return JSONResponse(
                    {"error": "Invalid or expired session"},
                    status_code=401
                )
            
            # Get deployment status
            status = self.deployment_manager.get_deployment_status()
            
            return JSONResponse({
                "success": True,
                "status": status,
                "audit_log": self.security_manager.get_deployment_history(50)
            })
            
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return JSONResponse(
                {"error": f"Failed to get history: {str(e)}"},
                status_code=500
            )
    
    async def handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connections for real-time updates"""
        await websocket.accept()
        ws_id = f"ws_{datetime.now().timestamp()}"
        self.active_websockets[ws_id] = websocket
        
        try:
            await websocket.send_json({
                "type": "connected",
                "message": "WebSocket connected for real-time updates"
            })
            
            # Keep connection alive
            while True:
                data = await websocket.receive_json()
                
                # Handle ping/pong
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except Exception as e:
            logger.info(f"WebSocket disconnected: {e}")
        finally:
            del self.active_websockets[ws_id]
    
    async def _broadcast_ws(self, data: Dict[str, Any]):
        """Broadcast to all WebSocket clients"""
        disconnected = []
        
        for ws_id, ws in self.active_websockets.items():
            try:
                await ws.send_json(data)
            except:
                disconnected.append(ws_id)
        
        # Clean up disconnected
        for ws_id in disconnected:
            del self.active_websockets[ws_id]
    
    def get_routes(self):
        """Get all orchestrator routes"""
        return [
            # UI
            ("/orchestrator", self.serve_orchestrator_ui, ["GET"]),
            
            # Authentication
            ("/api/orchestrator/generate-keys", self.generate_keys, ["POST"]),
            ("/api/orchestrator/authenticate", self.authenticate, ["POST"]),
            ("/api/orchestrator/validate", self.validate_session, ["GET"]),
            
            # Testing
            ("/api/orchestrator/test/{agent_id}", self.test_agent, ["POST"]),
            
            # Deployment
            ("/api/orchestrator/stage", self.stage_deployment, ["POST"]),
            ("/api/orchestrator/deploy", self.deploy, ["POST"]),
            ("/api/orchestrator/rollback", self.rollback, ["POST"]),
            ("/api/orchestrator/history", self.get_deployment_history, ["GET"]),
            
            # WebSocket
            ("/ws", self.handle_websocket, ["websocket"])
        ]