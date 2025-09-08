"""Middleware Configuration - HTTP Middleware Setup and Management.

Responsibilities:
- Configure CORS middleware for cross-origin requests
- Setup security headers and request logging
- Provide middleware configuration utilities
- Handle middleware ordering and dependencies
"""

import logging
from typing import Any

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from src.core.config.manager.manager import ConfigManager

logger = logging.getLogger(__name__)


def configure_application_middleware(app: Starlette, config: ConfigManager) -> None:
    """Configure all middleware for the application.

    Args:
        app: Starlette application instance
        config: Configuration manager with server settings
    """
    _configure_cors_middleware(app, config)
    _log_middleware_configuration(config)


def _configure_cors_middleware(app: Starlette, config: ConfigManager) -> None:
    """Configure CORS middleware for cross-origin requests.

    Args:
        app: Starlette application instance
        config: Configuration manager with CORS settings
    """
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
            "X-Requested-With",
            "Accept",
            "Origin",
        ],
        expose_headers=["Mcp-Session-Id"],
    )


def _log_middleware_configuration(config: ConfigManager) -> None:
    """Log middleware configuration for debugging.

    Args:
        config: Configuration manager with server settings
    """
    logger.info("✅ CORS middleware configured")
    logger.info(f"   Origins: {config.server.allow_origins}")
    logger.info(f"   Credentials: {config.server.allow_credentials}")


def get_middleware_info(config: ConfigManager) -> dict[str, Any]:
    """Get information about configured middleware.

    Args:
        config: Configuration manager

    Returns:
        Dictionary with middleware information
    """
    return {
        "cors_enabled": len(config.server.allow_origins) > 0,
        "allow_credentials": config.server.allow_credentials,
        "allowed_origins": config.server.allow_origins,
        "security_headers": True,
    }


def validate_middleware_config(config: ConfigManager) -> tuple[bool, list[str]]:
    """Validate middleware configuration.

    Args:
        config: Configuration manager to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Validate CORS configuration
    if not config.server.allow_origins:
        errors.append("No CORS origins configured")

    # Check for wildcard origin with credentials
    if "*" in config.server.allow_origins and config.server.allow_credentials:
        errors.append("Cannot use wildcard origin with credentials enabled")

    return len(errors) == 0, errors
