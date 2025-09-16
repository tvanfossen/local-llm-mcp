# File: ~/Projects/local-llm-mcp/src/core/agents/agent/agent.py
"""Agent Class with Direct Repository File Access

Responsibilities:
- Individual agent state and behavior with direct workspace file access
- JSON schema-compliant conversation management
- Direct file editing in workspace root (not agent subdirectories)
- Agent metadata storage in .mcp-agents/{agent_id}/ structure
- Context building for LLM prompts
- Persistence and serialization with environment detection
Workspace: Direct file access via SystemConfig workspace root detection
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.core.config.manager.manager import SystemConfig
from src.core.files.json_file_manager import JsonFileManager
from src.schemas.agents.agents import (
    AgentRequest,
    AgentResponse,
    AgentState,
    ConversationEntry,
    TaskType,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentCreateParams:
    """Parameters for creating a new agent"""

    name: str
    description: str
    system_config: SystemConfig
    specialized_files: list[str] = None
    max_conversation_length: int = 100


class Agent:
    """Agent with direct repository file access and JSON schema compliance"""

    def __init__(self, state: AgentState, system_config: SystemConfig, llm_manager=None, tool_executor=None):
        self.state = state
        self.system_config = system_config
        self.llm_manager = llm_manager
        self.tool_executor = tool_executor
        self.conversation_history: list[ConversationEntry] = []
        self.managed_files: set[str] = set(state.managed_files)

        # Setup agent directory structure
        self.agent_dir = system_config.agents_dir / state.agent_id
        self.metadata_file = self.agent_dir / "metadata.json"
        self.conversation_file = self.agent_dir / "conversation.json"

        # Setup logging
        self.logger = self._setup_logging()

        # Initialize JSON file manager for structured code generation
        workspace_path = getattr(system_config, 'workspace_root', '/workspace')
        templates_path = 'templates'
        self.json_file_manager = JsonFileManager(workspace_path, templates_path)

        # Load existing data
        self._load_conversation_history()

        self.logger.info(f"Agent initialized: {state.name}")
        self.logger.info(f"Workspace root: {system_config.workspace_root}")
        self.logger.info(f"Agent directory: {self.agent_dir}")

    def _setup_logging(self) -> logging.Logger:
        """Setup agent-specific logging"""
        agent_logger = logging.getLogger(f"agent.{self.state.agent_id}")

        # Create agent log directory with proper permissions
        log_dir = self.system_config.logs_dir / self.state.agent_id
        log_dir.mkdir(parents=True, exist_ok=True)

        # Ensure log directory is writable (fixes container permission issues)
        import os
        import stat

        try:
            os.chmod(log_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        except (OSError, PermissionError):
            # If we can't set permissions, continue but log the issue
            temp_logger = logging.getLogger(__name__)
            temp_logger.warning(f"Could not set permissions on log directory: {log_dir}")

        # Add file handler for agent-specific logs
        log_file = log_dir / f"{self.state.name.lower().replace(' ', '_')}.log"

        try:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            agent_logger.addHandler(handler)
        except (OSError, PermissionError) as e:
            # If we can't create log file due to permissions, use console logging only
            temp_logger = logging.getLogger(__name__)
            temp_logger.warning(f"Could not create log file {log_file}: {e}. Agent will use console logging only.")

        agent_logger.setLevel(logging.INFO)

        return agent_logger

    @classmethod
    def create(cls, params: AgentCreateParams, llm_manager=None, tool_executor=None) -> "Agent":
        """Create a new agent with fresh state"""
        state = AgentState(
            agent_id=cls._generate_agent_id(),
            name=params.name,
            description=params.description,
            managed_files=params.specialized_files or [],
            created_at=datetime.now(timezone.utc).isoformat(),
            last_updated=datetime.now(timezone.utc).isoformat(),
            interaction_count=0,
            success_rate=0.0,
            total_tasks_completed=0,
            recent_interactions=[],
        )

        agent = cls(state, params.system_config, llm_manager, tool_executor)
        agent._save_metadata()
        return agent

    @classmethod
    def from_json(
        cls, data: dict[str, Any], system_config: SystemConfig, llm_manager=None, tool_executor=None
    ) -> "Agent":
        """Load agent from JSON data"""
        state = AgentState(**data)
        return cls(state, system_config, llm_manager, tool_executor)

    @classmethod
    def load_from_disk(
        cls, agent_id: str, system_config: SystemConfig, llm_manager=None, tool_executor=None
    ) -> "Agent":
        """Load agent from disk by ID"""
        agent_dir = system_config.agents_dir / agent_id
        metadata_file = agent_dir / "metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Agent metadata not found: {metadata_file}")

        with open(metadata_file) as f:
            data = json.load(f)

        return cls.from_json(data, system_config, llm_manager, tool_executor)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process agent request with conversation tracking"""
        self.logger.info(f"Processing {request.task_type.value} request: {request.message}")

        try:
            # Add user message to conversation
            user_entry = ConversationEntry(
                role="user",
                content=request.message,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._add_conversation_entry(user_entry)

            # Process the request based on task type
            response = await self._execute_task(request)

            # Add assistant response to conversation
            assistant_entry = ConversationEntry(
                role="assistant",
                content=response.content,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._add_conversation_entry(assistant_entry)

            # Update statistics
            self._update_interaction_stats(response.success)

            return response

        except Exception as e:
            self.logger.error(f"Request processing failed: {e}")
            error_response = AgentResponse(
                success=False,
                content=f"Error processing request: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Still track failed interactions
            self._update_interaction_stats(False)
            return error_response

    async def _execute_task(self, request: AgentRequest) -> AgentResponse:
        """Execute task based on request type"""
        # Route all file operations to code generation for JSON metadata + tool calls
        if request.task_type in [TaskType.FILE_EDIT, TaskType.CODE_GENERATION]:
            self.logger.info(f"Routing {request.task_type} to code generation with tool calling")
            return await self._handle_code_generation(request)
        elif request.task_type == TaskType.CONVERSATION:
            return await self._handle_conversation(request)
        else:
            raise ValueError(f"Unsupported task type: {request.task_type}")

    async def _handle_file_edit(self, request: AgentRequest) -> AgentResponse:
        """Handle file editing requests using tool executor for actual file operations"""
        if not self.tool_executor:
            return AgentResponse(
                success=False,
                content="Agent not properly initialized with tool executor",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            self.logger.info(f"Executing file edit request: {request.message}")

            # Parse the request to determine what file operations are needed
            request_lower = request.message.lower()

            # Handle file operations based on request content
            if "create" in request_lower or "write" in request_lower:
                return await self._create_file_from_request(request)
            elif "read" in request_lower or "show" in request_lower:
                return await self._handle_file_read(request)
            elif "list" in request_lower or "directory" in request_lower:
                return await self._handle_directory_list(request)
            else:
                # Generic file operation - analyze and execute
                return await self._analyze_and_execute_file_operation(request)

        except Exception as e:
            self.logger.error(f"File edit handling failed: {e}")
            return AgentResponse(
                success=False,
                content=f"Error handling file edit: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
        """Handle code generation by creating JSON metadata first, then using LLM with tool calls"""
        self.logger.debug(f"ENTRY _handle_code_generation: request={request.message}")

        if not self.llm_manager:
            error = "LLM manager not available"
            self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
            return AgentResponse(
                success=False,
                content=error,
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            # Use the first managed file as the target file
            if self.state.managed_files and len(self.state.managed_files) > 0:
                filename = self.state.managed_files[0]
            else:
                error = "No managed files configured for agent"
                self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                return AgentResponse(
                    success=False,
                    content=error,
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            self.logger.info(f"Creating metadata for {filename} based on request: {request.message}")

            # Build context for LLM
            context = self.get_context_for_llm()

            # Create prompt for LLM to generate tool calls
            tool_calling_prompt = f"""Context: {context}
Task: Create file {filename} using MCP tools
Request: {request.message}

You must use tool calls to complete this task. Follow this workflow:
1. Use workspace tool to write the Python file with requested functionality
2. Use validation tool to test the code works correctly
3. Use git_operations tool to commit the working code if validation passes

Generate the Python code for {filename} that implements: {request.message}

Make your first tool call now:"""

            # Generate response using LLM with tool calling
            self.logger.info(f"Calling LLM with tool calling enabled for {filename}")

            if self.llm_manager and self.llm_manager.model_loaded:
                response = await self.llm_manager.generate_with_tools(
                    tool_calling_prompt, max_tokens=2048, temperature=0.3, tools_enabled=True
                )

                self.logger.info(f"LLM response: {response.get('type', 'unknown')} (success: {response.get('success', False)})")

                if response.get("success"):
                    if response.get("type") == "tool_calls":
                        # Tool calls were made and executed
                        tool_calls = response.get("tool_calls", [])
                        results = response.get("results", [])

                        self.logger.info(f"✅ Tool calls executed: {len(tool_calls)} calls, {len(results)} results")

                        # Check if workspace tool was called successfully
                        workspace_success = any(
                            r.get("success") and r.get("tool_name") == "workspace"
                            for r in results
                        )

                        if workspace_success:
                            self.logger.debug(f"EXIT _handle_code_generation: SUCCESS - workspace tool executed")
                            return AgentResponse(
                                success=True,
                                content=f"✅ Code generation completed for {filename} using MCP tool calls",
                                agent_id=self.state.agent_id,
                                task_type=request.task_type,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                files_modified=[filename],
                            )
                        else:
                            error = "Workspace tool calls failed"
                            self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                            return AgentResponse(
                                success=False,
                                content=f"❌ {error}: {[r.get('error') for r in results if not r.get('success')]}",
                                agent_id=self.state.agent_id,
                                task_type=request.task_type,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            )
                    elif response.get("type") == "text":
                        # Model generated text instead of tool calls - fail explicitly
                        error = "Model generated text instead of required tool calls"
                        self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                        return AgentResponse(
                            success=False,
                            content=f"❌ {error}. Expected workspace tool calls but got text response.",
                            agent_id=self.state.agent_id,
                            task_type=request.task_type,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    else:
                        error = f"Unknown response type: {response.get('type')}"
                        self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                        return AgentResponse(
                            success=False,
                            content=f"❌ {error}",
                            agent_id=self.state.agent_id,
                            task_type=request.task_type,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                else:
                    error = f"LLM generation failed: {response.get('error', 'Unknown error')}"
                    self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                    return AgentResponse(
                        success=False,
                        content=f"❌ {error}",
                        agent_id=self.state.agent_id,
                        task_type=request.task_type,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
            else:
                error = "LLM not available or not loaded"
                self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
                return AgentResponse(
                    success=False,
                    content=f"❌ {error}",
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        except Exception as e:
            self.logger.exception(f"EXIT _handle_code_generation: EXCEPTION - {e}")
            return AgentResponse(
                success=False,
                content=f"❌ Error in code generation: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )


    async def _handle_conversation(self, request: AgentRequest) -> AgentResponse:
        """Handle general conversation requests using LLM"""
        if not self.llm_manager:
            return AgentResponse(
                success=False,
                content="Agent not properly initialized with LLM manager",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            # Build context for LLM
            context = self.get_context_for_llm()

            # Create prompt for conversation
            prompt = f"""Context: {context}

Task: General conversation
Request: {request.message}

You are an AI agent having a conversation. Respond helpfully and naturally based on your context and role.
Use your knowledge of the workspace and managed files to provide relevant responses."""

            # Get response from LLM if loaded, otherwise provide structured response
            if self.llm_manager.model_loaded:
                llm_response = self.llm_manager.llm(prompt, max_tokens=256, temperature=0.7)
                content = llm_response["choices"][0]["text"].strip()
            else:
                content = f"Conversation response: {request.message} (mock mode - LLM not loaded)"

            return AgentResponse(
                success=True,
                content=content,
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            self.logger.error(f"Conversation handling failed: {e}")
            return AgentResponse(
                success=False,
                content=f"Error handling conversation: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def _add_conversation_entry(self, entry: ConversationEntry):
        """Add entry to conversation history with size management"""
        self.conversation_history.append(entry)

        # Limit conversation history size
        max_length = 200  # Keep last 200 entries
        if len(self.conversation_history) > max_length:
            self.conversation_history = self.conversation_history[-max_length:]

        # Persist to disk periodically
        if len(self.conversation_history) % 10 == 0:
            self._save_conversation_history()

    def _update_interaction_stats(self, success: bool):
        """Update interaction statistics"""
        self.state.interaction_count += 1

        if success:
            self.state.total_tasks_completed += 1

        # Calculate success rate
        self.state.success_rate = self.state.total_tasks_completed / self.state.interaction_count

        # Update timestamp
        self.state.last_updated = datetime.now(timezone.utc).isoformat()

        # Add to recent interactions (keep last 10)
        interaction_summary = {
            "timestamp": self.state.last_updated,
            "success": success,
            "type": "task_execution",
        }

        self.state.recent_interactions.append(interaction_summary)
        if len(self.state.recent_interactions) > 10:
            self.state.recent_interactions = self.state.recent_interactions[-10:]

        # Save updated metadata
        self._save_metadata()

    def _save_metadata(self):
        """Save agent metadata to disk"""
        self.agent_dir.mkdir(parents=True, exist_ok=True)

        with open(self.metadata_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

        self.logger.debug(f"Metadata saved to {self.metadata_file}")

    def _load_conversation_history(self):
        """Load conversation history from disk"""
        if self.conversation_file.exists():
            try:
                with open(self.conversation_file) as f:
                    data = json.load(f)
                    self.conversation_history = [ConversationEntry(**entry) for entry in data]
                self.logger.info(f"Loaded {len(self.conversation_history)} conversation entries")
            except Exception as e:
                self.logger.warning(f"Failed to load conversation history: {e}")
                self.conversation_history = []

    def _save_conversation_history(self):
        """Save conversation history to disk"""
        self.agent_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.conversation_file, "w") as f:
                json.dump([entry.to_dict() for entry in self.conversation_history], f, indent=2)
            self.logger.debug("Conversation history saved")
        except Exception as e:
            self.logger.error(f"Failed to save conversation history: {e}")

    async def _create_file_from_request(self, request: AgentRequest) -> AgentResponse:
        """Create the agent's managed file based on the request content"""
        # Agent should NOT generate final files - only JSON metadata
        # Route to code generation which creates JSON metadata for workspace tool
        return await self._handle_code_generation(request)


    async def _handle_file_creation(self, request: AgentRequest) -> AgentResponse:
        """Handle generic file creation requests"""
        self.logger.debug(f"ENTRY _handle_file_creation: request={request.message}")

        # Route all file creation through code generation workflow
        # This ensures metadata-first approach and proper tool calling
        result = await self._handle_code_generation(request)

        self.logger.debug(f"EXIT _handle_file_creation: success={result.success}")
        return result

    async def _handle_file_read(self, request: AgentRequest) -> AgentResponse:
        """Handle file reading requests via workspace tool"""
        self.logger.debug(f"ENTRY _handle_file_read: request={request.message}")

        if not self.tool_executor:
            error = "Tool executor not available for file reading"
            self.logger.error(f"EXIT _handle_file_read: FAILED - {error}")

            from src.core.exceptions import ToolNotAvailable
            raise ToolNotAvailable("workspace", ["workspace tool required for file operations"])

        try:
            # Extract file path from request (simple heuristic)
            # In production, this would be more sophisticated
            message_words = request.message.split()
            file_path = None

            # Look for file-like patterns
            for word in message_words:
                if '.' in word and '/' in word:  # Likely a file path
                    file_path = word
                    break

            if not file_path:
                # Default to agent's managed files
                if self.state.managed_files:
                    file_path = list(self.state.managed_files)[0]
                else:
                    error = "No file path specified and no managed files"
                    self.logger.error(f"EXIT _handle_file_read: FAILED - {error}")
                    return AgentResponse(
                        success=False,
                        content=f"❌ {error}. Please specify a file path.",
                        agent_id=self.state.agent_id,
                        task_type=request.task_type,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )

            self.logger.info(f"📖 Reading file: {file_path}")

            # Execute workspace read operation
            read_result = await self.tool_executor.execute_tool("workspace", {
                "action": "read",
                "path": file_path
            })

            if read_result.get("success", False):
                content = f"📄 **File: {file_path}**\n\n{read_result.get('content', 'No content')}"
                self.logger.info(f"✅ File read successful: {len(content)} characters")

                result = AgentResponse(
                    success=True,
                    content=content,
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    files_modified=[file_path]
                )
            else:
                error = read_result.get("error", "File read failed")
                self.logger.error(f"❌ File read failed: {error}")

                result = AgentResponse(
                    success=False,
                    content=f"❌ Failed to read {file_path}: {error}",
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            self.logger.debug(f"EXIT _handle_file_read: success={result.success}")
            return result

        except Exception as e:
            error = f"File read operation failed: {str(e)}"
            self.logger.error(f"EXIT _handle_file_read: EXCEPTION - {e}")
            return AgentResponse(
                success=False,
                content=f"❌ {error}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    async def _handle_directory_list(self, request: AgentRequest) -> AgentResponse:
        """Handle directory listing requests"""
        try:
            # Execute workspace list operation
            list_result = await self.tool_executor.execute_tool(
                "workspace", {"action": "list", "path": ".", "include_hidden": False}
            )

            if list_result.get("success"):
                return AgentResponse(
                    success=True,
                    content=f"📁 Directory listing:\n{list_result.get('message', 'No content')}",
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            else:
                return AgentResponse(
                    success=False,
                    content=f"❌ Failed to list directory: {list_result.get('error', 'Unknown error')}",
                    agent_id=self.state.agent_id,
                    task_type=request.task_type,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
        except Exception as e:
            return AgentResponse(
                success=False,
                content=f"❌ Error listing directory: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    async def _analyze_and_execute_file_operation(self, request: AgentRequest) -> AgentResponse:
        """Analyze request and execute appropriate file operations"""
        self.logger.debug(f"ENTRY _analyze_and_execute_file_operation: request={request.message}")

        error = "Generic file operation analysis not implemented"
        self.logger.error(f"EXIT _analyze_and_execute_file_operation: FAILED - {error}")

        return AgentResponse(
            success=False,
            content=f"❌ {error}",
            agent_id=self.state.agent_id,
            task_type=request.task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"error_type": "not_implemented", "operation": "analyze_file_operation"}
        )

    def get_context_for_llm(self) -> str:
        """Build context string for LLM prompt"""
        context_parts = [
            f"Agent: {self.state.name}",
            f"Description: {self.state.description}",
            f"Workspace: {self.system_config.workspace_root}",
        ]

        if self.managed_files:
            context_parts.append(f"Managed files: {', '.join(sorted(self.managed_files))}")

        # Add recent conversation context (last 10 entries)
        recent_conversation = self.conversation_history[-10:]
        if recent_conversation:
            context_parts.append("Recent conversation:")
            for entry in recent_conversation:
                context_parts.append(f"{entry.role}: {entry.content[:200]}...")

        return "\n".join(context_parts)

    def add_managed_file(self, file_path: str):
        """Add file to managed files list"""
        self.managed_files.add(file_path)
        self.state.managed_files = list(self.managed_files)
        self._save_metadata()
        self.logger.info(f"Added managed file: {file_path}")

    def remove_managed_file(self, file_path: str):
        """Remove file from managed files list"""
        self.managed_files.discard(file_path)
        self.state.managed_files = list(self.managed_files)
        self._save_metadata()
        self.logger.info(f"Removed managed file: {file_path}")

    def to_dict(self) -> dict[str, Any]:
        """Convert agent to dictionary for serialization"""
        return self.state.to_dict()

    def _extract_filename_from_request(self, message: str) -> str:
        """Extract filename from request message"""
        import re

        # Look for common file patterns in the message
        patterns = [
            r"(?:create|write|generate)\s+(?:file\s+)?([a-zA-Z0-9_]+\.[a-zA-Z0-9]+)",
            r"(?:file|filename):\s*([a-zA-Z0-9_]+\.[a-zA-Z0-9]+)",
            r"([a-zA-Z0-9_]+\.py)",  # Python files
            r"([a-zA-Z0-9_]+\.js)",  # JavaScript files
            r"([a-zA-Z0-9_]+\.md)",  # Markdown files
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def _generate_agent_id() -> str:
        """Generate unique agent ID"""
        import uuid

        return str(uuid.uuid4())[:8]
