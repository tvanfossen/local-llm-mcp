"""Agent Info MCP Tool

Responsibilities:
- Get detailed information about a specific agent
- Display agent metadata, managed files, and statistics
- Handle agent not found cases
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


async def get_agent_info(args: dict[str, Any]) -> dict[str, Any]:
    """Get detailed information about a specific agent"""
    try:
        agent_id = args.get("agent_id")
        
        if not agent_id:
            return _create_error("Missing Parameter", "Agent ID is required")
        
        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)
        
        agent = registry.get_agent(agent_id)
        if not agent:
            return _create_error("Agent Not Found", f"No agent found with ID: {agent_id}")
        
        agent_info = _format_agent_info(agent)
        return _create_success(agent_info)
        
    except Exception as e:
        logger.error(f"Failed to get agent info: {e}")
        return _handle_exception(e, "Get Agent Info")


def _format_agent_info(agent) -> str:
    """Format detailed agent information"""
    # Basic information
    basic_info = (
        f"🤖 **Agent Details**\n\n"
        f"📝 **Name:** {agent.state.name}\n"
        f"🆔 **ID:** {agent.state.agent_id}\n"
        f"📄 **Description:** {agent.state.description}\n"
        f"📅 **Created:** {agent.state.created_at}\n"
        f"🔄 **Last Modified:** {agent.state.last_modified}"
    )
    
    # System prompt (truncated if too long)
    system_prompt = agent.state.system_prompt or "Not set"
    if len(system_prompt) > 200:
        system_prompt = system_prompt[:200] + "..."
    
    prompt_info = f"\n\n🧠 **System Prompt:**\n```\n{system_prompt}\n```"
    
    # Managed files
    managed_files = agent.managed_files
    if managed_files:
        files_list = "\n".join([f"   📁 {file}" for file in managed_files])
        files_info = f"\n\n📁 **Managed Files:** ({len(managed_files)})\n{files_list}"
    else:
        files_info = f"\n\n📁 **Managed Files:** None"
    
    # Statistics
    stats_info = _format_agent_statistics(agent)
    
    # Recent interactions (last 5)
    interactions_info = _format_recent_interactions(agent)
    
    return f"{basic_info}{prompt_info}{files_info}{stats_info}{interactions_info}"


def _format_agent_statistics(agent) -> str:
    """Format agent statistics"""
    stats = (
        f"\n\n📊 **Statistics:**\n"
        f"   🔄 Total Interactions: {agent.state.interaction_count}\n"
        f"   ✅ Successful Operations: {agent.state.successful_operations}\n"
        f"   ❌ Failed Operations: {agent.state.failed_operations}\n"
        f"   📈 Success Rate: {agent.state.success_rate:.1%}"
    )
    
    if agent.state.interaction_count > 0:
        avg_response_time = getattr(agent.state, 'average_response_time', 0)
        if avg_response_time > 0:
            stats += f"\n   ⏱️ Average Response Time: {avg_response_time:.2f}s"
    
    return stats


def _format_recent_interactions(agent) -> str:
    """Format recent interactions"""
    if not hasattr(agent, 'conversation_history') or not agent.conversation_history:
        return "\n\n💬 **Recent Interactions:** None"
    
    # Get last 5 user interactions (excluding system messages)
    user_interactions = [
        msg for msg in agent.conversation_history[-10:] 
        if msg.get('role') == 'user'
    ][-5:]
    
    if not user_interactions:
        return "\n\n💬 **Recent Interactions:** None"
    
    interactions_list = []
    for i, interaction in enumerate(user_interactions, 1):
        timestamp = interaction.get('timestamp', 'Unknown time')
        content = interaction.get('content', '')
        
        # Truncate long content
        if len(content) > 100:
            content = content[:100] + "..."
        
        interactions_list.append(f"   {i}. [{timestamp}] {content}")
    
    interactions_text = "\n".join(interactions_list)
    return f"\n\n💬 **Recent Interactions:** (Last {len(user_interactions)})\n{interactions_text}"


def _format_file_info(file_path: str, agent) -> str:
    """Format information about a managed file"""
    # This could be expanded to include file stats, last modified, etc.
    try:
        from pathlib import Path
        full_path = Path(file_path)
        if full_path.exists():
            size = full_path.stat().st_size
            return f"{file_path} ({size} bytes)"
        else:
            return f"{file_path} (file not found)"
    except Exception:
        return file_path