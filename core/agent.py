# File: ~/Projects/local-llm-mcp/core/agent.py
"""
Agent Class and State Management

Responsibilities:
- Individual agent state and behavior
- JSON schema-compliant conversation management
- Workspace and file management
- Context building for LLM prompts
- Persistence and serialization
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from schemas.agent_schemas import (
    AgentState, AgentRequest, AgentResponse, ConversationEntry,
    TaskType, create_standard_request
)

logger = logging.getLogger(__name__)

class Agent:
    """
    Individual agent with standardized JSON schema communication
    
    Each agent manages exactly one file and maintains its own context,
    conversation history, and workspace state.
    """
    
    def __init__(self, state: AgentState, workspace_dir: Path):
        self.state = state
        self.workspace_dir = workspace_dir
        self.conversation_history: List[ConversationEntry] = []
        
        # Create workspace structure
        self.context_dir = workspace_dir / "context"
        self.files_dir = workspace_dir / "files"
        
        for directory in [self.context_dir, self.files_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Set up agent-specific logging
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up agent-specific logging"""
        agent_logger = logging.getLogger(f"agent.{self.state.agent_id}")
        
        # Avoid duplicate handlers
        if not agent_logger.handlers:
            log_file = self.workspace_dir.parent.parent / "logs" / f"agent_{self.state.agent_id}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            agent_logger.addHandler(handler)
            agent_logger.setLevel(logging.INFO)
        
        return agent_logger
    
    @classmethod
    def create(
        cls,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        managed_file: str,
        workspace_dir: Path,
        initial_context: str = ""
    ) -> 'Agent':
        """Factory method to create a new agent"""
        state = AgentState(
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            managed_file=managed_file,
            context=initial_context,
            total_interactions=0,
            success_rate=1.0
        )
        
        agent = cls(state, workspace_dir)
        agent.save_context()
        
        agent.logger.info(f"Created new agent: {name} -> {managed_file}")
        return agent
    
    @classmethod
    def from_json(cls, data: Dict[str, Any], workspace_dir: Path) -> 'Agent':
        """Load agent from JSON data"""
        state = AgentState.model_validate(data)
        agent = cls(state, workspace_dir)
        agent.load_conversation_history()
        return agent
    
    def to_json(self) -> Dict[str, Any]:
        """Convert agent to JSON format"""
        return self.state.model_dump()
    
    def update_activity(self, task_type: Optional[TaskType] = None):
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
            timestamp=datetime.now(timezone.utc).isoformat()
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
        """Save agent context as JSON"""
        context_file = self.context_dir / "agent_context.json"
        context_data = {
            "agent_state": self.state.model_dump(),
            "workspace_info": {
                "workspace_path": str(self.workspace_dir),
                "managed_file_path": str(self.files_dir / self.state.managed_file),
                "managed_file_exists": (self.files_dir / self.state.managed_file).exists(),
                "file_size": self._get_managed_file_size()
            },
            "metadata": {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "conversation_entries": len(self.conversation_history),
                "context_length": len(self.state.context)
            }
        }
        
        try:
            with open(context_file, 'w') as f:
                json.dump(context_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save context: {e}")
    
    def load_conversation_history(self):
        """Load conversation history from JSON Lines"""
        history_file = self.workspace_dir / "history.jsonl"
        if not history_file.exists():
            return
        
        try:
            with open(history_file, 'r') as f:
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
        history_file = self.workspace_dir / "history.jsonl"
        
        try:
            with open(history_file, 'w') as f:
                for entry in self.conversation_history:
                    f.write(entry.model_dump_json() + '\n')
        except Exception as e:
            self.logger.error(f"Failed to save conversation history: {e}")
    
    def build_context_prompt(self, request: AgentRequest) -> str:
        """
        Build standardized context prompt for LLM generation
        
        Constructs a comprehensive prompt that includes:
        - Agent identity and role
        - Current context and state
        - Task specification
        - Expected response format (JSON schema)
        - Recent conversation history (if relevant)
        """
        context_parts = [
            f"<|im_start|>system\n{self.state.system_prompt}\n\n",
            
            # Agent identity
            f"AGENT IDENTITY:\n",
            f"- Name: {self.state.name}\n",
            f"- Role: {self.state.description}\n",
            f"- Managed File: {self.state.managed_file}\n",
            f"- Success Rate: {self.state.success_rate:.2f}\n",
            f"- Total Interactions: {self.state.total_interactions}\n\n",
            
            # Current context
            f"CURRENT CONTEXT:\n{self.state.context}\n\n" if self.state.context else "",
            
            # Task specification
            f"TASK SPECIFICATION:\n",
            f"- Task Type: {request.task_type.value}\n",
            f"- Expected Output: {request.expected_output or 'Standard JSON response'}\n\n",
            
            # JSON response format
            f"RESPONSE FORMAT (REQUIRED):\n",
            f"Always respond with valid JSON matching this exact structure:\n",
            f'{{\n',
            f'  "status": "success|error|warning|partial",\n',
            f'  "message": "Human-readable description of what was done",\n',
            f'  "file_content": {{"filename": "your_managed_file", "content": "complete_file_content", "language": "file_type"}},\n',
            f'  "changes_made": ["list", "of", "specific", "changes"],\n',
            f'  "warnings": ["any", "warnings", "or", "notes"]\n',
            f'}}\n\n',
            
            "<|im_end|>\n",
            
            # User request
            f"<|im_start|>user\n{request.instruction}",
        ]
        
        # Add additional context and parameters if provided
        if request.context:
            context_parts.append(f"\n\nAdditional Context: {request.context}")
        
        if request.parameters:
            context_parts.append(f"\n\nParameters: {json.dumps(request.parameters, indent=2)}")
        
        # Add recent conversation context (last 2 entries for continuity)
        if len(self.conversation_history) > 0:
            recent_entries = self.conversation_history[-2:]
            context_parts.append(f"\n\nRecent Conversation Context:")
            for entry in recent_entries:
                context_parts.append(f"Previous task: {entry.request.task_type.value} -> {entry.response.status.value}")
        
        context_parts.extend([
            "\n\nRemember: Respond with valid JSON only.",
            "<|im_end|>\n<|im_start|>assistant\n"
        ])
        
        return "".join(filter(None, context_parts))
    
    def get_managed_file_path(self) -> Path:
        """Get the full path to the managed file"""
        return self.files_dir / self.state.managed_file
    
    def read_managed_file(self) -> Optional[str]:
        """Read the content of the managed file"""
        file_path = self.get_managed_file_path()
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read managed file: {e}")
            return None
    
    def write_managed_file(self, content: str) -> bool:
        """Write content to the managed file"""
        file_path = self.get_managed_file_path()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Updated managed file: {self.state.managed_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write managed file: {e}")
            return False
    
    def _get_managed_file_size(self) -> Optional[int]:
        """Get the size of the managed file in bytes"""
        file_path = self.get_managed_file_path()
        
        if file_path.exists():
            return file_path.stat().st_size
        return None
    
    def get_summary(self) -> Dict[str, Any]:
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
            "context_length": len(self.state.context)
        }