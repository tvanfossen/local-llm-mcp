# File: ~/Projects/local-llm-mcp/api/http_server.py
"""HTTP Server Setup with Starlette and Proper MCP Streamable HTTP Transport

Responsibilities:
- Create and configure Starlette application
- Implement MCP Streamable HTTP transport
- Setup middleware (CORS, logging, etc.)
- Route registration and organization
- Server lifecycle management
"""

import logging
from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute

from api.endpoints import APIEndpoints
from api.mcp_handler import MCPHandler
from api.orchestrator import OrchestratorAPI
from api.websocket_handler import WebSocketHandler
from core.agent_registry import AgentRegistry
from core.config import ConfigManager
from core.deployment import DeploymentManager
from core.llm_manager import LLMManager
from core.security import SecurityManager

logger = logging.getLogger(__name__)


async def _root_handler(
    request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry
) -> JSONResponse:
    """Root endpoint with server information"""
    model_info = llm_manager.get_model_info()
    registry_stats = agent_registry.get_registry_stats()

    return JSONResponse(
        {
            "service": "Standardized Agent-Based LLM Server",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": [
                "JSON Schema Validation",
                "One Agent Per File Rule",
                "CUDA 12.9 Optimized",
                "MCP Streamable HTTP Transport",
                "HTTP API",
                "WebSocket Support",
            ],
            "status": {
                "model_loaded": model_info["model_loaded"],
                "agents_active": registry_stats["total_agents"],
                "files_managed": registry_stats["managed_files"],
                "total_interactions": registry_stats["total_interactions"],
            },
            "endpoints": {
                "mcp": "POST/GET /mcp (MCP Streamable HTTP transport)",
                "health": "GET /health",
                "api": "/api/* (direct HTTP API)",
                "docs": "GET /docs (API documentation)",
            },
            "configuration": {
                "gpu_optimized": True,
                "context_size": model_info.get("configuration", {}).get("context_size"),
                "batch_size": model_info.get("configuration", {}).get("batch_size"),
            },
        }
    )


async def _health_handler(
    request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry
) -> JSONResponse:
    """Health check endpoint"""
    health_check = llm_manager.health_check()
    registry_stats = agent_registry.get_registry_stats()

    return JSONResponse(
        {
            "status": "healthy" if health_check.get("status") == "healthy" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": {
                "loaded": llm_manager.model_loaded,
                "health": health_check.get("status", "unknown"),
                "performance": health_check.get("avg_performance", 0),
            },
            "agents": {
                "total": registry_stats["total_agents"],
                "files_managed": registry_stats["managed_files"],
                "integrity": registry_stats.get("file_ownership_integrity", True),
            },
            "system": {
                "cuda_available": True,
                "gpu_optimized": True,
            },
        }
    )


async def _mcp_streamable_http_handler(request: Request, mcp_handler: MCPHandler) -> Response:
    """MCP Streamable HTTP transport endpoint"""
    try:
        session_id = request.headers.get("mcp-session-id")

        if request.method == "POST":
            return await _handle_mcp_post_request(request, mcp_handler, session_id)
        elif request.method == "GET":
            return JSONResponse(
                {
                    "error": "GET method not yet implemented",
                    "message": "Streaming support via SSE will be added in future version",
                },
                status_code=501,
            )
        else:
            return JSONResponse(
                {"error": "Method not allowed", "allowed": ["POST", "GET"]}, status_code=405
            )

    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e),
            },
        }
        return JSONResponse(error_response, status_code=500)


async def _handle_mcp_post_request(
    request: Request, mcp_handler: MCPHandler, session_id: str | None
) -> Response:
    """Handle MCP POST request"""
    try:
        request_data = await request.json()
        logger.info(
            f"MCP POST request: {request_data.get('method', 'unknown')} (session: {session_id})"
        )

        response_data = await mcp_handler.handle_jsonrpc_request(request_data, session_id)

        if response_data is None:
            return Response(status_code=204)

        headers = {"Content-Type": "application/json"}
        if "_session_id" in response_data:
            headers["Mcp-Session-Id"] = response_data.pop("_session_id")
            session_id = headers["Mcp-Session-Id"]
        elif session_id:
            headers["Mcp-Session-Id"] = session_id

        return JSONResponse(response_data, headers=headers)

    except Exception as e:
        logger.error(f"Failed to parse MCP request: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error",
                "data": str(e),
            },
        }
        return JSONResponse(error_response, status_code=400)


