# File: ~/Projects/local-llm-mcp/core/agent.py
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
from pathlib import Path
from typing import Any

from core.config import SystemConfig
from schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    AgentState,
    ConversationEntry,
    TaskType,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentCreateParams:
    """Parameters for creating an agent"""

    agent_id: str
    name: str
    description: str
    system_prompt: str
    managed_file: str
    system_config: SystemConfig
    initial_context: str = ""


class Agent:
    """Individual agent with direct repository file access

    Each agent manages exactly one file directly in the workspace root,
    while storing metadata in .mcp-agents/{agent_id}/ directory.
    """

    def __init__(self, state: AgentState, system_config: SystemConfig):
        self.state = state
        self.system_config = system_config
        self.conversation_history: list[ConversationEntry] = []

        # Get agent metadata directory from system config
        self.metadata_dir = self.system_config.get_agent_workspace_dir(self.state.agent_id)

        # Create metadata subdirectories
        self.context_dir = self.metadata_dir / "context"
        self.history_dir = self.metadata_dir / "history"

        # Ensure metadata directories exist
        for directory in [self.context_dir, self.history_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Set up agent-specific logging
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Set up agent-specific logging"""
        agent_logger = logging.getLogger(f"agent.{self.state.agent_id}")

        # Avoid duplicate handlers
        if not agent_logger.handlers:
            log_file = self.system_config.logs_dir / f"agent_{self.state.agent_id}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                )
            )
            agent_logger.addHandler(handler)
            agent_logger.setLevel(logging.INFO)

        return agent_logger

    @classmethod
    def create(cls, params: AgentCreateParams) -> "Agent":
        """Factory method to create a new agent"""
        state = AgentState(
            agent_id=params.agent_id,
            name=params.name,
            description=params.description,
            system_prompt=params.system_prompt,
            managed_file=params.managed_file,
            context=params.initial_context,
            total_interactions=0,
            success_rate=1.0,
        )

        agent = cls(state, params.system_config)
        agent.save_context()

        agent.logger.info(f"Created new agent: {params.name} -> {params.managed_file}")
        return agent

    @classmethod
    def from_json(cls, data: dict[str, Any], system_config: SystemConfig) -> "Agent":
        """Load agent from JSON data"""
        state = AgentState.model_validate(data)
        agent = cls(state, system_config)
        agent.load_conversation_history()
        return agent

    def to_json(self) -> dict[str, Any]:
        """Convert agent to JSON format"""
        return self.state.model_dump()

    def update_activity(self, task_type: TaskType | None = None):
        """Update agent activity with standardized format"""
        self.state.last_activity = datetime.now(timezone.utc).isoformat()
        self.state.total_interactions += 1

        if task_type:
            self.state.last_task = task_type

        self.logger.info(f"Activity updated - Total interactions: {self.state.total_interactions}")

    def update_success_rate(self, success: bool):
        """Update agent's success rate based on task outcome"""
        if self.state.total_interactions == 0:
            self.state.success_rate = 1.0 if success else 0.0
        else:
            # Simple moving average
            current_rate = self.state.success_rate
            weight = 0.1  # How much the new result affects the rate
            self.state.success_rate = current_rate * (1 - weight) + (1.0 if success else 0.0) * weight

    def add_conversation(self, request: AgentRequest, response: AgentResponse):
        """Add conversation entry in standardized format"""
        entry = ConversationEntry(
            request=request,
            response=response,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self.conversation_history.append(entry)

        # Trim history if too long (keep last 100 entries)
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]

        self.logger.info(f"Added conversation entry - Task: {request.task_type.value}")

    def update_context(self, new_context: str):
        """Update agent's current context"""
        self.state.context = new_context
        self.save_context()
        self.logger.info("Context updated")

    def save_context(self):
        """Save agent context as JSON to metadata directory"""
        context_file = self.context_dir / "agent_context.json"
        context_data = {
            "agent_state": self.state.model_dump(),
            "workspace_info": {
                "metadata_dir": str(self.metadata_dir),
                "managed_file_path": str(self.get_managed_file_path()),
                "managed_file_exists": self.get_managed_file_path().exists(),
                "file_size": self._get_managed_file_size(),
            },
            "environment_info": {
                "container_environment": self.system_config.is_container_environment(),
                "workspace_root": str(self.system_config.get_workspace_root()),
            },
            "metadata": {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "conversation_entries": len(self.conversation_history),
                "context_length": len(self.state.context),
            },
        }

        try:
            with open(context_file, "w") as f:
                json.dump(context_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save context: {e}")

    def load_conversation_history(self):
        """Load conversation history from JSON Lines"""
        history_file = self.history_dir / "conversation.jsonl"
        if not history_file.exists():
            return

        try:
            with open(history_file) as f:
                for line in f:
                    if line.strip():
                        entry_data = json.loads(line.strip())
                        entry = ConversationEntry.model_validate(entry_data)
                        self.conversation_history.append(entry)

            self.logger.info(f"Loaded {len(self.conversation_history)} conversation entries")

        except Exception as e:
            self.logger.error(f"Failed to load conversation history: {e}")

    def save_conversation_history(self):
        """Save conversation history as JSON Lines"""
        history_file = self.history_dir / "conversation.jsonl"

        try:
            with open(history_file, "w") as f:
                for entry in self.conversation_history:
                    f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            self.logger.error(f"Failed to save conversation history: {e}")

    def build_context_prompt(self, request: AgentRequest) -> str:
        """Build context prompt with direct file access approach"""
        # Read current file content if it exists
        current_content = self.read_managed_file()
        current_file_info = ""

        if current_content:
            file_size = len(current_content)
            line_count = len(current_content.split("\n"))
            current_file_info = f"""
CURRENT FILE ({self.state.managed_file}):
```
{current_content}
```
File has {line_count} lines, {file_size} characters.
"""
        else:
            current_file_info = f"""
CURRENT FILE STATUS:
- File: {self.state.managed_file} (does not exist yet)
"""

        context_parts = [
            f"<|im_start|>system\n{self.state.system_prompt}\n\n",
            # Agent identity
            "AGENT IDENTITY:\n",
            f"- Name: {self.state.name}\n",
            f"- Role: {self.state.description}\n",
            f"- Managed File: {self.state.managed_file}\n\n",
            # Current context and file
            f"CURRENT CONTEXT:\n{self.state.context}\n\n" if self.state.context else "",
            current_file_info,
            # SIMPLE JSON FORMAT - no nested objects, no quotes in content
            "🚨 RESPONSE FORMAT (REQUIRED) 🚨\n",
            "Respond with valid JSON. Use SIMPLE format - no nested objects:\n\n",
            "{\n",
            '  "status": "success",\n',
            '  "message": "Brief description of what you did",\n',
            '  "full_file_content": "complete updated file content goes here as single string",\n',
            '  "changes_summary": "Added multiply function with docstring",\n',
            '  "warnings": "any warnings or empty string"\n',
            "}\n\n",
            "CRITICAL RULES:\n",
            "1. Always provide COMPLETE file content in 'full_file_content'\n",
            "2. Escape newlines as \\n in the JSON string\n",
            '3. Escape quotes as " in the JSON string\n',
            "4. No nested objects - keep it flat and simple\n",
            "5. If file doesn't exist, create complete new content\n\n",
            "<|im_end|>\n",
            # User request
            f"<|im_start|>user\n{request.instruction}",
        ]

        # Add additional context if provided
        if request.context:
            context_parts.append(f"\n\nAdditional Context: {request.context}")

        context_parts.extend(
            [
                "\n\n🚨 REMINDER: Provide COMPLETE file content. Use simple JSON format.",
                "<|im_end|>\n<|im_start|>assistant\n",
            ]
        )

        return "".join(filter(None, context_parts))

    def _get_file_language(self) -> str:
        """Get syntax highlighting language for current file"""
        ext = self.state.managed_file.split(".")[-1].lower()
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "html": "html",
            "css": "css",
            "sql": "sql",
            "md": "markdown",
        }
        return lang_map.get(ext, "text")

    def get_managed_file_path(self) -> Path:
        """Get the full path to the managed file in workspace root"""
        workspace_root = self.system_config.get_workspace_root()
        return workspace_root / self.state.managed_file

    def read_managed_file(self) -> str | None:
        """Read the content of the managed file from workspace root"""
        file_path = self.get_managed_file_path()

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read managed file: {e}")
            return None

    def write_managed_file(self, content: str) -> bool:
        """Write content to the managed file in workspace root"""
        file_path = self.get_managed_file_path()

        try:
            # Ensure parent directories exist (in case of nested file paths)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Updated managed file: {self.state.managed_file} at {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to write managed file: {e}")
            return False

    def _get_managed_file_size(self) -> int | None:
        """Get the size of the managed file in bytes"""
        file_path = self.get_managed_file_path()

        if file_path.exists():
            return file_path.stat().st_size
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the agent's current state"""
        return {
            "agent_id": self.state.agent_id,
            "name": self.state.name,
            "description": self.state.description,
            "managed_file": self.state.managed_file,
            "file_exists": self.get_managed_file_path().exists(),
            "file_size": self._get_managed_file_size(),
            "last_activity": self.state.last_activity,
            "total_interactions": self.state.total_interactions,
            "success_rate": self.state.success_rate,
            "conversation_entries": len(self.conversation_history),
            "context_length": len(self.state.context),
            "environment": {
                "container_mode": self.system_config.is_container_environment(),
                "workspace_root": str(self.system_config.get_workspace_root()),
                "metadata_dir": str(self.metadata_dir),
            },
        }
