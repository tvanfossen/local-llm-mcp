# File: ~/Projects/local-llm-mcp/api/mcp_handler.py
"""
MCP Protocol Handler

Responsibilities:
- Handle MCP protocol requests from Claude Code
- Tool definitions and validation
- Request/response mapping between MCP and internal systems
- Error handling and response formatting for MCP
"""

import logging
from typing import Dict, Any, List

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import TaskType, create_standard_request

logger = logging.getLogger(__name__)

class MCPHandler:
    """
    Handles MCP protocol communication for Claude Code integration
    
    Provides a clean interface between Claude Code's MCP requests and
    the internal agent/LLM systems.
    """
    
    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        
        # Define available tools
        self.tools = self._define_tools()
    
    def _define_tools(self) -> List[Dict[str, Any]]:
        """Define MCP tools available to Claude Code"""
        return [
            {
                "name": "create_agent",
                "description": "Create a new agent to handle a specific file (ONE AGENT PER FILE ONLY)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Human-readable agent name"
                        },
                        "description": {
                            "type": "string",
                            "description": "What this agent does and its responsibilities"
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "LLM system prompt for this agent"
                        },
                        "managed_file": {
                            "type": "string",
                            "description": "Single file this agent manages (e.g., 'schema.sql', 'app.py')"
                        },
                        "initial_context": {
                            "type": "string",
                            "description": "Initial context or state for the agent (optional)"
                        }
                    },
                    "required": ["name", "description", "system_prompt", "managed_file"]
                }
            },
            {
                "name": "list_agents",
                "description": "List all active agents and their managed files",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_agent_info",
                "description": "Get detailed information about a specific agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to query"
                        }
                    },
                    "required": ["agent_id"]
                }
            },
            {
                "name": "chat_with_agent",
                "description": "Send a message to a specific agent in their context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to chat with"
                        },
                        "message": {
                            "type": "string",
                            "description": "Message to send to the agent"
                        },
                        "task_type": {
                            "type": "string",
                            "enum": ["create", "update", "analyze", "refactor", "debug", "document", "test"],
                            "default": "update",
                            "description": "Type of task to perform"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context for the task (optional)"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Additional parameters for the task (optional)"
                        }
                    },
                    "required": ["agent_id", "message"]
                }
            },
            {
                "name": "agent_update_file",
                "description": "Have an agent update its managed file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID"
                        },
                        "instruction": {
                            "type": "string",
                            "description": "Instructions for updating the file"
                        },
                        "current_content": {
                            "type": "string",
                            "description": "Current file content (optional, agent can read it)"
                        }
                    },
                    "required": ["agent_id", "instruction"]
                }
            },
            {
                "name": "get_agent_file",
                "description": "Get the current content of a file managed by an agent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID"
                        }
                    },
                    "required": ["agent_id"]
                }
            },
            {
                "name": "delete_agent",
                "description": "Delete an agent and free up its managed file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to delete"
                        }
                    },
                    "required": ["agent_id"]
                }
            },
            {
                "name": "system_status",
                "description": "Get system status including model and agent information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    async def handle_mcp_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming MCP requests
        
        Args:
            method: MCP method name ('list_tools' or 'call_tool')
            params: Method parameters
            
        Returns:
            MCP response dictionary
        """
        try:
            if method == "list_tools":
                return {"tools": self.tools}
            
            elif method == "call_tool":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                
                return await self._handle_tool_call(tool_name, tool_args)
            
            else:
                return self._error_response(f"Unknown MCP method: {method}")
                
        except Exception as e:
            logger.error(f"MCP request handling failed: {e}")
            return self._error_response(f"Request handling failed: {str(e)}")
    
    async def _handle_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle individual tool calls"""
        
        if tool_name == "create_agent":
            return await self._create_agent(args)
        
        elif tool_name == "list_agents":
            return await self._list_agents()
        
        elif tool_name == "get_agent_info":
            return await self._get_agent_info(args)
        
        elif tool_name == "chat_with_agent":
            return await self._chat_with_agent(args)
        
        elif tool_name == "agent_update_file":
            return await self._agent_update_file(args)
        
        elif tool_name == "get_agent_file":
            return await self._get_agent_file(args)
        
        elif tool_name == "delete_agent":
            return await self._delete_agent(args)
        
        elif tool_name == "system_status":
            return await self._system_status()
        
        else:
            return self._error_response(f"Unknown tool: {tool_name}")
    
    async def _create_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_agent tool call"""
        try:
            success, agent, error = self.agent_registry.create_agent(
                name=args["name"],
                description=args["description"],
                system_prompt=args["system_prompt"],
                managed_file=args["managed_file"],
                initial_context=args.get("initial_context", "")
            )
            
            if success:
                return self._success_response(
                    f"✅ **Agent Created Successfully**\n\n"
                    f"**ID:** {agent.state.agent_id}\n"
                    f"**Name:** {agent.state.name}\n"
                    f"**Description:** {agent.state.description}\n"
                    f"**Managed File:** {agent.state.managed_file}\n\n"
                    f"**JSON Schema:** Enabled\n"
                    f"**Rule Enforced:** One agent per file"
                )
            else:
                return self._error_response(f"❌ **Agent Creation Failed**\n\n{error}")
                
        except Exception as e:
            return self._error_response(f"❌ **Error:** {str(e)}")
    
    async def _list_agents(self) -> Dict[str, Any]:
        """Handle list_agents tool call"""
        try:
            agents = self.agent_registry.list_agents()
            
            if not agents:
                return self._success_response(
                    "📝 **No agents created yet.**\n\n"
                    "**Rule:** One agent per file, one file per agent.\n"
                    "Use `create_agent` to create your first agent."
                )
            
            # Build agent list
            agent_list = ["🤖 **Active Agents:**\n"]
            for agent in agents:
                agent_list.append(f"• **{agent.state.agent_id}** - {agent.state.name}")
                agent_list.append(f"  📄 File: `{agent.state.managed_file}`")
                agent_list.append(f"  📝 {agent.state.description}")
                agent_list.append(f"  🔢 Interactions: {agent.state.total_interactions}")
                agent_list.append(f"  📊 Success Rate: {agent.state.success_rate:.2f}")
                agent_list.append(f"  🕒 Last Active: {agent.state.last_activity}\n")
            
            # Add file ownership map
            file_map = self.agent_registry.get_file_ownership_map()
            if file_map:
                agent_list.append("\n**📂 File Ownership Map:**")
                for filename, agent_id in file_map.items():
                    agent_name = self.agent_registry.get_agent(agent_id).state.name
                    agent_list.append(f"• `{filename}` → {agent_name} ({agent_id})")
            
            return self._success_response("\n".join(agent_list))
            
        except Exception as e:
            return self._error_response(f"❌ **Failed to list agents:** {str(e)}")
    
    async def _get_agent_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_agent_info tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return self._error_response(f"❌ Agent `{agent_id}` not found")
            
            summary = agent.get_summary()
            
            info_text = f"🤖 **Agent Information: {agent.state.name}**\n\n"
            info_text += f"**ID:** {agent.state.agent_id}\n"
            info_text += f"**Description:** {agent.state.description}\n"
            info_text += f"**Managed File:** `{agent.state.managed_file}`\n"
            info_text += f"**File Exists:** {'✅' if summary['file_exists'] else '❌'}\n"
            
            if summary['file_size']:
                info_text += f"**File Size:** {summary['file_size']} bytes\n"
            
            info_text += f"**Total Interactions:** {summary['total_interactions']}\n"
            info_text += f"**Success Rate:** {summary['success_rate']:.2f}\n"
            info_text += f"**Conversation Entries:** {summary['conversation_entries']}\n"
            info_text += f"**Context Length:** {summary['context_length']} chars\n"
            info_text += f"**Created:** {agent.state.created_at}\n"
            info_text += f"**Last Active:** {agent.state.last_activity}\n"
            info_text += f"**Workspace:** `{agent.workspace_dir}`"
            
            return self._success_response(info_text)
            
        except Exception as e:
            return self._error_response(f"❌ **Failed to get agent info:** {str(e)}")
    
    async def _chat_with_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat_with_agent tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return self._error_response(f"❌ Agent `{agent_id}` not found")
            
            if not self.llm_manager.model_loaded:
                return self._error_response("❌ Model not loaded")
            
            # Create standardized request
            agent_request = create_standard_request(
                task_type=TaskType(args.get("task_type", "update")),
                instruction=args["message"],
                context=args.get("context"),
                parameters=args.get("parameters", {})
            )
            
            # Generate response
            prompt = agent.build_context_prompt(agent_request)
            agent_response, metrics = await self.llm_manager.generate_response(prompt)
            
            # Update agent
            agent.update_activity(agent_request.task_type)
            agent.update_success_rate(agent_response.status.value == "success")
            agent.add_conversation(agent_request, agent_response)
            
            # Save state
            self.agent_registry.save_registry()
            
            # Format response for MCP
            result_text = f"🤖 **Agent {agent.state.name} ({agent_id}):**\n\n"
            result_text += f"**Status:** {agent_response.status.value}\n"
            result_text += f"**Response:** {agent_response.message}\n\n"
            
            if agent_response.file_content:
                result_text += f"**File Updated:** `{agent_response.file_content.filename}`\n"
            
            if agent_response.changes_made:
                result_text += f"**Changes:** {', '.join(agent_response.changes_made)}\n"
            
            if agent_response.warnings:
                result_text += f"**⚠️ Warnings:** {', '.join(agent_response.warnings)}\n"
            
            result_text += f"\n*📊 Tokens: {agent_response.tokens_used} | ⏱️ Time: {agent_response.processing_time:.1f}s*"
            
            return self._success_response(result_text)
            
        except Exception as e:
            return self._error_response(f"❌ **Chat failed:** {str(e)}")
    
    async def _agent_update_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent_update_file tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return self._error_response(f"❌ Agent `{agent_id}` not found")
            
            # Build file update instruction
            instruction = args["instruction"]
            current_content = args.get("current_content", "") or agent.read_managed_file() or ""
            
            file_update_prompt = f"Update your managed file `{agent.state.managed_file}` according to these instructions:\n\n{instruction}\n\n"
            
            if current_content:
                file_update_prompt += f"Current file content:\n```\n{current_content}\n```\n\n"
            
            file_update_prompt += "Provide the complete updated file content in your JSON response under 'file_content'."
            
            # Use chat functionality for file update
            chat_result = await self._chat_with_agent({
                "agent_id": agent_id,
                "message": file_update_prompt,
                "task_type": "update",
                "parameters": {"file_operation": "update"}
            })
            
            # Check if file was actually updated by examining the response
            if "File Updated:" in chat_result.get("content", [{}])[0].get("text", ""):
                return self._success_response(
                    f"✅ **File Update Completed**\n\n"
                    f"Agent `{agent.state.name}` has updated `{agent.state.managed_file}`.\n\n"
                    f"{chat_result['content'][0]['text']}"
                )
            else:
                return self._success_response(
                    f"⚠️ **File Update Response**\n\n"
                    f"{chat_result['content'][0]['text']}"
                )
            
        except Exception as e:
            return self._error_response(f"❌ **File update failed:** {str(e)}")
    
    async def _get_agent_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_agent_file tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return self._error_response(f"❌ Agent `{agent_id}` not found")
            
            file_content = agent.read_managed_file()
            filename = agent.state.managed_file
            
            if file_content is None:
                return self._success_response(
                    f"📄 **File Status:** `{filename}`\n\n"
                    f"Agent: {agent.state.name} ({agent_id})\n"
                    f"File does not exist yet.\n\n"
                    f"*Use `agent_update_file` to create the file.*"
                )
            
            # Determine file language for syntax highlighting
            file_ext = filename.split('.')[-1].lower() if '.' in filename else 'text'
            language_map = {
                'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                'html': 'html', 'css': 'css', 'sql': 'sql',
                'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
                'md': 'markdown', 'sh': 'bash'
            }
            language = language_map.get(file_ext, file_ext)
            
            return self._success_response(
                f"📄 **File Content:** `{filename}`\n\n"
                f"**Agent:** {agent.state.name} ({agent_id})\n"
                f"**Size:** {len(file_content)} characters\n\n"
                f"```{language}\n{file_content}\n```"
            )
            
        except Exception as e:
            return self._error_response(f"❌ **Failed to read file:** {str(e)}")
    
    async def _delete_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_agent tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return self._error_response(f"❌ Agent `{agent_id}` not found")
            
            agent_name = agent.state.name
            managed_file = agent.state.managed_file
            
            success, error = self.agent_registry.delete_agent(agent_id)
            
            if success:
                return self._success_response(
                    f"✅ **Agent Deleted Successfully**\n\n"
                    f"**Deleted:** {agent_name} (ID: {agent_id})\n"
                    f"**File Released:** `{managed_file}`\n\n"
                    f"The file `{managed_file}` is now available for a new agent.\n"
                    f"Workspace preserved at `workspaces/{agent_id}/`"
                )
            else:
                return self._error_response(f"❌ **Deletion failed:** {error}")
                
        except Exception as e:
            return self._error_response(f"❌ **Error:** {str(e)}")
    
    async def _system_status(self) -> Dict[str, Any]:
        """Handle system_status tool call"""
        try:
            # Get model info
            model_info = self.llm_manager.get_model_info()
            performance = self.llm_manager.get_performance_summary()
            
            # Get agent registry stats
            registry_stats = self.agent_registry.get_registry_stats()
            
            # Build status report
            status_text = f"🖥️ **System Status Report**\n\n"
            
            # Model status
            status_text += f"**🤖 Model Status:** {'✅ Loaded' if model_info['model_loaded'] else '❌ Not Loaded'}\n"
            if model_info['model_loaded']:
                status_text += f"**Model Path:** `{model_info['model_path']}`\n"
                status_text += f"**GPU Layers:** {model_info['configuration']['gpu_layers']}\n"
                status_text += f"**Context Size:** {model_info['configuration']['context_size']}\n"
                status_text += f"**Performance:** {performance.get('avg_tokens_per_second', 0)} tokens/sec\n"
            
            status_text += f"\n**👥 Agent Registry:**\n"
            status_text += f"**Total Agents:** {registry_stats['total_agents']}\n"
            status_text += f"**Managed Files:** {registry_stats['managed_files']}\n"
            status_text += f"**Total Interactions:** {registry_stats['total_interactions']}\n"
            status_text += f"**Average Success Rate:** {registry_stats['average_success_rate']:.2f}\n"
            
            if registry_stats['most_active_agent']:
                most_active = registry_stats['most_active_agent']
                status_text += f"**Most Active Agent:** {most_active['name']} ({most_active['interactions']} interactions)\n"
            
            status_text += f"\n**📊 Performance Metrics:**\n"
            if model_info['model_loaded']:
                status_text += f"**Inference Count:** {performance.get('total_inferences', 0)}\n"
                status_text += f"**Total Tokens Generated:** {performance.get('total_tokens', 0)}\n"
                status_text += f"**Efficiency:** {performance.get('efficiency', 'unknown')}\n"
            
            status_text += f"\n**🔧 System Configuration:**\n"
            status_text += f"**CUDA Optimized:** ✅ RTX 1080ti + CUDA 12.9\n"
            status_text += f"**JSON Schema:** ✅ Enabled\n"
            status_text += f"**File Ownership:** ✅ One agent per file enforced\n"
            
            return self._success_response(status_text)
            
        except Exception as e:
            return self._error_response(f"❌ **System status check failed:** {str(e)}")
    
    def _success_response(self, text: str) -> Dict[str, Any]:
        """Create successful MCP response"""
        return {
            "content": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
    
    def _error_response(self, text: str) -> Dict[str, Any]:
        """Create error MCP response"""
        return {
            "content": [
                {
                    "type": "text", 
                    "text": text
                }
            ],
            "isError": True
        }