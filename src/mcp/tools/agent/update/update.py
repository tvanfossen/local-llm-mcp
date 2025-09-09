"""Update Agent MCP Tool

Responsibilities:
- Update agent properties (name, description, system prompt)
- Manage agent's file assignments
- Handle agent configuration changes
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


async def update_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Update agent properties and configuration"""
    try:
        agent_id = args.get("agent_id")

        if not agent_id:
            return _create_error("Missing Parameter", "Agent ID is required")

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agent = registry.get_agent(agent_id)
        if not agent:
            return _create_error("Agent Not Found", f"No agent found with ID: {agent_id}")

        # Collect what will be updated
        updates = []

        # Update name if provided
        new_name = args.get("name")
        if new_name:
            validation_error = _validate_agent_name(new_name)
            if validation_error:
                return _create_error("Invalid Name", validation_error)

            # Check for name conflicts
            existing_agent = registry.get_agent_by_name(new_name)
            if existing_agent and existing_agent.state.agent_id != agent_id:
                return _create_error("Name Conflict", f"Agent with name '{new_name}' already exists")

            old_name = agent.state.name
            agent.state.name = new_name
            updates.append(f"Name: '{old_name}' → '{new_name}'")

        # Update description if provided
        new_description = args.get("description")
        if new_description:
            validation_error = _validate_description(new_description)
            if validation_error:
                return _create_error("Invalid Description", validation_error)

            agent.state.description = new_description
            updates.append("Description updated")

        # Update system prompt if provided
        new_system_prompt = args.get("system_prompt")
        if new_system_prompt:
            validation_error = _validate_system_prompt(new_system_prompt)
            if validation_error:
                return _create_error("Invalid System Prompt", validation_error)

            agent.state.system_prompt = new_system_prompt
            updates.append("System prompt updated")

        # Handle file management operations
        add_files = args.get("add_files", [])
        remove_files = args.get("remove_files", [])

        if add_files:
            for file_path in add_files:
                agent.add_managed_file(file_path)
                updates.append(f"Added file: {file_path}")

        if remove_files:
            for file_path in remove_files:
                if file_path in agent.managed_files:
                    agent.remove_managed_file(file_path)
                    updates.append(f"Removed file: {file_path}")

        if not updates:
            return _create_error("No Updates", "No valid update parameters provided")

        # Update timestamp and save
        agent.state.last_modified = agent._get_timestamp()
        agent._save_metadata()

        # Format success response
        updates_text = "\n   • ".join(updates)
        success_msg = (
            f"✅ **Agent Updated Successfully**\n\n"
            f"🤖 **Agent:** {agent.state.name} (`{agent.state.agent_id[:8]}...`)\n\n"
            f"📝 **Updates Applied:**\n   • {updates_text}"
        )

        return _create_success(success_msg)

    except Exception as e:
        logger.error(f"Failed to update agent: {e}")
        return _handle_exception(e, "Update Agent")


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


async def update_agent_files(args: dict[str, Any]) -> dict[str, Any]:
    """Update agent's managed files (separate function for file-only updates)"""
    try:
        agent_id = args.get("agent_id")
        file_path = args.get("file_path")
        operation = args.get("operation", "add")  # "add" or "remove"

        if not agent_id:
            return _create_error("Missing Parameter", "Agent ID is required")

        if not file_path:
            return _create_error("Missing Parameter", "File path is required")

        if operation not in ["add", "remove"]:
            return _create_error("Invalid Operation", "Operation must be 'add' or 'remove'")

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agent = registry.get_agent(agent_id)
        if not agent:
            return _create_error("Agent Not Found", f"No agent found with ID: {agent_id}")

        if operation == "add":
            if file_path in agent.managed_files:
                return _create_error("File Already Managed", f"Agent already manages file: {file_path}")

            agent.add_managed_file(file_path)
            success_msg = f"✅ **File Added**\n🤖 Agent: {agent.state.name}\n📁 Added: {file_path}"

        else:  # remove
            if file_path not in agent.managed_files:
                return _create_error("File Not Managed", f"Agent does not manage file: {file_path}")

            agent.remove_managed_file(file_path)
            success_msg = f"✅ **File Removed**\n🤖 Agent: {agent.state.name}\n📁 Removed: {file_path}"

        # Update timestamp and save
        agent.state.last_modified = agent._get_timestamp()
        agent._save_metadata()

        return _create_success(success_msg)

    except Exception as e:
        logger.error(f"Failed to update agent files: {e}")
        return _handle_exception(e, "Update Agent Files")
