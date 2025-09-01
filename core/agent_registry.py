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
        """Create a new agent with strict file ownership validation

        Args:
            name: Human-readable agent name
            description: Agent's purpose and responsibilities
            system_prompt: LLM system prompt for this agent
            managed_file: Single file this agent will manage
            initial_context: Optional initial context

        Returns:
            Tuple of (success: bool, agent: Optional[Agent], error: Optional[str])
        """
        try:
            # Validate file ownership conflict
            conflict_result = self.check_file_conflict(managed_file)
            if conflict_result[0]:  # Conflict exists
                return False, None, conflict_result[1]

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

            # Persist registry
            self.save_registry()

            logger.info(f"Created agent {agent_id} ({name}) managing {managed_file}")
            return True, agent, None

        except Exception as e:
            error_msg = f"Failed to create agent: {e!s}"
            logger.error(error_msg)
            return False, None, error_msg

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
        """Delete an agent and free up its managed file

        Args:
            agent_id: ID of agent to delete

        Returns:
            Tuple of (success: bool, error: Optional[str])
        """
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
        """Check if a file is already managed by another agent

        Args:
            filename: File to check
            exclude_agent_id: Agent ID to exclude from conflict check

        Returns:
            Tuple of (has_conflict: bool, error_message: Optional[str])
        """
        existing_agent_id = self.file_to_agent.get(filename)

        if existing_agent_id and existing_agent_id != exclude_agent_id:
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
        avg_success_rate = 0.0
        if active_agents > 0:
            avg_success_rate = (
                sum(agent.state.success_rate for agent in self.agents.values()) / active_agents
            )

        # Find most active agent
        most_active_agent = None
        if self.agents:
            most_active_agent = max(
                self.agents.values(),
                key=lambda a: a.state.total_interactions,
            )

        return {
            "total_agents": active_agents,
            "managed_files": managed_files,
            "total_interactions": total_interactions,
            "average_success_rate": round(avg_success_rate, 3),
            "most_active_agent": (
                {
                    "id": most_active_agent.state.agent_id,
                    "name": most_active_agent.state.name,
                    "interactions": most_active_agent.state.total_interactions,
                }
                if most_active_agent
                else None
            ),
            "file_ownership_integrity": len(self.file_to_agent)
            == len(set(self.file_to_agent.values())),
        }

    def validate_registry_integrity(self) -> list[str]:
        """Validate registry integrity and return list of issues found

        Returns:
            List of integrity issues (empty if all good)
        """
        issues = []

        # Check for orphaned file mappings
        for filename, agent_id in self.file_to_agent.items():
            if agent_id not in self.agents:
                issues.append(f"Orphaned file mapping: {filename} -> {agent_id}")

        # Check for agents without file mappings
        for agent_id, agent in self.agents.items():
            managed_file = agent.state.managed_file
            if managed_file not in self.file_to_agent:
                issues.append(f"Agent {agent_id} manages {managed_file} but no file mapping exists")
            elif self.file_to_agent[managed_file] != agent_id:
                issues.append(f"File mapping mismatch for {managed_file}")

        # Check for duplicate file ownership
        file_owners = {}
        for filename, agent_id in self.file_to_agent.items():
            if filename in file_owners:
                issues.append(f"Duplicate file ownership: {filename} claimed by multiple agents")
            file_owners[filename] = agent_id

        return issues

    def repair_registry_integrity(self) -> tuple[bool, list[str]]:
        """Attempt to repair registry integrity issues

        Returns:
            Tuple of (success: bool, actions_taken: List[str])
        """
        actions = []

        try:
            # Remove orphaned file mappings
            orphaned_files = []
            for filename, agent_id in self.file_to_agent.items():
                if agent_id not in self.agents:
                    orphaned_files.append(filename)

            for filename in orphaned_files:
                del self.file_to_agent[filename]
                actions.append(f"Removed orphaned file mapping: {filename}")

            # Add missing file mappings
            for agent_id, agent in self.agents.items():
                managed_file = agent.state.managed_file
                if managed_file not in self.file_to_agent:
                    self.file_to_agent[managed_file] = agent_id
                    actions.append(f"Added missing file mapping: {managed_file} -> {agent_id}")

            # Save repaired registry
            if actions:
                self.save_registry()
                logger.info(f"Registry integrity repaired: {len(actions)} actions taken")

            return True, actions

        except Exception as e:
            error_msg = f"Failed to repair registry integrity: {e!s}"
            logger.error(error_msg)
            return False, [error_msg]

    def save_registry(self) -> bool:
        """Save registry state to file"""
        try:
            print(f"DEBUG: Attempting to save to {self.registry_file}")
            print(f"DEBUG: Registry file parent exists: {self.registry_file.parent.exists()}")
            print(f"DEBUG: Number of agents to save: {len(self.agents)}")

            # Ensure state directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            print(f"DEBUG: State directory created/verified: {self.registry_file.parent}")

            registry_data = {
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

            print("DEBUG: Registry data prepared, writing to file...")

            with open(self.registry_file, "w") as f:
                json.dump(registry_data, f, indent=2)

            print(f"DEBUG: Registry saved successfully to {self.registry_file}")

            # Save individual agent states
            for agent in self.agents.values():
                print(f"DEBUG: Saving agent {agent.state.agent_id} context...")
                agent.save_context()
                agent.save_conversation_history()

            print("DEBUG: All agent states saved")
            return True

        except Exception as e:
            print(f"DEBUG: Save registry failed: {e}")
            logger.error(f"Failed to save registry: {e}")
            return False

    def load_registry(self) -> bool:
        """Load registry state from file"""
        if not self.registry_file.exists():
            logger.info("No existing registry found, starting fresh")
            return True

        try:
            with open(self.registry_file) as f:
                registry_data = json.load(f)

            # Load agents
            agents_loaded = 0
            for agent_data in registry_data.get("agents", []):
                try:
                    agent_id = agent_data["agent_id"]
                    workspace_dir = self.config.workspaces_dir / agent_id

                    # Create workspace if it doesn't exist
                    workspace_dir.mkdir(parents=True, exist_ok=True)

                    # Load agent
                    agent = Agent.from_json(agent_data, workspace_dir)
                    self.agents[agent_id] = agent
                    agents_loaded += 1

                except Exception as e:
                    logger.error(
                        f"Failed to load agent {agent_data.get('agent_id', 'unknown')}: {e}"
                    )

            # Load file mappings
            self.file_to_agent = registry_data.get("file_mappings", {})

            # Validate and repair integrity
            integrity_issues = self.validate_registry_integrity()
            if integrity_issues:
                logger.warning(f"Registry integrity issues found: {integrity_issues}")
                success, actions = self.repair_registry_integrity()
                if success:
                    logger.info(f"Registry integrity repaired: {actions}")

            logger.info(f"Loaded {agents_loaded} agents from registry")
            return True

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return False

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
        """Clean up agents that haven't been active for specified days

        Args:
            days_inactive: Number of days of inactivity before cleanup

        Returns:
            Tuple of (count_cleaned: int, cleaned_agent_names: List[str])
        """
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)
        inactive_agents = []

        for agent_id, agent in self.agents.items():
            try:
                last_activity = datetime.fromisoformat(
                    agent.state.last_activity.replace("Z", "+00:00")
                )
                if last_activity < cutoff_date:
                    inactive_agents.append((agent_id, agent.state.name))
            except Exception as e:
                logger.warning(f"Could not parse last_activity for agent {agent_id}: {e}")

        cleaned_names = []
        for agent_id, agent_name in inactive_agents:
            success, error = self.delete_agent(agent_id)
            if success:
                cleaned_names.append(agent_name)
                logger.info(f"Cleaned up inactive agent: {agent_name} ({agent_id})")
            else:
                logger.error(f"Failed to clean up agent {agent_name}: {error}")

        return len(cleaned_names), cleaned_names
