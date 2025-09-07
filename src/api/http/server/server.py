# File: ~/Projects/local-llm-mcp/src/api/http/server/server.py
"""HTTP Server Setup with Starlette and Proper MCP Streamable HTTP Transport

Responsibilities:
- Create and configure Starlette application
- Coordinate between extracted modules (routes, middleware, handlers)
- Initialize core components and dependencies
- Provide main server factory function
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from starlette.applications import Starlette

from src.api.http.endpoints.endpoints import APIEndpoints
from src.api.http.handlers.handlers import (
    handle_health_check,
    handle_mcp_legacy,
    handle_mcp_streamable_http,
    handle_root_request,
)
from src.api.http.routes.routes import build_application_routes
from src.api.http.types.types import RouteHandlers
from src.api.middleware.auth.auth import configure_application_middleware
from src.api.orchestrator.orchestrator import OrchestratorAPI
from src.api.websocket.handler.handler import WebSocketHandler
from src.core.agents.registry.registry import AgentRegistry
from src.core.config.manager.manager import ConfigManager
from src.core.deployment.manager.manager import DeploymentManager
from src.core.llm.manager.manager import LLMManager
from src.core.security.manager.manager import SecurityManager
from src.mcp.handler import MCPHandler

logger = logging.getLogger(__name__)


def create_http_server(
    agent_registry: AgentRegistry,
    llm_manager: LLMManager,
    config: ConfigManager,
) -> Starlette:
    """Create and configure the Starlette HTTP application with MCP and authentication support.

    Args:
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance
        config: Configuration manager instance

    Returns:
        Configured Starlette application
    """
    # Initialize all handlers
    handlers = _initialize_handlers(agent_registry, llm_manager, config)

    # Create application with routes and middleware
    app = _create_starlette_app(handlers)
    configure_application_middleware(app, config)

    logger.info("✅ HTTP server configured with MCP Streamable HTTP transport")
    logger.info("🔐 Authentication bridge enabled for all MCP endpoints")
    logger.info("🗑️ Agent HTTP endpoints removed - using MCP protocol only")
    return app


def _initialize_handlers(agent_registry, llm_manager, config):
    """Initialize all route handlers.

    Args:
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance
        config: Configuration manager instance

    Returns:
        RouteHandlers instance with all handlers configured
    """
    components = _create_core_components(agent_registry, llm_manager, config)
    return _create_route_handlers(components, agent_registry, llm_manager)


def _create_core_components(agent_registry, llm_manager, config):
    """Create core components needed for handlers.

    Args:
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance
        config: Configuration manager instance

    Returns:
        Dictionary with core component instances
    """
    # Create security manager
    security_manager = SecurityManager(config.system.state_dir)

    # Create MCP handler with security manager for authentication
    mcp_handler = MCPHandler(agent_registry, llm_manager, security_manager)

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
        "security_manager": security_manager,
    }


def _create_route_handlers(components, agent_registry, llm_manager):
    """Create handler wrappers.

    Args:
        components: Dictionary of core components
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance

    Returns:
        RouteHandlers instance
    """
    handlers = _build_handler_functions(components, agent_registry, llm_manager)

    return RouteHandlers(
        root_handler=handlers["root"],
        health_handler=handlers["health"],
        mcp_handler_wrapper=handlers["mcp"],
        legacy_handler_wrapper=handlers["legacy"],
        api_endpoints=components["api_endpoints"],
        orchestrator_api=components["orchestrator_api"],
        websocket_endpoint=handlers["websocket"],
    )


def _build_handler_functions(components, agent_registry, llm_manager):
    """Build all handler functions.

    Args:
        components: Dictionary of core components
        agent_registry: Agent registry instance
        llm_manager: LLM manager instance

    Returns:
        Dictionary of handler functions
    """
    return {
        "root": _create_root_handler(agent_registry, llm_manager),
        "health": _create_health_handler(agent_registry, llm_manager),
        "mcp": _create_mcp_handler(components["mcp_handler"]),
        "legacy": _create_legacy_handler(components["mcp_handler"]),
        "websocket": _create_websocket_handler(components["websocket_handler"]),
    }


def _create_root_handler(agent_registry, llm_manager):
    """Create root handler wrapper."""

    async def root_handler(request):
        return await handle_root_request(request, llm_manager, agent_registry)

    return root_handler


def _create_health_handler(agent_registry, llm_manager):
    """Create health handler wrapper."""

    async def health_handler(request):
        return await handle_health_check(request, llm_manager, agent_registry)

    return health_handler


def _create_mcp_handler(mcp_handler):
    """Create MCP handler wrapper."""

    async def mcp_handler_wrapper(request):
        return await handle_mcp_streamable_http(request, mcp_handler)

    return mcp_handler_wrapper


def _create_legacy_handler(mcp_handler):
    """Create legacy MCP handler wrapper."""

    async def legacy_handler_wrapper(request):
        return await handle_mcp_legacy(request, mcp_handler)

    return legacy_handler_wrapper


def _create_websocket_handler(websocket_handler):
    """Create WebSocket handler wrapper."""

    async def websocket_endpoint(websocket):
        await websocket_handler.handle_connection(websocket)

    return websocket_endpoint


def _create_starlette_app(handlers: RouteHandlers) -> Starlette:
    """Create Starlette application with routes.

    Args:
        handlers: Container with all route handlers

    Returns:
        Configured Starlette application
    """
    routes = build_application_routes(handlers)
    return Starlette(routes=routes)
