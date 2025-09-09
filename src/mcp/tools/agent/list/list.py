"""List Agents MCP Tool

Responsibilities:
- List all active agents in the registry
- Display agent summary information
- Handle empty registry cases
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


async def list_agents(args: dict[str, Any] = None) -> dict[str, Any]:
    """List all active agents"""
    try:
        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agents = registry.list_agents()

        if not agents:
            return _create_success(
                "📋 **Agent Registry**\n\nNo agents found. Use the create agent tool to create your first agent."
            )

        registry_stats = registry.get_registry_stats()
        agent_list = _format_agent_list(agents)
        stats_summary = _format_registry_stats(registry_stats)

        result = f"📋 **Agent Registry** ({len(agents)} agents)\n\n{agent_list}\n\n{stats_summary}"
        return _create_success(result)

    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return _handle_exception(e, "List Agents")


def _format_agent_list(agents: list) -> str:
    """Format the list of agents for display"""
    agent_entries = []

    for agent in agents:
        # Format managed files count
        file_count = len(agent.managed_files)
        file_info = f"{file_count} file{'s' if file_count != 1 else ''}"

        # Format interaction count
        interaction_count = agent.state.interaction_count
        interaction_info = f"{interaction_count} interaction{'s' if interaction_count != 1 else ''}"

        # Format success rate
        success_rate = agent.state.success_rate
        success_info = f"{success_rate:.1%}" if interaction_count > 0 else "N/A"

        # Create agent entry
        entry = (
            f"🤖 **{agent.state.name}** (ID: `{agent.state.agent_id[:8]}...`)\n"
            f"   📄 Description: {agent.state.description}\n"
            f"   📁 Managing: {file_info} | 🔄 {interaction_info} | ✅ Success: {success_info}"
        )

        agent_entries.append(entry)

    return "\n\n".join(agent_entries)


def _format_registry_stats(stats: dict) -> str:
    """Format registry statistics for display"""
    total_agents = stats["total_agents"]
    managed_files = stats["managed_files"]
    total_interactions = stats["total_interactions"]
    avg_success_rate = stats["average_success_rate"]
    most_active = stats["most_active_agent"]

    stats_lines = [
        "📊 **Registry Statistics:**",
        f"   Total Agents: {total_agents}",
        f"   Files Under Management: {managed_files}",
        f"   Total Interactions: {total_interactions}",
        f"   Average Success Rate: {avg_success_rate:.1%}"
        if total_interactions > 0
        else "   Average Success Rate: N/A",
    ]

    if most_active:
        stats_lines.append(f"   Most Active Agent: {most_active}")

    return "\n".join(stats_lines)


def _format_agent_summary(agent) -> str:
    """Format a single agent summary"""
    file_count = len(agent.managed_files)
    files_text = "files" if file_count != 1 else "file"

    return (
        f"🤖 **{agent.state.name}** (`{agent.state.agent_id[:8]}...`)\n"
        f"   📄 {agent.state.description}\n"
        f"   📁 {file_count} {files_text} | "
        f"🔄 {agent.state.interaction_count} interactions | "
        f"✅ {agent.state.success_rate:.1%} success"
    )
