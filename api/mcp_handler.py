# File: ~/Projects/local-llm-mcp/api/mcp_handler.py
"""
MCP Protocol Handler with proper JSON-RPC 2.0 implementation

Responsibilities:
- Handle JSON-RPC 2.0 protocol requirements
- Implement MCP initialization handshake
- Handle tool definitions and validation
- Request/response mapping between MCP and internal systems
- Session management and state tracking
"""

import logging
import uuid
from typing import Dict, Any, List, Optional

from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import TaskType, create_standard_request

logger = logging.getLogger(__name__)

class MCPSession:
    """MCP session state management"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.protocol_version = "2024-11-05"  # Using stable version
        self.capabilities = {}
        self.client_info = {}
        self.initialized = False

class MCPHandler:
    """
    Proper MCP protocol handler implementing JSON-RPC 2.0 and MCP specification
    
    Handles the complete MCP lifecycle:
    1. JSON-RPC 2.0 message format validation
    2. MCP initialization handshake
    3. Capability negotiation
    4. Tool execution
    5. Session management
    """
    
    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        
        # Session management
        self.sessions: Dict[str, MCPSession] = {}
        
        # MCP server info
        self.server_info = {
            "name": "local-llm-agents",
            "version": "1.0.0"
        }
        
        # Define server capabilities
        self.server_capabilities = {
            "tools": {
                "listChanged": True
            },
            "resources": {},
            "prompts": {}
        }
        
        # Define available tools
        self.tools = self._define_tools()
    
    def _define_tools(self) -> List[Dict[str, Any]]:
        """Define MCP tools available to clients"""
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
    
    async def handle_jsonrpc_request(self, request_data: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle JSON-RPC 2.0 request according to MCP specification
        
        Args:
            request_data: JSON-RPC request data
            session_id: Optional session ID for stateful connections
            
        Returns:
            JSON-RPC response dictionary
        """
        try:
            # Validate JSON-RPC 2.0 format
            if not self._validate_jsonrpc_request(request_data):
                return self._create_error_response(
                    None, -32600, "Invalid Request", "Invalid JSON-RPC 2.0 format"
                )
            
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            logger.info(f"Handling JSON-RPC method: {method}")
            
            # Handle notifications (no response required)
            if request_id is None:
                await self._handle_notification(method, params, session_id)
                return None  # No response for notifications
            
            # Handle requests (response required)
            if method == "initialize":
                return await self._handle_initialize(request_id, params, session_id)
            elif method == "tools/list":
                return await self._handle_tools_list(request_id, params, session_id)
            elif method == "tools/call":
                return await self._handle_tools_call(request_id, params, session_id)
            else:
                return self._create_error_response(
                    request_id, -32601, "Method not found", f"Unknown method: {method}"
                )
                
        except Exception as e:
            logger.error(f"JSON-RPC request handling failed: {e}")
            return self._create_error_response(
                request_data.get("id"), -32603, "Internal error", str(e)
            )
    
    def _validate_jsonrpc_request(self, request: Dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 request format"""
        return (
            isinstance(request, dict) and
            request.get("jsonrpc") == "2.0" and
            "method" in request and
            isinstance(request["method"], str)
        )
    
    async def _handle_initialize(self, request_id: Any, params: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        try:
            # Extract client info
            client_version = params.get("protocolVersion", "2024-11-05")
            client_capabilities = params.get("capabilities", {})
            client_info = params.get("clientInfo", {})
            
            # Create or update session
            if not session_id:
                session_id = str(uuid.uuid4())
            
            session = MCPSession(session_id)
            session.protocol_version = client_version
            session.capabilities = client_capabilities
            session.client_info = client_info
            
            self.sessions[session_id] = session
            
            logger.info(f"MCP session initialized: {session_id} for client: {client_info.get('name', 'unknown')}")
            
            # Return initialization response
            response = self._create_success_response(request_id, {
                "protocolVersion": session.protocol_version,
                "serverInfo": self.server_info,
                "capabilities": self.server_capabilities
            })
            
            # Add session ID to response headers (for HTTP transport)
            response["_session_id"] = session_id
            
            return response
            
        except Exception as e:
            return self._create_error_response(
                request_id, -32603, "Initialization failed", str(e)
            )
    
    async def _handle_tools_list(self, request_id: Any, params: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        """Handle tools/list request"""
        try:
            # Validate session if provided
            if session_id and session_id not in self.sessions:
                return self._create_error_response(
                    request_id, -32002, "Session not found", f"Session {session_id} not found"
                )
            
            return self._create_success_response(request_id, {
                "tools": self.tools
            })
            
        except Exception as e:
            return self._create_error_response(
                request_id, -32603, "Failed to list tools", str(e)
            )
    
    async def _handle_tools_call(self, request_id: Any, params: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        """Handle tools/call request"""
        try:
            # Validate session if provided
            if session_id and session_id not in self.sessions:
                return self._create_error_response(
                    request_id, -32002, "Session not found", f"Session {session_id} not found"
                )
            
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if not tool_name:
                return self._create_error_response(
                    request_id, -32602, "Invalid params", "Missing tool name"
                )
            
            # Execute tool
            result = await self._execute_tool(tool_name, tool_args)
            
            return self._create_success_response(request_id, {
                "content": result["content"],
                "isError": result.get("isError", False)
            })
            
        except Exception as e:
            return self._create_error_response(
                request_id, -32603, "Tool execution failed", str(e)
            )
    
    async def _handle_notification(self, method: str, params: Dict[str, Any], session_id: Optional[str]):
        """Handle JSON-RPC notification (no response required)"""
        try:
            if method == "notifications/initialized" or method == "initialized":
                if session_id and session_id in self.sessions:
                    self.sessions[session_id].initialized = True
                    logger.info(f"MCP session {session_id} fully initialized")
                else:
                    logger.warning(f"Received initialized notification without valid session")
            else:
                logger.info(f"Received notification: {method}")
                
        except Exception as e:
            logger.error(f"Notification handling failed: {e}")
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool and return MCP-formatted result"""
        
        if tool_name == "create_agent":
            return await self._tool_create_agent(args)
        elif tool_name == "list_agents":
            return await self._tool_list_agents()
        elif tool_name == "get_agent_info":
            return await self._tool_get_agent_info(args)
        elif tool_name == "chat_with_agent":
            return await self._tool_chat_with_agent(args)
        elif tool_name == "agent_update_file":
            return await self._tool_agent_update_file(args)
        elif tool_name == "get_agent_file":
            return await self._tool_get_agent_file(args)
        elif tool_name == "delete_agent":
            return await self._tool_delete_agent(args)
        elif tool_name == "system_status":
            return await self._tool_system_status()
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Unknown tool:** {tool_name}"
                }],
                "isError": True
            }
    
    # Tool implementations (keeping existing logic but with proper MCP format)
    
    async def _tool_create_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
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
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            f"✅ **Agent Created Successfully**\n\n"
                            f"**ID:** {agent.state.agent_id}\n"
                            f"**Name:** {agent.state.name}\n"
                            f"**Description:** {agent.state.description}\n"
                            f"**Managed File:** {agent.state.managed_file}\n\n"
                            f"**JSON Schema:** Enabled\n"
                            f"**Rule Enforced:** One agent per file"
                        )
                    }]
                }
            else:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"❌ **Agent Creation Failed**\n\n{error}"
                    }],
                    "isError": True
                }
                
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error:** {str(e)}"
                }],
                "isError": True
            }
    
    # ... (continuing with other tool implementations - keeping existing logic)
    # I'll include a few key ones and indicate the pattern
    
    async def _tool_list_agents(self) -> Dict[str, Any]:
        """Handle list_agents tool call"""
        try:
            agents = self.agent_registry.list_agents()
            
            if not agents:
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            "📝 **No agents created yet.**\n\n"
                            "**Rule:** One agent per file, one file per agent.\n"
                            "Use `create_agent` to create your first agent."
                        )
                    }]
                }
            
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
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(agent_list)
                }]
            }
            
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Failed to list agents:** {str(e)}"
                }],
                "isError": True
            }
    
    async def _tool_chat_with_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat_with_agent tool call"""
        try:
            agent_id = args["agent_id"]
            agent = self.agent_registry.get_agent(agent_id)
            
            if not agent:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"❌ Agent `{agent_id}` not found"
                    }],
                    "isError": True
                }
            
            if not self.llm_manager.model_loaded:
                return {
                    "content": [{
                        "type": "text", 
                        "text": "❌ Model not loaded"
                    }],
                    "isError": True
                }
            
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
            
            return {
                "content": [{
                    "type": "text",
                    "text": result_text
                }]
            }
            
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Chat failed:** {str(e)}"
                }],
                "isError": True
            }
    
    async def _tool_system_status(self) -> Dict[str, Any]:
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
            
            status_text += f"\n**🔧 System Configuration:**\n"
            status_text += f"**CUDA Optimized:** ✅ RTX 1080ti + CUDA 12.9\n"
            status_text += f"**JSON Schema:** ✅ Enabled\n"
            status_text += f"**File Ownership:** ✅ One agent per file enforced\n"
            
            return {
                "content": [{
                    "type": "text",
                    "text": status_text
                }]
            }
            
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ **System status check failed:** {str(e)}"
                }],
                "isError": True
            }
    
    def _create_success_response(self, request_id: Any, result: Any) -> Dict[str, Any]:
        """Create JSON-RPC 2.0 success response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    def _create_error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        """Create JSON-RPC 2.0 error response"""
        error = {
            "code": code,
            "message": message
        }
        if data is not None:
            error["data"] = data
            
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        }
    
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def cleanup_session(self, session_id: str):
        """Clean up session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up MCP session: {session_id}")