async def _mcp_legacy_handler(request: Request, mcp_handler: MCPHandler) -> JSONResponse:
    """Legacy MCP endpoint for backwards compatibility"""
    try:
        data = await request.json()

        if "method" in data and "params" in data:
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": data["method"],
                "params": data["params"],
            }
            response = await mcp_handler.handle_jsonrpc_request(jsonrpc_request)

            if response and "result" in response:
                return JSONResponse(response["result"])
            elif response and "error" in response:
                return JSONResponse(response["error"], status_code=400)
            else:
                return JSONResponse({"error": "No response"}, status_code=500)

        response = await mcp_handler.handle_jsonrpc_request(data)
        return JSONResponse(response or {"status": "ok"})

    except Exception as e:
        logger.error(f"Legacy MCP endpoint error: {e}")
        return JSONResponse({"error": f"Request failed: {e!s}"}, status_code=500)


def create_http_server(
    agent_registry: AgentRegistry,
    llm_manager: LLMManager,
    config: ConfigManager,
) -> Starlette:
    """Create and configure the Starlette HTTP application with proper MCP support"""
    # Initialize handlers
    mcp_handler = MCPHandler(agent_registry, llm_manager)
    api_endpoints = APIEndpoints(agent_registry, llm_manager)
    security_manager = SecurityManager(config.system.state_dir)
    deployment_manager = DeploymentManager(security_manager, config.system.workspaces_dir)
    orchestrator_api = OrchestratorAPI(agent_registry, security_manager, deployment_manager)
    websocket_handler = WebSocketHandler(agent_registry, llm_manager)

    # Create handler wrappers
    async def root_handler(request: Request) -> JSONResponse:
        return await _root_handler(request, llm_manager, agent_registry)

    async def health_handler(request: Request) -> JSONResponse:
        return await _health_handler(request, llm_manager, agent_registry)

    async def mcp_handler_wrapper(request: Request) -> Response:
        return await _mcp_streamable_http_handler(request, mcp_handler)

    async def legacy_handler_wrapper(request: Request) -> JSONResponse:
        return await _mcp_legacy_handler(request, mcp_handler)

    async def websocket_endpoint(websocket):
        await websocket_handler.handle_connection(websocket)

    # Build routes list
    routes = _build_routes(
        root_handler,
        health_handler,
        mcp_handler_wrapper,
        legacy_handler_wrapper,
        api_endpoints,
        orchestrator_api,
        websocket_endpoint,
    )

    # Create and configure Starlette application
    app = Starlette(routes=routes)
    _configure_middleware(app, config)

    logger.info("✅ HTTP server configured with MCP Streamable HTTP transport")
    return app


def _build_routes(
    root_handler,
    health_handler,
    mcp_handler_wrapper,
    legacy_handler_wrapper,
    api_endpoints,
    orchestrator_api,
    websocket_endpoint,
):
    """Build the complete routes list"""
    routes = [
        # Core endpoints
        Route("/", root_handler, methods=["GET"]),
        Route("/health", health_handler, methods=["GET"]),
        # MCP endpoints
        Route("/mcp", mcp_handler_wrapper, methods=["POST", "GET"]),
        Route("/mcp-legacy", legacy_handler_wrapper, methods=["POST"]),
        # API endpoints
        Route("/api/agents", api_endpoints.list_agents, methods=["GET"]),
        Route("/api/agents", api_endpoints.create_agent, methods=["POST"]),
        Route("/api/agents/{agent_id}", api_endpoints.get_agent, methods=["GET"]),
        Route("/api/agents/{agent_id}", api_endpoints.delete_agent, methods=["DELETE"]),
        Route("/api/agents/{agent_id}/chat", api_endpoints.chat_with_agent, methods=["POST"]),
        Route("/api/agents/{agent_id}/file", api_endpoints.get_agent_file, methods=["GET"]),
        Route("/api/system/status", api_endpoints.system_status, methods=["GET"]),
        WebSocketRoute("/ws", websocket_endpoint),
    ]

    # Add orchestrator routes
    for path, handler, methods in orchestrator_api.get_routes():
        if "websocket" in methods:
            if path != "/ws":  # Avoid duplicate WebSocket routes
                routes.append(WebSocketRoute(path, handler))
        else:
            routes.append(Route(path, handler, methods=methods))

    return routes


def _configure_middleware(app: Starlette, config: ConfigManager):
    """Configure middleware for the application"""
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.allow_origins,
        allow_credentials=config.server.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "*",
            "Content-Type",
            "Authorization",
            "Mcp-Session-Id",
            "Last-Event-Id",
        ],
        expose_headers=["Mcp-Session-Id"],
    )

    # Add logging and session middleware
    @app.middleware("http")
    async def log_and_session_middleware(request, call_next):
        start_time = datetime.now()
        session_id = request.headers.get("mcp-session-id", "no-session")
        logger.info(f"Request: {request.method} {request.url.path} (session: {session_id})")

        response = await call_next(request)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
        )

        return response

    # Add CORS preflight middleware
    @app.middleware("http")
    async def cors_preflight_middleware(request, call_next):
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, Mcp-Session-Id"
            )
            response.headers["Access-Control-Expose-Headers"] = "Mcp-Session-Id"
            return response
        return await call_next(request)
