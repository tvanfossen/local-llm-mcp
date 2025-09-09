"""Delete Agent MCP Tool

Responsibilities:
- Delete agents from the registry
- Handle agent cleanup and file removal
- Provide confirmation and safety checks
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


async def delete_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Delete an agent from the registry"""
    try:
        agent_id = args.get("agent_id")
        force = args.get("force", False)

        if not agent_id:
            return _create_error("Missing Parameter", "Agent ID is required")

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agent = registry.get_agent(agent_id)
        if not agent:
            return _create_error("Agent Not Found", f"No agent found with ID: {agent_id}")

        # Collect agent info before deletion
        agent_name = agent.state.name
        managed_files_count = len(agent.managed_files)
        interaction_count = agent.state.interaction_count

        # Safety check for agents with significant activity
        if not force and interaction_count > 10:
            return _create_error(
                "Deletion Blocked",
                f"Agent '{agent_name}' has {interaction_count} interactions. Use 'force: true' to confirm deletion.",
            )

        # Perform cleanup
        cleanup_results = _cleanup_agent_data(agent, config_manager)

        # Remove from registry
        success = registry.remove_agent(agent_id)
        if not success:
            return _create_error("Deletion Failed", "Failed to remove agent from registry")

        # Format success message
        success_msg = _format_deletion_success(
            agent_name, agent_id, managed_files_count, interaction_count, cleanup_results
        )

        return _create_success(success_msg)

    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        return _handle_exception(e, "Delete Agent")


def _cleanup_agent_data(agent, config_manager) -> dict:
    """Clean up agent data files and directories"""
    cleanup_results = {"files_removed": 0, "directories_removed": 0, "errors": []}

    try:
        # Get agent directory path
        agent_dir = config_manager.system.agents_dir / agent.state.agent_id

        if agent_dir.exists():
            # Remove agent files
            for file_path in agent_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        cleanup_results["files_removed"] += 1
                    except Exception as e:
                        cleanup_results["errors"].append(f"Failed to remove file {file_path}: {e}")

            # Remove agent directory
            try:
                agent_dir.rmdir()
                cleanup_results["directories_removed"] += 1
            except Exception as e:
                cleanup_results["errors"].append(f"Failed to remove directory {agent_dir}: {e}")

    except Exception as e:
        cleanup_results["errors"].append(f"Cleanup error: {e}")

    return cleanup_results


def _format_deletion_success(
    agent_name: str, agent_id: str, managed_files_count: int, interaction_count: int, cleanup_results: dict
) -> str:
    """Format the deletion success message"""
    base_msg = (
        f"🗑️ **Agent Deleted Successfully**\n\n"
        f"🤖 **Agent:** {agent_name}\n"
        f"🆔 **ID:** `{agent_id[:8]}...`\n"
        f"📁 **Managed Files:** {managed_files_count}\n"
        f"🔄 **Total Interactions:** {interaction_count}"
    )

    # Add cleanup information
    if cleanup_results["files_removed"] > 0 or cleanup_results["directories_removed"] > 0:
        cleanup_msg = (
            f"\n\n🧹 **Cleanup Summary:**\n"
            f"   • Files removed: {cleanup_results['files_removed']}\n"
            f"   • Directories removed: {cleanup_results['directories_removed']}"
        )
        base_msg += cleanup_msg

    # Add error information if any
    if cleanup_results["errors"]:
        error_count = len(cleanup_results["errors"])
        error_msg = f"\n\n⚠️ **Cleanup Warnings:** {error_count} issues encountered"
        if error_count <= 3:
            error_list = "\n".join([f"   • {error}" for error in cleanup_results["errors"]])
            error_msg += f"\n{error_list}"
        base_msg += error_msg

    return base_msg


async def delete_all_agents(args: dict[str, Any] = None) -> dict[str, Any]:
    """Delete all agents from the registry (dangerous operation)"""
    try:
        force = args.get("force", False) if args else False

        if not force:
            return _create_error(
                "Deletion Blocked", "This operation will delete ALL agents. Use 'force: true' to confirm."
            )

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agents = registry.list_agents()
        if not agents:
            return _create_success("🗑️ **No Agents to Delete**\n\nRegistry is already empty.")

        deletion_results = {"successful_deletions": 0, "failed_deletions": 0, "total_files_removed": 0, "errors": []}

        # Delete each agent
        for agent in agents:
            try:
                cleanup_results = _cleanup_agent_data(agent, config_manager)
                success = registry.remove_agent(agent.state.agent_id)

                if success:
                    deletion_results["successful_deletions"] += 1
                    deletion_results["total_files_removed"] += cleanup_results["files_removed"]
                else:
                    deletion_results["failed_deletions"] += 1
                    deletion_results["errors"].append(f"Failed to remove agent {agent.state.name}")

                # Add cleanup errors
                deletion_results["errors"].extend(cleanup_results["errors"])

            except Exception as e:
                deletion_results["failed_deletions"] += 1
                deletion_results["errors"].append(f"Error deleting agent {agent.state.name}: {e}")

        # Format results
        result_msg = _format_bulk_deletion_results(deletion_results, len(agents))
        return _create_success(result_msg)

    except Exception as e:
        logger.error(f"Failed to delete all agents: {e}")
        return _handle_exception(e, "Delete All Agents")


def _format_bulk_deletion_results(results: dict, total_agents: int) -> str:
    """Format bulk deletion results"""
    success_count = results["successful_deletions"]
    failed_count = results["failed_deletions"]
    files_removed = results["total_files_removed"]

    base_msg = (
        f"🗑️ **Bulk Agent Deletion Complete**\n\n"
        f"📊 **Results:**\n"
        f"   • Total agents: {total_agents}\n"
        f"   • Successfully deleted: {success_count}\n"
        f"   • Failed deletions: {failed_count}\n"
        f"   • Files removed: {files_removed}"
    )

    if results["errors"]:
        error_count = len(results["errors"])
        error_msg = f"\n\n⚠️ **Errors:** {error_count} issues encountered"
        if error_count <= 5:
            error_list = "\n".join([f"   • {error}" for error in results["errors"][:5]])
            error_msg += f"\n{error_list}"
            if error_count > 5:
                error_msg += f"\n   • ... and {error_count - 5} more errors"
        base_msg += error_msg

    return base_msg
