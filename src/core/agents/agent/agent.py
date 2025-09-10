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

    def __init__(self, state: AgentState, system_config: SystemConfig):
        self.state = state
        self.system_config = system_config
        self.conversation_history: list[ConversationEntry] = []
        self.managed_files: set[str] = set(state.managed_files)

        # Setup agent directory structure
        self.agent_dir = system_config.agents_dir / state.agent_id
        self.metadata_file = self.agent_dir / "metadata.json"
        self.conversation_file = self.agent_dir / "conversation.json"

        # Setup logging
        self.logger = self._setup_logging()

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
    def create(cls, params: AgentCreateParams) -> "Agent":
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

        agent = cls(state, params.system_config)
        agent._save_metadata()
        return agent

    @classmethod
    def from_json(cls, data: dict[str, Any], system_config: SystemConfig) -> "Agent":
        """Load agent from JSON data"""
        state = AgentState(**data)
        return cls(state, system_config)

    @classmethod
    def load_from_disk(cls, agent_id: str, system_config: SystemConfig) -> "Agent":
        """Load agent from disk by ID"""
        agent_dir = system_config.agents_dir / agent_id
        metadata_file = agent_dir / "metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Agent metadata not found: {metadata_file}")

        with open(metadata_file) as f:
            data = json.load(f)

        return cls.from_json(data, system_config)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process agent request with conversation tracking"""
        self.logger.info(f"Processing {request.task_type.value} request: {request.message[:100]}...")

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
        if request.task_type == TaskType.FILE_EDIT:
            return await self._handle_file_edit(request)
        elif request.task_type == TaskType.CODE_GENERATION:
            return await self._handle_code_generation(request)
        elif request.task_type == TaskType.CONVERSATION:
            return await self._handle_conversation(request)
        else:
            raise ValueError(f"Unsupported task type: {request.task_type}")

    async def _handle_file_edit(self, request: AgentRequest) -> AgentResponse:
        """Handle file editing requests"""
        # Implementation would integrate with LLM for file editing
        # This is a placeholder for the actual implementation
        return AgentResponse(
            success=True,
            content=f"File edit task received: {request.message}",
            agent_id=self.state.agent_id,
            task_type=request.task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
        """Handle code generation requests"""
        # Implementation would integrate with LLM for code generation
        return AgentResponse(
            success=True,
            content=f"Code generation task received: {request.message}",
            agent_id=self.state.agent_id,
            task_type=request.task_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _handle_conversation(self, request: AgentRequest) -> AgentResponse:
        """Handle general conversation requests"""
        # Implementation would integrate with LLM for conversation
        return AgentResponse(
            success=True,
            content=f"Conversation response for: {request.message}",
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

    @staticmethod
    def _generate_agent_id() -> str:
        """Generate unique agent ID"""
        import uuid

        return str(uuid.uuid4())[:8]
