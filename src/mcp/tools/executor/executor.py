"""MCP Tools Executor - Execute MCP Tool Calls

Responsibilities:
- Execute MCP tool calls including agent operations
- Handle tool validation and dispatch
- Provide tool definitions and metadata
- Coordinate with git tools and agent registry
"""

import logging
from pathlib import Path
from typing import Any

from src.core.agents.agent.agent import AgentCreateParams
from src.mcp.tools.git.commit.commit import git_commit
from src.mcp.tools.git.diff.diff import git_diff
from src.mcp.tools.git.log.log import git_log
from src.mcp.tools.git.status.status import git_status
from src.mcp.tools.system.all_validations.all_validations import run_all_validations
from src.mcp.tools.testing.precommit.precommit import run_pre_commit
from src.mcp.tools.testing.run_tests.run_tests import run_tests
from src.mcp.tools.validation.agent_file.agent_file import validate_agent_file
from src.mcp.tools.validation.file_length.file_length import validate_file_length
from src.schemas.agents.agents import AgentRequest, TaskType

logger = logging.getLogger(__name__)


class MCPToolExecutor:
    """Executes MCP tool calls with validation"""

    def __init__(self, agent_registry, llm_manager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.available_tools = self._build_tool_registry()

    def _build_tool_registry(self) -> dict[str, Any]:
        """Build registry of available tools"""
        return {
            # Agent Management Tools
            "create_agent": {
                "name": "create_agent",
                "description": "Create a new agent to manage a file",
                "function": self._create_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Agent name"},
                        "description": {"type": "string", "description": "Agent description"},
                        "system_prompt": {"type": "string", "description": "System prompt for the agent"},
                        "managed_file": {"type": "string", "description": "File the agent will manage"},
                        "initial_context": {"type": "string", "description": "Initial context (optional)"},
                    },
                    "required": ["name", "description", "system_prompt", "managed_file"],
                },
            },
            "list_agents": {
                "name": "list_agents",
                "description": "List all active agents",
                "function": self._list_agents,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "get_agent_info": {
                "name": "get_agent_info",
                "description": "Get detailed information about an agent",
                "function": self._get_agent_info,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID"}},
                    "required": ["agent_id"],
                },
            },
            "delete_agent": {
                "name": "delete_agent",
                "description": "Delete an agent",
                "function": self._delete_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID to delete"}},
                    "required": ["agent_id"],
                },
            },
            "chat_with_agent": {
                "name": "chat_with_agent",
                "description": "Send a message to an agent for processing",
                "function": self._chat_with_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID"},
                        "message": {"type": "string", "description": "Message to send"},
                        "task_type": {
                            "type": "string",
                            "enum": ["update", "create", "analyze", "refactor", "debug", "document", "test"],
                            "description": "Type of task",
                        },
                    },
                    "required": ["agent_id", "message"],
                },
            },
            "get_agent_file": {
                "name": "get_agent_file",
                "description": "Get the content of the file managed by an agent",
                "function": self._get_agent_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID"}},
                    "required": ["agent_id"],
                },
            },
            # System Tools
            "system_status": {
                "name": "system_status",
                "description": "Get system and model status",
                "function": self._system_status,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            # Git Tools
            "git_status": {
                "name": "git_status",
                "description": "Check git repository status",
                "function": git_status,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "git_commit": {
                "name": "git_commit",
                "description": "Create git commit",
                "function": git_commit,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Commit message"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to commit (optional)",
                        },
                    },
                    "required": ["message"],
                },
            },
            "git_diff": {
                "name": "git_diff",
                "description": "Show git diff",
                "function": git_diff,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Specific file to diff (optional)"},
                        "staged": {"type": "boolean", "description": "Show staged changes"},
                    },
                    "required": [],
                },
            },
            "git_log": {
                "name": "git_log",
                "description": "Show git commit history",
                "function": git_log,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of commits to show (default: 10)"},
                        "file_path": {"type": "string", "description": "Filter by file path (optional)"},
                    },
                    "required": [],
                },
            },
            # Testing & Validation Tools
            "run_tests": {
                "name": "run_tests",
                "description": "Run pytest with optional coverage",
                "function": run_tests,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test_path": {"type": "string", "description": "Path to tests (default: src/)"},
                        "coverage": {"type": "boolean", "description": "Generate coverage report (default: true)"},
                        "verbose": {"type": "boolean", "description": "Verbose output (default: false)"},
                    },
                    "required": [],
                },
            },
            "run_pre_commit": {
                "name": "run_pre_commit",
                "description": "Run pre-commit hooks for validation",
                "function": run_pre_commit,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hook": {"type": "string", "description": "Specific hook to run (optional)"},
                        "all_files": {"type": "boolean", "description": "Run on all files (default: false)"},
                    },
                    "required": [],
                },
            },
            "validate_file_length": {
                "name": "validate_file_length",
                "description": "Validate file line counts against limits",
                "function": validate_file_length,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to validate",
                        },
                        "max_lines": {"type": "integer", "description": "Maximum lines allowed (default: 300)"},
                    },
                    "required": ["file_paths"],
                },
            },
            "validate_agent_file": {
                "name": "validate_agent_file",
                "description": "Validate agent's managed file meets requirements",
                "function": validate_agent_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID to validate"}},
                    "required": ["agent_id"],
                },
            },
            # Unified validation tool
            "run_all_validations": {
                "name": "run_all_validations",
                "description": "Run all tests, pre-commit hooks, and validations",
                "function": run_all_validations,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        }

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools with schemas"""
        return [
            {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": tool_info.get("inputSchema", {"type": "object", "properties": {}, "required": []}),
            }
            for tool_info in self.available_tools.values()
        ]

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], user_context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Execute a tool with given arguments"""
        if tool_name not in self.available_tools:
            return {
                "content": [{"type": "text", "text": f"❌ **Error:** Tool not found: {tool_name}"}],
                "isError": True,
            }

        try:
            tool_function = self.available_tools[tool_name]["function"]
            result = await tool_function(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Tool Error:** {str(e)}"}], "isError": True}

    # Agent Management Tool Implementations
    async def _create_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a new agent"""
        try:
            name = args.get("name")
            description = args.get("description")
            system_prompt = args.get("system_prompt", description)  # Use description as fallback
            managed_file = args.get("managed_file")

            # Create the agent
            agent = self.agent_registry.create_agent(
                name=name, description=description, specialized_files=[managed_file] if managed_file else []
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "✅ **Agent Created Successfully**\n\n"
                        + f"**ID:** {agent.state.agent_id}\n"
                        + f"**Name:** {agent.state.name}\n"
                        + f"**Managed File:** `{managed_file}`\n"
                        + f"**Description:** {agent.state.description}",
                    }
                ],
                "isError": False,
            }
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Create Agent Failed:** {str(e)}"}], "isError": True}

    async def _list_agents(self, args: dict[str, Any]) -> dict[str, Any]:
        """List all agents"""
        try:
            agents = self.agent_registry.list_agents()

            if not agents:
                return {
                    "content": [
                        {"type": "text", "text": "📭 **No Agents Found**\n\nNo agents are currently registered."}
                    ],
                    "isError": False,
                }

            agent_list = "📋 **Active Agents:**\n\n"
            for agent in agents:
                files = ", ".join(agent.managed_files) if agent.managed_files else "None"
                agent_list += f"• **{agent.state.agent_id}** - {agent.state.name}\n"
                agent_list += f"  📄 File: `{files}`\n"
                agent_list += f"  📝 {agent.state.description}\n"
                agent_list += f"  🔢 Interactions: {agent.state.interaction_count}\n"
                agent_list += f"  📊 Success Rate: {agent.state.success_rate:.2f}\n\n"

            return {"content": [{"type": "text", "text": agent_list}], "isError": False}
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return {"content": [{"type": "text", "text": f"❌ **List Agents Failed:** {str(e)}"}], "isError": True}

    async def _get_agent_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get agent information"""
        try:
            agent_id = args.get("agent_id")
            agent = self.agent_registry.get_agent(agent_id)

            if not agent:
                return {"content": [{"type": "text", "text": f"❌ **Agent Not Found:** {agent_id}"}], "isError": True}

            files = ", ".join(agent.managed_files) if agent.managed_files else "None"
            info = "📊 **Agent Information:**\n\n"
            info += f"**ID:** {agent.state.agent_id}\n"
            info += f"**Name:** {agent.state.name}\n"
            info += f"**Managed File:** `{files}`\n"
            info += f"**Description:** {agent.state.description}\n"
            info += f"**Created:** {agent.state.created_at}\n"
            info += f"**Last Updated:** {agent.state.last_updated}\n"
            info += f"**Total Interactions:** {agent.state.interaction_count}\n"
            info += f"**Success Rate:** {agent.state.success_rate:.2%}\n"
            info += f"**Tasks Completed:** {agent.state.total_tasks_completed}"

            return {"content": [{"type": "text", "text": info}], "isError": False}
        except Exception as e:
            logger.error(f"Failed to get agent info: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Get Agent Info Failed:** {str(e)}"}], "isError": True}

    async def _delete_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Delete an agent"""
        try:
            agent_id = args.get("agent_id")

            # Get agent info before deletion
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"content": [{"type": "text", "text": f"❌ **Agent Not Found:** {agent_id}"}], "isError": True}

            agent_name = agent.state.name

            # Delete the agent
            success = self.agent_registry.remove_agent(agent_id)

            if success:
                return {
                    "content": [{"type": "text", "text": f"✅ **Agent Deleted:** {agent_name} ({agent_id})"}],
                    "isError": False,
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"❌ **Failed to Delete Agent:** {agent_id}"}],
                    "isError": True,
                }
        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Delete Agent Failed:** {str(e)}"}], "isError": True}

    async def _chat_with_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        """Chat with an agent"""
        try:
            agent_id = args.get("agent_id")
            message = args.get("message")
            task_type_str = args.get("task_type", "conversation")

            # Map task type string to enum
            task_type_map = {
                "update": TaskType.FILE_EDIT,
                "create": TaskType.CODE_GENERATION,
                "analyze": TaskType.CONVERSATION,
                "refactor": TaskType.CODE_GENERATION,
                "debug": TaskType.CODE_GENERATION,
                "document": TaskType.CONVERSATION,
                "test": TaskType.CODE_GENERATION,
                "conversation": TaskType.CONVERSATION,
            }
            task_type = task_type_map.get(task_type_str, TaskType.CONVERSATION)

            # Get the agent
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"content": [{"type": "text", "text": f"❌ **Agent Not Found:** {agent_id}"}], "isError": True}

            # Create request
            request = AgentRequest(message=message, task_type=task_type, agent_id=agent_id)

            # Process with agent
            response = await agent.process_request(request)

            if response.success:
                return {
                    "content": [
                        {"type": "text", "text": f"💬 **Agent Response** ({agent.state.name}):\n\n{response.content}"}
                    ],
                    "isError": False,
                }
            else:
                return {
                    "content": [{"type": "text", "text": f"❌ **Agent Error:** {response.content}"}],
                    "isError": True,
                }

        except Exception as e:
            logger.error(f"Failed to chat with agent: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Chat Failed:** {str(e)}"}], "isError": True}

    async def _get_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get agent's managed file content"""
        try:
            agent_id = args.get("agent_id")

            # Get the agent
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                return {"content": [{"type": "text", "text": f"❌ **Agent Not Found:** {agent_id}"}], "isError": True}

            if not agent.managed_files:
                return {
                    "content": [
                        {"type": "text", "text": f"📭 **No Files:** Agent {agent.state.name} has no managed files"}
                    ],
                    "isError": False,
                }

            # Get the first managed file
            file_path = agent.managed_files[0] if isinstance(agent.managed_files, set) else list(agent.managed_files)[0]
            workspace_root = agent.system_config.workspace_root
            full_path = workspace_root / file_path

            if full_path.exists():
                content = full_path.read_text()
                # Truncate if too long
                if len(content) > 2000:
                    content = content[:2000] + "\n\n... [content truncated]"

                result = f"📄 **File Content:** `{file_path}`\n"
                result += f"**Size:** {len(content)} characters\n\n"
                result += f"```python\n{content}\n```"

                return {"content": [{"type": "text", "text": result}], "isError": False}
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"📄 **File:** `{file_path}`\n\n⚠️ File does not exist yet. Use chat_with_agent to create it.",
                        }
                    ],
                    "isError": False,
                }

        except Exception as e:
            logger.error(f"Failed to get agent file: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Get File Failed:** {str(e)}"}], "isError": True}

    async def _system_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get system status"""
        try:
            # Get model info
            model_info = self.llm_manager.get_model_info()

            # Get agent stats
            registry_stats = self.agent_registry.get_registry_stats()

            status = "📊 **System Status Report:**\n\n"

            # Model status
            model_status = "✅ Loaded" if model_info["model_loaded"] else "❌ Not Loaded"
            status += f"**🤖 Model Status:** {model_status}\n"
            if model_info.get("model_path"):
                status += f"**Model Path:** `{model_info['model_path']}`\n"

            # Configuration
            if model_info.get("configuration"):
                config = model_info["configuration"]
                status += f"**Context Size:** {config.get('context_size', 'N/A')} tokens\n"
                status += f"**Batch Size:** {config.get('batch_size', 'N/A')}\n"

            # Agent statistics
            status += "\n**👥 Agent Statistics:**\n"
            status += f"**Total Agents:** {registry_stats['total_agents']}\n"
            status += f"**Managed Files:** {registry_stats['managed_files']}\n"
            status += f"**Total Interactions:** {registry_stats['total_interactions']}\n"
            status += f"**Average Success Rate:** {registry_stats['average_success_rate']:.2%}\n"

            if registry_stats.get("most_active_agent"):
                status += f"**Most Active Agent:** {registry_stats['most_active_agent']}\n"

            return {"content": [{"type": "text", "text": status}], "isError": False}
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {"content": [{"type": "text", "text": f"❌ **System Status Failed:** {str(e)}"}], "isError": True}
