# File: ~/Projects/local-llm-mcp/src/api/http/endpoints/endpoints.py
"""API Endpoints for HTTP interface - System endpoints only

Responsibilities:
- System status and health endpoints only
- Agent operations now handled via MCP protocol
- Minimal HTTP API surface for system monitoring
"""

import logging
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from src.core.agents.registry.registry import AgentRegistry
from src.core.llm.manager.manager import LLMManager

logger = logging.getLogger(__name__)


class APIEndpoints:
    """HTTP API endpoints for system monitoring only

    Agent operations have been moved to MCP protocol.
    This class now only handles system-level endpoints.
    """

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager

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
                        "note": "Agent operations available via MCP protocol at POST /mcp",
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
                        "access_method": "MCP tools via POST /mcp endpoint",
                    },
                    "endpoints": {
                        "mcp_protocol": "POST /mcp",
                        "system_status": "GET /api/system/status",
                        "health_check": "GET /health",
                        "documentation": "GET /",
                    },
                }
            )

        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return JSONResponse({"error": f"System status failed: {e!s}"}, status_code=500)
