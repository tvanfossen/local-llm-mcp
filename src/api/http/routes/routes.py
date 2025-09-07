"""Route Factory - HTTP Route Generation and Configuration.

Responsibilities:
- Build complete routes list for Starlette application
- Configure static file routes and WebSocket endpoints
- Integrate orchestrator routes with core API routes
- Provide route building utilities
"""

from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

from src.api.http.types.types import RouteHandlers


def build_application_routes(handlers: RouteHandlers) -> list:
    """Build the complete routes list for the application.

    Args:
        handlers: Container with all route handlers

    Returns:
        List of Starlette routes
    """
    routes = _build_core_routes(handlers)
    routes.extend(_build_orchestrator_routes(handlers))
    routes.append(_build_static_route())

    return routes


def _build_core_routes(handlers: RouteHandlers) -> list:
    """Build core API routes.

    Args:
        handlers: Container with all route handlers

    Returns:
        List of core routes
    """
    return [
        # Core endpoints
        Route("/", handlers.root_handler, methods=["GET"]),
        Route("/health", handlers.health_handler, methods=["GET"]),
        # MCP endpoints with authentication bridge
        Route("/mcp", handlers.mcp_handler_wrapper, methods=["POST", "GET"]),
        Route("/mcp-legacy", handlers.legacy_handler_wrapper, methods=["POST"]),
        # System endpoint only (agent endpoints removed)
        Route("/api/system/status", handlers.api_endpoints.system_status, methods=["GET"]),
        # WebSocket
        WebSocketRoute("/ws", handlers.websocket_endpoint),
    ]


def _build_orchestrator_routes(handlers: RouteHandlers) -> list:
    """Build orchestrator-specific routes.

    Args:
        handlers: Container with all route handlers

    Returns:
        List of orchestrator routes
    """
    routes = []

    # Add orchestrator routes
    for path, handler, methods in handlers.orchestrator_api.get_routes():
        if "websocket" in methods:
            if path != "/ws":  # Avoid duplicate WebSocket routes
                routes.append(WebSocketRoute(path, handler))
        else:
            routes.append(Route(path, handler, methods=methods))

    return routes


def _build_static_route() -> Mount:
    """Build static file serving route.

    Returns:
        Static files mount point
    """
    return Mount("/static", StaticFiles(directory="static"), name="static")


def create_route_metadata() -> dict:
    """Create metadata about available routes.

    Returns:
        Dictionary with route information
    """
    return {
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
    }
