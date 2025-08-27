# File: ~/Projects/local-llm-mcp/api/http_server.py
"""
HTTP Server Setup with Starlette

Responsibilities:
- Create and configure Starlette application
- Setup middleware (CORS, logging, etc.)
- Route registration and organization
- Server lifecycle management
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request

from api.mcp_handler import MCPHandler
from api.endpoints import APIEndpoints
from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from core.config import ConfigManager

logger = logging.getLogger(__name__)

def create_http_server(
    agent_registry: AgentRegistry,
    llm_manager: LLMManager,
    config: ConfigManager
) -> Starlette:
    """
    Create and configure the Starlette HTTP application
    
    Args:
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance
        config: Configuration manager
        
    Returns:
        Configured Starlette application
    """
    
    # Initialize handlers
    mcp_handler = MCPHandler(agent_registry, llm_manager)
    api_endpoints = APIEndpoints(agent_registry, llm_manager)
    
    async def root_handler(request: Request) -> JSONResponse:
        """Root endpoint with server information"""
        model_info = llm_manager.get_model_info()
        registry_stats = agent_registry.get_registry_stats()
        
        return JSONResponse({
            "service": "Standardized Agent-Based LLM Server",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": [
                "JSON Schema Validation",
                "One Agent Per File Rule",
                "CUDA 12.9 Optimized",
                "MCP Protocol Support",
                "HTTP API",
                "WebSocket Support"
            ],
            "status": {
                "model_loaded": model_info["model_loaded"],
                "agents_active": registry_stats["total_agents"],
                "files_managed": registry_stats["managed_files"],
                "total_interactions": registry_stats["total_interactions"]
            },
            "endpoints": {
                "mcp": "POST /mcp (for Claude Code integration)",
                "health": "GET /health",
                "api": "/api/* (direct HTTP API)",
                "docs": "GET /docs (API documentation)"
            },
            "configuration": {
                "gpu_optimized": True,
                "context_size": model_info.get("configuration", {}).get("context_size"),
                "batch_size": model_info.get("configuration", {}).get("batch_size")
            }
        })
    
    async def health_handler(request: Request) -> JSONResponse:
        """Health check endpoint"""
        health_check = llm_manager.health_check()
        registry_stats = agent_registry.get_registry_stats()
        
        return JSONResponse({
            "status": "healthy" if health_check.get("status") == "healthy" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": {
                "loaded": llm_manager.model_loaded,
                "health": health_check.get("status", "unknown"),
                "performance": health_check.get("avg_performance", 0)
            },
            "agents": {
                "total": registry_stats["total_agents"],
                "files_managed": registry_stats["managed_files"],
                "integrity": registry_stats.get("file_ownership_integrity", True)
            },
            "system": {
                "cuda_available": True,
                "gpu_optimized": True
            }
        })
    
    async def mcp_endpoint(request: Request) -> JSONResponse:
        """MCP protocol endpoint for Claude Code"""
        try:
            data = await request.json()
            method = data.get("method", "")
            params = data.get("params", {})
            
            logger.info(f"MCP request: {method}")
            response = await mcp_handler.handle_mcp_request(method, params)
            
            return JSONResponse(response)
            
        except Exception as e:
            logger.error(f"MCP endpoint error: {e}")
            return JSONResponse(
                {
                    "content": [{
                        "type": "text",
                        "text": f"❌ **MCP Error:** {str(e)}"
                    }],
                    "isError": True
                },
                status_code=500
            )
    
    # Define routes
    routes = [
        # Core endpoints
        Route("/", root_handler, methods=["GET"]),
        Route("/health", health_handler, methods=["GET"]),
        
        # MCP endpoint for Claude Code
        Route("/mcp", mcp_endpoint, methods=["POST"]),
        
        # API endpoints (for testing/debugging)
        Route("/api/agents", api_endpoints.list_agents, methods=["GET"]),
        Route("/api/agents", api_endpoints.create_agent, methods=["POST"]),
        Route("/api/agents/{agent_id}", api_endpoints.get_agent, methods=["GET"]),
        Route("/api/agents/{agent_id}", api_endpoints.delete_agent, methods=["DELETE"]),
        Route("/api/agents/{agent_id}/chat", api_endpoints.chat_with_agent, methods=["POST"]),
        Route("/api/agents/{agent_id}/file", api_endpoints.get_agent_file, methods=["GET"]),
        Route("/api/system/status", api_endpoints.system_status, methods=["GET"]),
    ]
    
    # Create Starlette application
    app = Starlette(routes=routes)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.allow_origins,
        allow_credentials=config.server.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware for request logging
    @app.middleware("http")
    async def log_requests(request, call_next):
        start_time = datetime.now()
        
        response = await call_next(request)
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {duration:.3f}s"
        )
        
        return response
    
    logger.info("✅ HTTP server configured with all endpoints")
    return app