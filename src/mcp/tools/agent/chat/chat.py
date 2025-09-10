"""Chat with Agent MCP Tool

Responsibilities:
- Send messages to agents for processing
- Handle different task types (update, create, analyze, etc.)
- Track conversation history and interactions
- Return standardized MCP response format
"""

import logging
from typing import Any

from src.core.agents.registry.registry import AgentRegistry
from src.core.config.manager.manager import ConfigManager
from src.core.utils import create_success, create_error, handle_exception

logger = logging.getLogger(__name__)




async def chat_with_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Send a message to an agent for processing"""
    try:
        agent_id = args.get("agent_id")
        message = args.get("message")
        task_type = args.get("task_type", "analyze")

        if not agent_id:
            return create_error("Missing Parameter", "Agent ID is required")

        if not message:
            return create_error("Missing Parameter", "Message is required")

        # Validate task type
        valid_task_types = ["update", "create", "analyze", "refactor", "debug", "document", "test"]
        if task_type not in valid_task_types:
            return create_error("Invalid Task Type", f"Task type must be one of: {', '.join(valid_task_types)}")

        config_manager = ConfigManager()
        registry = AgentRegistry(config_manager)

        agent = registry.get_agent(agent_id)
        if not agent:
            return create_error("Agent Not Found", f"No agent found with ID: {agent_id}")

        # Process the message with the agent
        response = await _process_agent_message(agent, message, task_type)

        # Update agent statistics
        agent.state.interaction_count += 1
        agent.state.last_modified = agent._get_timestamp()

        # Save updated state
        agent._save_metadata()

        return create_success(response)

    except Exception as e:
        logger.error(f"Failed to chat with agent: {e}")
        return handle_exception(e, "Chat with Agent")


async def _process_agent_message(agent, message: str, task_type: str) -> str:
    """Process a message with the agent"""
    try:
        # Add user message to conversation history
        user_message = {"role": "user", "content": message, "task_type": task_type, "timestamp": agent._get_timestamp()}
        agent.conversation_history.append(user_message)

        # For now, we'll simulate agent processing
        # In a real implementation, this would call the LLM with the agent's context
        response_content = _simulate_agent_response(agent, message, task_type)

        # Add agent response to conversation history
        agent_response = {
            "role": "assistant",
            "content": response_content,
            "task_type": task_type,
            "timestamp": agent._get_timestamp(),
        }
        agent.conversation_history.append(agent_response)

        # Save conversation history
        agent._save_conversation_history()

        # Update success/failure statistics
        agent.state.successful_operations += 1

        return _format_agent_response(agent, response_content, task_type)

    except Exception as e:
        agent.state.failed_operations += 1
        agent._save_metadata()
        raise e


def _build_system_context(agent, task_type: str) -> str:
    """Build system context for the agent"""
    base_context = f"""You are {agent.state.name}, an AI agent with the following characteristics:

Description: {agent.state.description}
System Prompt: {agent.state.system_prompt or "No specific system prompt set"}

Managed Files: {", ".join(agent.managed_files) if agent.managed_files else "None"}

Current Task Type: {task_type}
"""

    task_contexts = {
        "update": "Focus on modifying and improving existing code or content.",
        "create": "Focus on creating new code, files, or content from scratch.",
        "analyze": "Focus on analyzing and understanding existing code or content.",
        "refactor": "Focus on restructuring code while preserving functionality.",
        "debug": "Focus on identifying and fixing issues or bugs.",
        "document": "Focus on creating or updating documentation.",
        "test": "Focus on creating or running tests and validating functionality.",
    }

    if task_type in task_contexts:
        base_context += f"\nTask Context: {task_contexts[task_type]}"

    return base_context


def _simulate_agent_response(agent, message: str, task_type: str) -> str:
    """Simulate agent response (placeholder for actual LLM integration)"""
    # This is a placeholder implementation
    # In the real system, this would integrate with the LLM service

    responses = {
        "update": f"I'll help update the content based on your request: '{message}'. Let me analyze the managed files and make the necessary changes.",
        "create": f"I'll create new content based on your request: '{message}'. Let me design and implement what you need.",
        "analyze": f"I've analyzed your request: '{message}'. Here's my understanding and recommendations.",
        "refactor": f"I'll refactor the code according to your request: '{message}'. Let me restructure while preserving functionality.",
        "debug": f"I'll help debug the issue you described: '{message}'. Let me investigate and provide solutions.",
        "document": f"I'll create documentation for your request: '{message}'. Let me prepare comprehensive documentation.",
        "test": f"I'll help with testing based on your request: '{message}'. Let me create or run appropriate tests.",
    }

    base_response = responses.get(task_type, f"I'll help with your request: '{message}'.")

    # Add file-specific context if managing files
    if agent.managed_files:
        file_context = f"\n\nI'm currently managing these files: {', '.join(agent.managed_files)}"
        base_response += file_context

    return base_response


def _format_agent_response(agent, response_content: str, task_type: str) -> str:
    """Format the agent response for display"""
    task_emoji = {
        "update": "🔄",
        "create": "✨",
        "analyze": "🔍",
        "refactor": "🛠️",
        "debug": "🐛",
        "document": "📚",
        "test": "🧪",
    }

    emoji = task_emoji.get(task_type, "💬")

    formatted_response = (
        f"{emoji} **{agent.state.name} Response** ({task_type})\n\n"
        f"{response_content}\n\n"
        f"---\n"
        f"🆔 Agent ID: `{agent.state.agent_id[:8]}...` | "
        f"🔄 Interaction #{agent.state.interaction_count}"
    )

    return formatted_response
