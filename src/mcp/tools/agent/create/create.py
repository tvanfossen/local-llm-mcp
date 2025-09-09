"""Create Agent MCP Tool

Responsibilities:
- Create new agents through the AgentRegistry
- Validate agent creation parameters
- Handle agent creation errors
- Return standardized MCP response format
"""

import logging
from typing import Any

from src.core.agents.registry.registry import AgentRegistry
from src.core.config.manager.manager import ConfigManager

logger = logging.getLogger(__name__)


def _create_success(text: str) -> dict[str, Any]:
    """Create success response format"""
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format"""
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
    """Handle exceptions with consistent error format"""
    return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}


async def create_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new agent"""
    try:
        name = args.get("name")
        description = args.get("description")
        system_prompt = args.get("system_prompt")
        managed_file = args.get("managed_file")
        initial_context = args.get("initial_context", "")

        if not name:
            return _create_error("Missing Parameter", "Agent name is required")

        if not description:
            return _create_error("Missing Parameter", "Agent description is required")

        if not system_prompt:
            return _create_error("Missing Parameter", "System prompt is required")

        if not managed_file:
            return _create_error("Missing Parameter", "Managed file is required")

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        # Check if agent with same name already exists
        existing_agent = registry.get_agent_by_name(name)
        if existing_agent:
            return _create_error("Agent Exists", f"Agent with name '{name}' already exists")

        specialized_files = [managed_file] if managed_file else []
        agent = registry.create_agent(name, description, specialized_files)

        # Set system prompt if provided
        if system_prompt:
            agent.state.system_prompt = system_prompt
            agent._save_metadata()

        # Add initial context if provided
        if initial_context:
            agent.conversation_history.append(
                {"role": "system", "content": initial_context, "timestamp": agent._get_timestamp()}
            )
            agent._save_conversation_history()

        success_msg = (
            f"✅ **Agent Created Successfully**\n"
            f"📝 Name: {name}\n"
            f"🆔 ID: {agent.state.agent_id}\n"
            f"📄 Description: {description}\n"
            f"📁 Managed File: {managed_file}"
        )

        return _create_success(success_msg)

    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return _handle_exception(e, "Create Agent")


def _validate_agent_name(name: str) -> str | None:
    """Validate agent name format"""
    if not name or not name.strip():
        return "Agent name cannot be empty"

    if len(name) > 100:
        return "Agent name cannot exceed 100 characters"

    # Check for invalid characters
    invalid_chars = set(name) - set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")
    if invalid_chars:
        return f"Agent name contains invalid characters: {', '.join(invalid_chars)}"

    return None


def _validate_description(description: str) -> str | None:
    """Validate agent description"""
    if not description or not description.strip():
        return "Agent description cannot be empty"

    if len(description) > 1000:
        return "Agent description cannot exceed 1000 characters"

    return None


def _validate_system_prompt(system_prompt: str) -> str | None:
    """Validate system prompt"""
    if not system_prompt or not system_prompt.strip():
        return "System prompt cannot be empty"

    if len(system_prompt) > 5000:
        return "System prompt cannot exceed 5000 characters"

    return None
