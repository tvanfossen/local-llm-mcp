# File: ~/Projects/local-llm-mcp/core/agent_registry.py
"""Agent Registry and File Ownership Management

Responsibilities:
- Agent lifecycle management (create, load, save, delete)
- File ownership tracking and conflict prevention
- Agent discovery and retrieval
- Persistence of agent registry state
- Workspace management
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from core.agent import Agent
from core.config import SystemConfig

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Centralized registry for agent management and file ownership tracking

    Enforces the core rule: One agent per file, one file per agent
    """

    def __init__(self, system_config: SystemConfig):
        self.config = system_config
        self.agents: dict[str, Agent] = {}
        self.file_to_agent: dict[str, str] = {}  # filename -> agent_id

        # Registry state file
        self.registry_file = system_config.state_dir / "agents.json"

        # Load existing agents
        self.load_registry()

    def create_agent(
        self,
        name: str,
        description: str,
        system_prompt: str,
        managed_file: str,
        initial_context: str = "",
    ) -> tuple[bool, Agent | None, str | None]:
        """Create a new agent with strict file ownership validation"""
        try:
            # Validate file ownership conflict
            conflict_result = self.check_file_conflict(managed_file)
            if conflict_result[0]:  # Conflict exists
                return False, None, conflict_result[1]

            # Create agent
            agent = self._create_and_register_agent(
                name, description, system_prompt, managed_file, initial_context
            )

            # Persist registry
            self.save_registry()

            logger.info(f"Created agent {agent.state.agent_id} ({name}) managing {managed_file}")
            return True, agent, None

        except Exception as e:
            error_msg = f"Failed to create agent: {e!s}"
            logger.error(error_msg)
            return False, None, error_msg

    def _create_and_register_agent(
        self,
        name: str,
        description: str,
        system_prompt: str,
        managed_file: str,
        initial_context: str,
    ) -> Agent:
        """Create and register a new agent"""
        # Generate unique agent ID
        agent_id = self._generate_agent_id()

        # Create workspace
        workspace_dir = self.config.workspaces_dir / agent_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create agent
        agent = Agent.create(
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            managed_file=managed_file,
            workspace_dir=workspace_dir,
            initial_context=initial_context,
        )

        # Register agent and file ownership
        self.agents[agent_id] = agent
        self.file_to_agent[managed_file] = agent_id

        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def get_agent_by_file(self, filename: str) -> Agent | None:
        """Get agent that manages a specific file"""
        agent_id = self.file_to_agent.get(filename)
        if agent_id:
            return self.agents.get(agent_id)
        return None

    def list_agents(self) -> list[Agent]:
        """Get list of all active agents"""
        return list(self.agents.values())

    def delete_agent(self, agent_id: str) -> tuple[bool, str | None]:
        """Delete an agent and free up its managed file"""
        if agent_id not in self.agents:
            return False, f"Agent {agent_id} not found"

        try:
            agent = self.agents[agent_id]
            managed_file = agent.state.managed_file

            # Remove from registry
            del self.agents[agent_id]
            if managed_file in self.file_to_agent:
                del self.file_to_agent[managed_file]

            # Save final state before deletion
            agent.save_context()
            agent.save_conversation_history()

            # Persist registry
            self.save_registry()

            logger.info(f"Deleted agent {agent_id} ({agent.state.name}), freed file {managed_file}")
            return True, None

        except Exception as e:
            error_msg = f"Failed to delete agent {agent_id}: {e!s}"
            logger.error(error_msg)
            return False, error_msg

    def check_file_conflict(
        self, filename: str, exclude_agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        """Check if a file is already managed by another agent"""
        existing_agent_id = self.file_to_agent.get(filename)

        if existing_agent_id and existing_agent_id != exclude_agent_id:
            return self._handle_existing_agent_conflict(filename, existing_agent_id)

        return False, None

    def _handle_existing_agent_conflict(
        self, filename: str, existing_agent_id: str
    ) -> tuple[bool, str | None]:
        """Handle conflict with existing agent"""
        if existing_agent_id in self.agents:
            existing_agent = self.agents[existing_agent_id]
            error_msg = (
                f"File '{filename}' is already managed by agent "
                f"'{existing_agent.state.name}' (ID: {existing_agent_id}). "
                f"Rule: One agent per file, one file per agent."
            )
            return True, error_msg

        # Orphaned file mapping, clean it up
        del self.file_to_agent[filename]
        self.save_registry()
        logger.warning(f"Cleaned up orphaned file mapping: {filename}")
        return False, None

    def get_file_ownership_map(self) -> dict[str, str]:
        """Get complete file ownership mapping"""
        return self.file_to_agent.copy()

    def get_registry_stats(self) -> dict[str, any]:
        """Get registry statistics"""
        active_agents = len(self.agents)
        managed_files = len(self.file_to_agent)

        # Calculate agent activity stats
        total_interactions = sum(agent.state.total_interactions for agent in self.agents.values())
        avg_success_rate = self._calculate_average_success_rate(active_agents)

        # Find most active agent
        most_active_agent = self._find_most_active_agent()

        return {
            "total_agents": active_agents,
            "managed_files": managed_files,
            "total_interactions": total_interactions,
            "average_success_rate": round(avg_success_rate, 3),
            "most_active_agent": most_active_agent,
            "file_ownership_integrity": len(self.file_to_agent)
            == len(set(self.file_to_agent.values())),
        }

    def _calculate_average_success_rate(self, active_agents: int) -> float:
        """Calculate average success rate across all agents"""
        if active_agents == 0:
            return 0.0
        return sum(agent.state.success_rate for agent in self.agents.values()) / active_agents

    def _find_most_active_agent(self) -> dict | None:
        """Find the most active agent"""
        if not self.agents:
            return None

        most_active_agent = max(
            self.agents.values(),
            key=lambda a: a.state.total_interactions,
        )

        return {
            "id": most_active_agent.state.agent_id,
            "name": most_active_agent.state.name,
            "interactions": most_active_agent.state.total_interactions,
        }

    def validate_registry_integrity(self) -> list[str]:
        """Validate registry integrity and return list of issues found"""
        issues = []

        # Check different types of integrity issues
        self._check_orphaned_file_mappings(issues)
        self._check_missing_file_mappings(issues)
        self._check_duplicate_file_ownership(issues)

        return issues

    def _check_orphaned_file_mappings(self, issues: list[str]):
        """Check for orphaned file mappings"""
        for filename, agent_id in self.file_to_agent.items():
            if agent_id not in self.agents:
                issues.append(f"Orphaned file mapping: {filename} -> {agent_id}")

    def _check_missing_file_mappings(self, issues: list[str]):
        """Check for agents without file mappings"""
        for agent_id, agent in self.agents.items():
            managed_file = agent.state.managed_file
            if managed_file not in self.file_to_agent:
                issues.append(f"Agent {agent_id} manages {managed_file} but no file mapping exists")
            elif self.file_to_agent[managed_file] != agent_id:
                issues.append(f"File mapping mismatch for {managed_file}")

    def _check_duplicate_file_ownership(self, issues: list[str]):
        """Check for duplicate file ownership"""
        file_owners = {}
        for filename, agent_id in self.file_to_agent.items():
            if filename in file_owners:
                issues.append(f"Duplicate file ownership: {filename} claimed by multiple agents")
            file_owners[filename] = agent_id

    def repair_registry_integrity(self) -> tuple[bool, list[str]]:
        """Attempt to repair registry integrity issues"""
        actions = []

        try:
            # Remove orphaned file mappings
            self._repair_orphaned_mappings(actions)

            # Add missing file mappings
            self._repair_missing_mappings(actions)

            # Save repaired registry
            if actions:
                self.save_registry()
                logger.info(f"Registry integrity repaired: {len(actions)} actions taken")

            return True, actions

        except Exception as e:
            error_msg = f"Failed to repair registry integrity: {e!s}"
            logger.error(error_msg)
            return False, [error_msg]

    def _repair_orphaned_mappings(self, actions: list[str]):
        """Remove orphaned file mappings"""
        orphaned_files = []
        for filename, agent_id in self.file_to_agent.items():
            if agent_id not in self.agents:
                orphaned_files.append(filename)

        for filename in orphaned_files:
            del self.file_to_agent[filename]
            actions.append(f"Removed orphaned file mapping: {filename}")

    def _repair_missing_mappings(self, actions: list[str]):
        """Add missing file mappings"""
        for agent_id, agent in self.agents.items():
            managed_file = agent.state.managed_file
            if managed_file not in self.file_to_agent:
                self.file_to_agent[managed_file] = agent_id
                actions.append(f"Added missing file mapping: {managed_file} -> {agent_id}")

    def save_registry(self) -> bool:
        """Save registry state to file"""
        try:
            print(f"DEBUG: Attempting to save to {self.registry_file}")
            print(f"DEBUG: Registry file parent exists: {self.registry_file.parent.exists()}")
            print(f"DEBUG: Number of agents to save: {len(self.agents)}")

            # Ensure state directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            print(f"DEBUG: State directory created/verified: {self.registry_file.parent}")

            registry_data = self._build_registry_data()

            print("DEBUG: Registry data prepared, writing to file...")

            with open(self.registry_file, "w") as f:
                json.dump(registry_data, f, indent=2)

            print(f"DEBUG: Registry saved successfully to {self.registry_file}")

            # Save individual agent states
            self._save_all_agent_states()

            print("DEBUG: All agent states saved")
            return True

        except Exception as e:
            print(f"DEBUG: Save registry failed: {e}")
            logger.error(f"Failed to save registry: {e}")
            return False

    def _build_registry_data(self) -> dict:
        """Build registry data structure for saving"""
        return {
            "schema_version": "1.0",
            "agents": [agent.to_json() for agent in self.agents.values()],
            "file_mappings": self.file_to_agent.copy(),
            "metadata": {
                "total_agents": len(self.agents),
                "total_files": len(self.file_to_agent),
                "last_saved": datetime.now(timezone.utc).isoformat(),
                "integrity_validated": len(self.validate_registry_integrity()) == 0,
            },
        }

    def _save_all_agent_states(self):
        """Save all agent states"""
        for agent in self.agents.values():
            print(f"DEBUG: Saving agent {agent.state.agent_id} context...")
            agent.save_context()
            agent.save_conversation_history()

    def load_registry(self) -> bool:
        """Load registry state from file"""
        if not self.registry_file.exists():
            logger.info("No existing registry found, starting fresh")
            return True

        try:
            with open(self.registry_file) as f:
                registry_data = json.load(f)

            # Load agents
            agents_loaded = self._load_agents_from_data(registry_data)

            # Load file mappings
            self.file_to_agent = registry_data.get("file_mappings", {})

            # Validate and repair integrity
            self._validate_and_repair_integrity()

            logger.info(f"Loaded {agents_loaded} agents from registry")
            return True

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return False

    def _load_agents_from_data(self, registry_data: dict) -> int:
        """Load agents from registry data"""
        agents_loaded = 0
        for agent_data in registry_data.get("agents", []):
            if self._load_single_agent(agent_data):
                agents_loaded += 1
        return agents_loaded

    def _load_single_agent(self, agent_data: dict) -> bool:
        """Load a single agent from data"""
        try:
            agent_id = agent_data["agent_id"]
            workspace_dir = self.config.workspaces_dir / agent_id

            # Create workspace if it doesn't exist
            workspace_dir.mkdir(parents=True, exist_ok=True)

            # Load agent
            agent = Agent.from_json(agent_data, workspace_dir)
            self.agents[agent_id] = agent
            return True

        except Exception as e:
            logger.error(f"Failed to load agent {agent_data.get('agent_id', 'unknown')}: {e}")
            return False

    def _validate_and_repair_integrity(self):
        """Validate and repair integrity after loading"""
        integrity_issues = self.validate_registry_integrity()
        if integrity_issues:
            logger.warning(f"Registry integrity issues found: {integrity_issues}")
            success, actions = self.repair_registry_integrity()
            if success:
                logger.info(f"Registry integrity repaired: {actions}")

    def _generate_agent_id(self) -> str:
        """Generate a unique agent ID"""
        while True:
            agent_id = str(uuid.uuid4())[:8]
            if agent_id not in self.agents:
                return agent_id

    def get_agents_summary(self) -> list[dict[str, any]]:
        """Get summary information for all agents"""
        summaries = []
        for agent in self.agents.values():
            summary = agent.get_summary()
            summaries.append(summary)

        # Sort by last activity (most recent first)
        summaries.sort(key=lambda x: x["last_activity"], reverse=True)
        return summaries

    def cleanup_inactive_agents(self, days_inactive: int = 30) -> tuple[int, list[str]]:
        """Clean up agents that haven't been active for specified days"""
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)
        inactive_agents = self._find_inactive_agents(cutoff_date)

        cleaned_names = self._delete_inactive_agents(inactive_agents)

        return len(cleaned_names), cleaned_names

    def _find_inactive_agents(self, cutoff_date: datetime) -> list[tuple[str, str]]:
        """Find agents that are inactive before cutoff date"""
        inactive_agents = []

        for agent_id, agent in self.agents.items():
            if self._is_agent_inactive(agent, cutoff_date):
                inactive_agents.append((agent_id, agent.state.name))

        return inactive_agents

    def _is_agent_inactive(self, agent: Agent, cutoff_date: datetime) -> bool:
        """Check if agent is inactive before cutoff date"""
        try:
            last_activity = datetime.fromisoformat(agent.state.last_activity.replace("Z", "+00:00"))
            return last_activity < cutoff_date
        except Exception as e:
            logger.warning(f"Could not parse last_activity for agent {agent.state.agent_id}: {e}")
            return False

    def _delete_inactive_agents(self, inactive_agents: list[tuple[str, str]]) -> list[str]:
        """Delete inactive agents and return list of cleaned names"""
        cleaned_names = []
        for agent_id, agent_name in inactive_agents:
            success, error = self.delete_agent(agent_id)
            if success:
                cleaned_names.append(agent_name)
                logger.info(f"Cleaned up inactive agent: {agent_name} ({agent_id})")
            else:
                logger.error(f"Failed to clean up agent {agent_name}: {error}")
        return cleaned_names
