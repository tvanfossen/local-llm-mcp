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
        """Handle code generation requests using tool executor for file operations"""
        if not self.tool_executor:
            return AgentResponse(
                success=False,
                content="Agent not properly initialized with tool executor",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            self.logger.info(f"Processing code generation request: {request.message}")

            # Use the first managed file as the target file, or determine from request
            if self.state.managed_files and len(self.state.managed_files) > 0:
                filename = self.state.managed_files[0]
            else:
                # Extract filename from request or use default
                filename = self._extract_filename_from_request(request.message) or "generated_code.py"

            self.logger.info(f"Generating code for file: {filename}")

            # Build context for LLM code generation
            context = self.get_context_for_llm()

            # Get current file structure for context
            file_structure = await self.json_file_manager.get_file_structure(filename)
            structure_context = ""
            if file_structure:
                structure_context = f"""
Current file structure:
- Functions: {[f['name'] for f in file_structure['functions']]}
- Classes: {[c['name'] for c in file_structure['classes']]}
- Dataclasses: {[dc['name'] for dc in file_structure['dataclasses']]}
"""

            # Create tool-calling prompt for MCP architecture
            code_gen_prompt = f"""Context: {context}
{structure_context}
Task: Structured Code Generation for {filename}
Request: {request.message}

You are an agent that must use MCP tools to complete tasks. You have access to these tools:
- workspace: Create, write, read files and directories
- validation: Run tests and validation on code
- git_operations: Commit and manage git operations

CRITICAL: You must use explicit tool calls to complete this task. DO NOT generate code directly.

Your workflow should be:
1. Use workspace tool to write the Python file with the requested functionality
2. Use validation tool to test the code works correctly
3. Use git_operations tool to commit the working code

For the file content, generate clean Python code with:
- Proper function/class definitions
- Meaningful docstrings
- Type hints where appropriate
- Functional implementation (not just stubs)

Example tool call format:
```json
{{
    "tool_name": "workspace",
    "action": "write",
    "path": "{filename}",
    "content": "def example():\\n    \\\"\\\"\\\"Example function\\\"\\\"\\\"\\n    return True"
}}
```

Begin by making your first tool call to create the file:"""

            # Generate code using LLM if available
            self.logger.info(f"Starting code generation for {filename}")
            self.logger.info(f"LLM available: {self.llm_manager is not None and self.llm_manager.is_ready()}")
            self.logger.info(f"Code generation prompt: {code_gen_prompt}")

            if self.llm_manager and self.llm_manager.is_ready():
                self.logger.info("Using LLM with tool calling for code generation")

                # Use new tool calling method
                response = await self.llm_manager.generate_with_tools(
                    code_gen_prompt, max_tokens=8192, temperature=0.3, tools_enabled=True
                )

                self.logger.info(f"LLM response success: {response['success']}")
                self.logger.info(f"LLM response type: {response.get('type', 'unknown')}")

                if response["success"]:
                    if response["type"] == "tool_calls":
                        # Tool calls were executed - check results
                        results = response.get("results", [])
                        tool_calls = response.get("tool_calls", [])

                        self.logger.info(f"Tool calls executed: {len(tool_calls)}")
                        self.logger.info(f"Tool results: {len(results)}")

                        # Find workspace tool results
                        workspace_results = [r for r in results if r.get("tool_name") == "workspace"]

                        if workspace_results and any(r.get("success") for r in workspace_results):
                            return AgentResponse(
                                success=True,
                                content=f"✅ Code generation completed via MCP tools\n\n"
                                       f"📁 **File**: {filename}\n"
                                       f"🔧 **Tool Results**: {len(results)} tools executed\n"
                                       f"📝 **Status**: File updated successfully\n\n"
                                       f"The code was generated and written using structured MCP tool calls.",
                                agent_id=self.state.agent_id,
                                task_type=request.task_type,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                files_modified=[filename],
                            )
                        else:
                            # Tool calls failed, extract error information
                            failed_results = [r for r in results if not r.get("success")]
                            error_msgs = [r.get("error", "Unknown error") for r in failed_results]

                            return AgentResponse(
                                success=False,
                                content=f"❌ Tool execution failed: {'; '.join(error_msgs)}",
                                agent_id=self.state.agent_id,
                                task_type=request.task_type,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            )

                    elif response["type"] == "text":
                        # Model generated text but no tool calls - this should not happen with proper prompting
                        raw_response = response["content"].strip()
                        self.logger.warning(f"Model generated text response instead of tool calls: {len(raw_response)} characters")
                        self.logger.warning(f"Response content preview: {raw_response[:200]}...")

                        return AgentResponse(
                            success=False,
                            content=f"❌ Model failed to make required tool calls\n\n"
                                   f"Expected: workspace, validation, and git_operations tool calls\n"
                                   f"Received: Plain text response\n\n"
                                   f"This indicates the model is not following MCP tool calling instructions. "
                                   f"The agent requires explicit tool calls to maintain structured workflows.",
                            agent_id=self.state.agent_id,
                            task_type=request.task_type,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                else:
                    self.logger.error(f"LLM generation failed: {response.get('error', 'Unknown error')}")
                    return await self._generate_structured_fallback(filename, request.message)
            else:
                self.logger.info("LLM not available, using structured fallback")
                # Use structured fallback
                return await self._generate_structured_fallback(filename, request.message)

        except Exception as e:
            self.logger.error(f"Code generation handling failed: {e}")
            return AgentResponse(
                success=False,
                content=f"Error handling code generation: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=request.task_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    async def _generate_structured_fallback(self, filename: str, request: str) -> AgentResponse:
        """Generate structured fallback when LLM is not available"""
        try:
            # Create a simple function fallback
            fallback_element = {
                "name": "generated_function",
                "docstring": f"Generated function based on request: {request}",
                "parameters": [],
                "return_type": "str",
                "body": 'return "Function generated as fallback"',
                "decorators": []
            }

            success = await self.json_file_manager.update_element(filename, "function", fallback_element)

            if success:
                return AgentResponse(
                    success=True,
                    content=f"✅ Generated fallback function in {filename}",
                    agent_id=self.state.agent_id,
                    task_type=TaskType.CODE_GENERATION,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    files_modified=[filename],
                )
            else:
                return AgentResponse(
                    success=False,
                    content=f"❌ Failed to generate fallback in {filename}",
                    agent_id=self.state.agent_id,
                    task_type=TaskType.CODE_GENERATION,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        except Exception as e:
            self.logger.error(f"Fallback generation failed: {e}")
            return AgentResponse(
                success=False,
                content=f"Error generating fallback: {str(e)}",
                agent_id=self.state.agent_id,
                task_type=TaskType.CODE_GENERATION,
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
        # Implementation for other file creation tasks
        return AgentResponse(
            success=True,
            content="Generic file creation not yet implemented",
            agent_id=self.state.agent_id,
            task_type=request.task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _handle_file_read(self, request: AgentRequest) -> AgentResponse:
        """Handle file reading requests"""
        # Implementation for file reading
        return AgentResponse(
            success=True,
            content="File reading not yet implemented",
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
        return AgentResponse(
            success=True,
            content="Generic file operation analysis not yet implemented",
            agent_id=self.state.agent_id,
            task_type=request.task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
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
