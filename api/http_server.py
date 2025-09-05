# File: ~/Projects/local-llm-mcp/api/http_server.py
"""HTTP Server Setup with Enhanced MCP Authentication Bridge

Responsibilities:
- Create and configure Starlette application
- Implement MCP Streamable HTTP transport with authentication bridge
- Setup middleware (CORS, logging, etc.)
- Route registration for system endpoints only
- Server lifecycle management
- Bridge orchestrator authentication with MCP protocol securely
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


@dataclass
class RouteHandlers:
    """Container for route handlers"""

    root_handler: callable
    health_handler: callable
    mcp_handler_wrapper: callable
    legacy_handler_wrapper: callable
    api_endpoints: Any
    orchestrator_api: Any
    websocket_endpoint: callable


def extract_auth_token(request: Request) -> str | None:
    """Extract authentication token from request headers with validation"""
    auth_header = request.headers.get("authorization", "").strip()

    if not auth_header:
        return None

    # Handle Bearer token format
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        return token if token else None

    # Return the header value as-is for other formats
    return auth_header


def log_auth_attempt(method: str, session_id: str | None, auth_present: bool, success: bool = None):
    """Log authentication attempt for audit purposes"""
    auth_status = "present" if auth_present else "missing"
    session_info = f"session:{session_id}" if session_id else "no-session"

    if success is not None:
        result = "success" if success else "failed"
        logger.info(f"MCP Auth {result}: {method} ({session_info}, auth:{auth_status})")
    else:
        logger.debug(f"MCP Request: {method} ({session_info}, auth:{auth_status})")


async def _root_handler(request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry) -> JSONResponse:
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
                "WebSocket Support",
                "Unified MCP Architecture",
                "Orchestrator Authentication Integration",
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
                "system": "GET /api/system/status",
                "orchestrator": "GET /orchestrator (Secure UI)",
                "websocket": "WS /ws",
            },
            "agent_access": {
                "primary": "MCP tools via POST /mcp",
                "authentication": "Required - use orchestrator token",
                "note": "All agent operations use MCP protocol with security",
                "legacy_removed": "HTTP /api/agents/* endpoints removed in Phase 3",
            },
            "configuration": {
                "gpu_optimized": True,
                "context_size": model_info.get("configuration", {}).get("context_size"),
                "batch_size": model_info.get("configuration", {}).get("batch_size"),
                "authentication_enabled": True,
            },
        }
    )


async def _health_handler(request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry) -> JSONResponse:
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
            "protocol": {
                "mcp_enabled": True,
                "agent_access": "MCP tools only",
                "unified_architecture": True,
                "authentication_required": True,
            },
            "system": {
                "cuda_available": True,
                "gpu_optimized": True,
            },
        }
    )


async def _mcp_streamable_http_handler(request: Request, mcp_handler: MCPHandler) -> Response:
    """MCP Streamable HTTP transport endpoint with enhanced authentication bridge"""
    try:
        # Extract authentication and session information
        session_id = request.headers.get("mcp-session-id")
        auth_token = extract_auth_token(request)

        # Log authentication attempt
        method = await _extract_request_method(request)
        log_auth_attempt(method, session_id, auth_token is not None)

        # Route to appropriate method handler
        if request.method == "POST":
            return await _handle_mcp_post_request(request, mcp_handler, session_id, auth_token)

        # GET method (streaming support planned for future)
        return JSONResponse(
            {
                "error": "GET method not yet implemented",
                "message": "Streaming support via SSE will be added in future version",
            },
            status_code=501,
        )

    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return _create_mcp_error_response(None, e)


async def _extract_request_method(request: Request) -> str:
    """Extract MCP method from request for logging"""
    try:
        if request.method == "POST":
            # Try to peek at the method without consuming the body
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                return "POST(JSON-RPC)"
        return request.method
    except Exception:
        return "unknown"


async def _handle_mcp_post_request(
    request: Request, mcp_handler: MCPHandler, session_id: str | None, auth_token: str | None
) -> Response:
    """Handle MCP POST request with enhanced authentication"""
    try:
        request_data = await request.json()
        method = request_data.get("method", "unknown")

        logger.info(
            f"MCP POST request: {method} (session: {session_id}, auth: {'present' if auth_token else 'missing'})"
        )

        # Pass auth token to MCP handler for validation
        response_data = await mcp_handler.handle_jsonrpc_request(request_data, session_id, auth_token)

        if response_data is None:
            return Response(status_code=204)

        # Handle session management in headers
        headers = {"Content-Type": "application/json"}
        if "_session_id" in response_data:
            headers["Mcp-Session-Id"] = response_data.pop("_session_id")
            session_id = headers["Mcp-Session-Id"]
        elif session_id:
            headers["Mcp-Session-Id"] = session_id

        # Log successful authentication if applicable
        if auth_token and not response_data.get("error"):
            log_auth_attempt(method, session_id, True, True)

        return JSONResponse(response_data, headers=headers)

    except Exception as e:
        logger.error(f"Failed to parse MCP request: {e}")
        return _create_mcp_parse_error_response(e)


async def _mcp_legacy_handler(request: Request, mcp_handler: MCPHandler) -> JSONResponse:
    """Legacy MCP endpoint with authentication support"""
    try:
        data = await request.json()
        auth_token = extract_auth_token(request)

        # Log legacy request attempt
        method = data.get("method", "unknown")
        log_auth_attempt(f"legacy-{method}", None, auth_token is not None)

        # Process legacy request format with authentication
        response = await _process_legacy_request(data, mcp_handler, auth_token)
        return _format_legacy_response(response)

    except Exception as e:
        logger.error(f"Legacy MCP endpoint error: {e}")
        return JSONResponse({"error": f"Request failed: {e!s}"}, status_code=500)


async def _process_legacy_request(data: dict, mcp_handler: MCPHandler, auth_token: str | None):
    """Process legacy request format with authentication"""
    # Convert to standard JSON-RPC format if needed
    if "method" in data and "params" in data:
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": data["method"],
            "params": data["params"],
        }
    else:
        jsonrpc_request = data

    return await mcp_handler.handle_jsonrpc_request(jsonrpc_request, auth_token=auth_token)


def _format_legacy_response(response) -> JSONResponse:
    """Format legacy response with appropriate status codes"""
    if not response:
        return JSONResponse({"status": "ok"})

    if "result" in response:
        return JSONResponse(response["result"])

    # Handle authentication errors with proper status codes
    if "error" in response:
        error = response["error"]
        status_code = 401 if error.get("code") == -32002 else 400
        return JSONResponse(error, status_code=status_code)

    return JSONResponse({"error": "No response"}, status_code=500)


def _create_mcp_error_response(request_id: Any, error: Exception) -> JSONResponse:
    """Create standardized MCP error response"""
    error_response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32603,
            "message": "Internal error",
            "data": str(error),
        },
    }
    return JSONResponse(error_response, status_code=500)


def _create_mcp_parse_error_response(error: Exception) -> JSONResponse:
    """Create MCP parse error response"""
    error_response = {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": -32700,
            "message": "Parse error",
            "data": str(error),
        },
    }
    return JSONResponse(error_response, status_code=400)


def create_http_server(
    agent_registry: AgentRegistry,
    llm_manager: LLMManager,
    config: ConfigManager,
) -> Starlette:
    """Create and configure the Starlette HTTP application with enhanced MCP authentication"""
    # Initialize components
    components = _initialize_core_components(agent_registry, llm_manager, config)
    handlers = _create_route_handlers(components, agent_registry, llm_manager)

    # Create application
    app = _build_starlette_application(handlers)
    _configure_application_middleware(app, config)

    logger.info("✅ HTTP server configured with enhanced MCP authentication bridge")
    logger.info("🔐 Authentication integration fully enabled for MCP protocol")
    logger.info("🗑️ Agent HTTP endpoints removed - using MCP protocol only")
    return app


def _initialize_core_components(agent_registry, llm_manager, config):
    """Initialize core components for HTTP server"""
    # Create security manager for authentication
    security_manager = SecurityManager(config.system.state_dir)

    # Create MCP handler with enhanced security integration
    mcp_handler = MCPHandler(agent_registry, llm_manager, security_manager)

    # Create other components
    api_endpoints = APIEndpoints(agent_registry, llm_manager)

    workspace_root = (
        Path("/workspace") if config.system.is_container_environment() else config.system.get_workspace_root()
    )
    deployment_manager = DeploymentManager(security_manager, workspace_root)
    orchestrator_api = OrchestratorAPI(agent_registry, security_manager, deployment_manager)
    websocket_handler = WebSocketHandler(agent_registry, llm_manager)

    return {
        "mcp_handler": mcp_handler,
        "api_endpoints": api_endpoints,
        "orchestrator_api": orchestrator_api,
        "websocket_handler": websocket_handler,
    }


def _create_route_handlers(components, agent_registry, llm_manager):
    """Create route handler wrappers with authentication support"""
    # Create handler functions
    root_handler = lambda req: _root_handler(req, llm_manager, agent_registry)
    health_handler = lambda req: _health_handler(req, llm_manager, agent_registry)
    mcp_handler_wrapper = lambda req: _mcp_streamable_http_handler(req, components["mcp_handler"])
    legacy_handler_wrapper = lambda req: _mcp_legacy_handler(req, components["mcp_handler"])
    websocket_endpoint = lambda ws: components["websocket_handler"].handle_connection(ws)

    return RouteHandlers(
        root_handler=root_handler,
        health_handler=health_handler,
        mcp_handler_wrapper=mcp_handler_wrapper,
        legacy_handler_wrapper=legacy_handler_wrapper,
        api_endpoints=components["api_endpoints"],
        orchestrator_api=components["orchestrator_api"],
        websocket_endpoint=websocket_endpoint,
    )


def _build_starlette_application(handlers: RouteHandlers) -> Starlette:
    """Build Starlette application with all routes"""
    routes = [
        # Core endpoints
        Route("/", handlers.root_handler, methods=["GET"]),
        Route("/health", handlers.health_handler, methods=["GET"]),
        # MCP endpoints with enhanced authentication
        Route("/mcp", handlers.mcp_handler_wrapper, methods=["POST", "GET"]),
        Route("/mcp-legacy", handlers.legacy_handler_wrapper, methods=["POST"]),
        # System endpoint only (agent endpoints removed)
        Route("/api/system/status", handlers.api_endpoints.system_status, methods=["GET"]),
        # WebSocket
        WebSocketRoute("/ws", handlers.websocket_endpoint),
    ]

    # Add orchestrator routes
    for path, handler, methods in handlers.orchestrator_api.get_routes():
        if "websocket" in methods:
            if path != "/ws":  # Avoid duplicate WebSocket routes
                routes.append(WebSocketRoute(path, handler))
        else:
            routes.append(Route(path, handler, methods=methods))

    return Starlette(routes=routes)


def _configure_application_middleware(app: Starlette, config: ConfigManager):
    """Configure middleware with enhanced security headers"""
    # Add CORS middleware with authentication headers
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

    # Add enhanced logging middleware with authentication tracking
    @app.middleware("http")
    async def enhanced_logging_middleware(request, call_next):
        start_time = datetime.now()
        session_id = request.headers.get("mcp-session-id", "no-session")
        auth_present = "yes" if request.headers.get("authorization") else "no"

        logger.info(f"Request: {request.method} {request.url.path} (session: {session_id}, auth: {auth_present})")

        response = await call_next(request)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")

        return response

    # Add CORS preflight middleware
    @app.middleware("http")
    async def cors_preflight_middleware(request, call_next):
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Mcp-Session-Id"
            response.headers["Access-Control-Expose-Headers"] = "Mcp-Session-Id"
            return response
        return await call_next(request)
