"""Request Handlers - HTTP Request Processing Logic.

Responsibilities:
- Handle root endpoint with server information
- Process health check requests
- Handle MCP Streamable HTTP transport with authentication
- Process legacy MCP requests for backward compatibility
- Provide error handling for HTTP requests
"""

import logging
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.core.agents.registry.registry import AgentRegistry
from src.core.llm.manager.manager import LLMManager
from src.mcp.handler import MCPHandler

logger = logging.getLogger(__name__)


async def handle_root_request(request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry) -> JSONResponse:
    """Root endpoint with comprehensive server information.

    Args:
        request: HTTP request object
        llm_manager: LLM manager instance
        agent_registry: Agent registry instance

    Returns:
        JSON response with server status and configuration
    """
    logger.debug(f"ENTRY handle_root_request")

    model_info = llm_manager.get_model_info()
    registry_stats = agent_registry.get_registry_stats()

    logger.info(f"📊 Root request: model_loaded={model_info['model_loaded']}, agents={registry_stats['total_agents']}")

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
            "endpoints": _get_endpoint_info(),
            "agent_access": _get_agent_access_info(),
            "configuration": _get_configuration_info(model_info),
        }
    )

    logger.debug(f"EXIT handle_root_request: success")


async def handle_health_check(request: Request, llm_manager: LLMManager, agent_registry: AgentRegistry) -> JSONResponse:
    """Health check endpoint with comprehensive system status.

    Args:
        request: HTTP request object
        llm_manager: LLM manager instance
        agent_registry: Agent registry instance

    Returns:
        JSON response with health status
    """
    logger.debug(f"ENTRY handle_health_check")

    health_check = llm_manager.health_check()
    registry_stats = agent_registry.get_registry_stats()

    health_status = "healthy" if health_check.get("status") == "healthy" else "degraded"
    logger.info(f"🏥 Health check: {health_status}, model={health_check.get('status')}, agents={registry_stats['total_agents']}")

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

    logger.debug(f"EXIT handle_health_check: {health_status}")


async def handle_mcp_streamable_http(request: Request, mcp_handler: MCPHandler) -> Response:
    """MCP Streamable HTTP transport endpoint with authentication bridge.

    Args:
        request: HTTP request object
        mcp_handler: MCP handler instance

    Returns:
        HTTP response (JSON or appropriate error response)
    """
    logger.debug(f"ENTRY handle_mcp_streamable_http: method={request.method}")

    try:
        # Extract both MCP session ID and orchestrator auth token
        session_id = request.headers.get("mcp-session-id")
        auth_token = request.headers.get("authorization")

        logger.info(f"🔗 MCP Streamable HTTP request: {request.method} (session: {session_id[:8] if session_id else 'None'})")

        # Route to appropriate method handler
        if request.method == "POST":
            result = await _handle_mcp_post_request(request, mcp_handler, session_id, auth_token)
            logger.debug(f"EXIT handle_mcp_streamable_http: POST processed successfully")
            return result

        # GET method - explicitly not supported for streaming
        from src.core.exceptions import OperationNotImplemented
        error = OperationNotImplemented("GET method for MCP Streamable HTTP", "HTTP Transport")
        logger.error(f"EXIT handle_mcp_streamable_http: FAILED - {error}")

        return JSONResponse(
            {
                "error": "GET method not supported",
                "message": "MCP Streamable HTTP transport requires POST method only",
                "error_type": error.error_type,
                "supported_methods": ["POST"]
            },
            status_code=405,  # Method Not Allowed
        )

    except Exception as e:
        logger.error(f"EXIT handle_mcp_streamable_http: FAILED - {e}")
        return _create_mcp_error_response(None, e)


async def handle_mcp_legacy(request: Request, mcp_handler: MCPHandler) -> JSONResponse:
    """Legacy MCP endpoint for backwards compatibility.

    Args:
        request: HTTP request object
        mcp_handler: MCP handler instance

    Returns:
        JSON response with MCP result
    """
    logger.debug(f"ENTRY handle_mcp_legacy")

    try:
        data = await request.json()
        # Extract both session ID and auth token for consistency with main handler
        session_id = request.headers.get("mcp-session-id")
        auth_token = request.headers.get("authorization")

        logger.info(f"🔗 Legacy MCP request: {data.get('method', 'unknown')} (session: {session_id[:8] if session_id else 'None'})")

        # Handle different request formats with authentication
        response = await _process_legacy_request(data, mcp_handler, session_id, auth_token)

        # Return appropriate response format
        result = _format_legacy_response(response)
        logger.debug(f"EXIT handle_mcp_legacy: processed successfully")
        return result

    except Exception as e:
        logger.error(f"EXIT handle_mcp_legacy: FAILED - {e}")
        return JSONResponse({"error": f"Request failed: {e!s}"}, status_code=500)


# Private helper functions


def _get_endpoint_info() -> dict[str, str]:
    """Get endpoint information for root response."""
    return {
        "mcp": "POST/GET /mcp (MCP Streamable HTTP transport)",
        "health": "GET /health",
        "system": "GET /api/system/status",
        "orchestrator": "GET /orchestrator (Secure UI)",
        "websocket": "WS /ws",
    }


def _get_agent_access_info() -> dict[str, str]:
    """Get agent access information for root response."""
    return {
        "primary": "MCP tools via POST /mcp",
        "authentication": "Required - use orchestrator token",
        "note": "All agent operations use MCP protocol with security",
        "legacy_removed": "HTTP /api/agents/* endpoints removed in Phase 3",
    }


def _get_configuration_info(model_info: dict) -> dict[str, Any]:
    """Get configuration information for root response."""
    return {
        "gpu_optimized": True,
        "context_size": model_info.get("configuration", {}).get("context_size"),
        "batch_size": model_info.get("configuration", {}).get("batch_size"),
        "authentication_enabled": True,
    }


async def _handle_mcp_post_request(
    request: Request, mcp_handler: MCPHandler, session_id: str | None, auth_token: str | None
) -> Response:
    """Handle MCP POST request with authentication bridge."""
    try:
        request_data = await request.json()
        logger.info(f"MCP POST request: {request_data.get('method', 'unknown')} (session: {session_id})")

        # Pass both session ID and auth token to MCP handler
        response_data = await mcp_handler.handle_jsonrpc_request(request_data, session_id, auth_token)

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
        return _create_mcp_parse_error_response(e)


def _create_mcp_error_response(request_id: Any, error: Exception) -> JSONResponse:
    """Create standardized MCP error response."""
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
    """Create MCP parse error response."""
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


async def _process_legacy_request(data: dict, mcp_handler: MCPHandler, session_id: str | None, auth_token: str | None):
    """Process legacy request format with authentication bridge."""
    if "method" in data and "params" in data:
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": data["method"],
            "params": data["params"],
        }
        return await mcp_handler.handle_jsonrpc_request(jsonrpc_request, session_id, auth_token)

    return await mcp_handler.handle_jsonrpc_request(data, session_id, auth_token)


def _format_legacy_response(response) -> JSONResponse:
    """Format legacy response."""
    if not response:
        return JSONResponse({"status": "ok"})

    # Handle result response
    if "result" in response:
        return JSONResponse(response["result"])

    # Handle error response or no response
    error_data = response.get("error", {"error": "No response"})
    status_code = 400 if "error" in response else 500
    return JSONResponse(error_data, status_code=status_code)
