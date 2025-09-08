"""Orchestrator API - Web UI and Management Interface

Responsibilities:
- Provide web-based management interface
- Handle orchestrator routes and endpoints
- Coordinate with security and deployment managers
- Serve static UI assets
"""

import logging
from pathlib import Path
from typing import Any

from starlette.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)


class OrchestratorAPI:
    """Web-based orchestrator and management interface"""

    def __init__(self, agent_registry, security_manager, deployment_manager):
        self.agent_registry = agent_registry
        self.security_manager = security_manager
        self.deployment_manager = deployment_manager
        
        # Path to static HTML file
        self.orchestrator_html_path = Path(__file__).parent.parent.parent.parent / "static" / "orchestrator.html"

    def get_routes(self) -> list[tuple[str, Any, list[str]]]:
        """Get orchestrator routes"""
        return [
            ("/orchestrator", self._orchestrator_handler, ["GET"]),
            ("/orchestrator/status", self._status_handler, ["GET"]),
            ("/api/orchestrator/authenticate", self._authenticate_handler, ["POST"]),
        ]

    async def _orchestrator_handler(self, request):
        """Main orchestrator page handler - serve HTML"""
        try:
            # Serve the static HTML file
            if self.orchestrator_html_path.exists():
                with open(self.orchestrator_html_path, 'r') as f:
                    html_content = f.read()
                return HTMLResponse(content=html_content)
            else:
                # Fallback if file not found
                return HTMLResponse(content="<h1>Orchestrator HTML not found</h1>", status_code=404)
        except Exception as e:
            logger.error(f"Failed to serve orchestrator HTML: {e}")
            return HTMLResponse(content=f"<h1>Error loading orchestrator: {str(e)}</h1>", status_code=500)

    async def _status_handler(self, request):
        """Orchestrator status handler"""
        return JSONResponse({
            "agents": self.agent_registry.get_registry_stats(),
            "security": self.security_manager.get_security_status(),
            "deployment": self.deployment_manager.get_deployment_status(),
        })

    async def _authenticate_handler(self, request):
        """Handle authentication requests from orchestrator UI"""
        try:
            data = await request.json()
            private_key = data.get("private_key", "")
            
            if private_key:
                # Create a session using the security manager
                session_data = self.security_manager.create_session(
                    client_name="Orchestrator UI",
                    private_key=private_key
                )
                
                logger.info(f"Authentication successful for Orchestrator UI")
                
                return JSONResponse(session_data)
            else:
                return JSONResponse(
                    {"error": "No private key provided"},
                    status_code=400
                )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return JSONResponse(
                {"error": str(e)},
                status_code=500
            )