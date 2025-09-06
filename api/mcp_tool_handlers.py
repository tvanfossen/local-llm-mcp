import logging
from typing import Any, Optional

from api.mcp_git_handlers import MCPGitHandlers
from api.mcp_validation_handlers import MCPValidationHandlers
from core.agent_registry import AgentRegistry
from core.llm_manager import LLMManager
from schemas.agent_schemas import ResponseStatus, TaskType, create_standard_request

logger = logging.getLogger(__name__)


class MCPToolHandlers:
    """Contains all MCP tool handler implementations"""

    def __init__(self, agent_registry: AgentRegistry, llm_manager: LLMManager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.git_handlers = MCPGitHandlers()
        self.validation_handlers = MCPValidationHandlers(agent_registry)

    @staticmethod
    def _create_success(text: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": False}

    @staticmethod
    def _create_error(title: str, message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}

    @staticmethod
    def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}

    def _validate_agent_id(self, agent_id: Optional[str]) -> tuple[bool, dict[str, Any]]:
        if not agent_id:
            return False, self._create_error("Missing Parameter", "agent_id is required")
        return True, None

    def _get_agent(self, agent_id: str) -> tuple[bool, dict[str, Any], Optional[Any]]:
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            return False, self._create_error("Agent Not Found", f"Agent {agent_id} not found"), None
        return True, None, agent

    def _validate_and_get_agent(self, args: dict[str, Any]) -> tuple[bool, dict[str, Any], Optional[Any]]:
        valid, error = self._validate_agent_id(args.get("agent_id"))
        if not valid:
            return False, error, None

        valid, error, agent = self._get_agent(args["agent_id"])
        if not valid:
            return False, error, None

        return True, None, agent

    async def create_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            success, agent, error = self.agent_registry.create_agent(
                name=args["name"],
                description=args["description"],
                system_prompt=args["system_prompt"],
                managed_file=args["managed_file"],
                initial_context=args.get("initial_context", ""),
            )
            if success:
                return self._create_success(
                    f"✅ **Agent Created Successfully**\n\n"
                    f"**ID:** {agent.state.agent_id}\n"
                    f"**Name:** {agent.state.name}\n"
                    f"**Managed File:** {agent.state.managed_file}\n"
                    f"**Authentication:** ✅ Session verified"
                )
            return self._create_error("Agent Creation Failed", error)
        except Exception as e:
            return self._handle_exception(e, "Creation")

    async def list_agents(self, args: dict[str, Any] = None) -> dict[str, Any]:
        try:
            agents = self.agent_registry.list_agents()
            if not agents:
                return self._create_success(
                    "📝 **No agents created yet.**\n\n"
                    "**Rule:** One agent per file, one file per agent.\n"
                    "Use `create_agent` to create your first agent."
                )
            response_text = "🤖 **Active Agents:**\n\n"
            for agent in agents:
                response_text += (
                    f"• **{agent.state.agent_id}** - {agent.state.name}\n"
                    f"  📄 File: `{agent.state.managed_file}`\n"
                    f"  📝 {agent.state.description}\n"
                    f"  🔢 Interactions: {agent.state.total_interactions}\n"
                    f"  📊 Success Rate: {agent.state.success_rate:.2f}\n\n"
                )
            return self._create_success(response_text)
        except Exception as e:
            return self._handle_exception(e, "List")

    def _build_agent_info(self, agent) -> str:
        summary = agent.get_summary()
        return (
            f"🤖 **Agent Information: {agent.state.name}**\n\n"
            f"**ID:** {agent.state.agent_id}\n"
            f"**Description:** {agent.state.description}\n"
            f"**Managed File:** `{agent.state.managed_file}`\n"
            f"**File Exists:** {'✅' if summary['file_exists'] else '❌'}\n"
            f"**Total Interactions:** {summary['total_interactions']}\n"
            f"**Success Rate:** {summary['success_rate']:.2f}\n"
            f"**Created:** {agent.state.created_at}\n"
            f"**Authentication:** ✅ Required for all operations"
        )

    async def get_agent_info(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            valid, error, agent = self._validate_and_get_agent(args)
            if not valid:
                return error
            return self._create_success(self._build_agent_info(agent))
        except Exception as e:
            return self._handle_exception(e, "Info")

    def _build_delete_response(self, agent_name: str, agent_id: str, managed_file: str) -> str:
        return (
            f"✅ **Agent Deleted Successfully**\n\n"
            f"**Deleted:** {agent_name} (ID: {agent_id})\n"
            f"**File Released:** `{managed_file}`\n\n"
            f"The file `{managed_file}` is now available for a new agent."
        )

    def _perform_delete(self, agent_id: str, agent_name: str, managed_file: str) -> dict[str, Any]:
        success, error = self.agent_registry.delete_agent(agent_id)
        if success:
            return self._create_success(self._build_delete_response(agent_name, agent_id, managed_file))
        return self._create_error("Deletion Failed", error)

    async def delete_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            valid, error, agent = self._validate_and_get_agent(args)
            if not valid:
                return error
            return self._perform_delete(args["agent_id"], agent.state.name, agent.state.managed_file)
        except Exception as e:
            return self._handle_exception(e, "Delete")

    def _get_file_language(self, filename: str) -> str:
        file_ext = filename.split(".")[-1].lower() if "." in filename else "text"
        lang_map = {"py": "python", "js": "javascript", "html": "html", "css": "css", "sql": "sql"}
        return lang_map.get(file_ext, file_ext)

    def _build_file_response(self, agent, file_content: Optional[str]) -> str:
        filename = agent.state.managed_file
        if file_content is None:
            return f"📄 **File Status:** `{filename}`\n\nAgent: {agent.state.name}\nFile does not exist yet."
        language = self._get_file_language(filename)
        return (
            f"📄 **File Content:** `{filename}`\n\n"
            f"**Agent:** {agent.state.name}\n"
            f"**Size:** {len(file_content)} characters\n\n"
            f"```{language}\n{file_content}\n```"
        )

    async def get_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            valid, error, agent = self._validate_and_get_agent(args)
            if not valid:
                return error
            file_content = agent.read_managed_file()
            return self._create_success(self._build_file_response(agent, file_content))
        except Exception as e:
            return self._handle_exception(e, "File")

    def _handle_file_update(self, agent, agent_response) -> None:
        # Check if necessary conditions are met
        has_file_content = hasattr(agent_response, "file_content") and agent_response.file_content
        is_successful = agent_response.status == ResponseStatus.SUCCESS

        # Guard clause: return early if conditions are not met
        if not (has_file_content and is_successful):
            return

        # Check filename match
        if agent_response.file_content.filename != agent.state.managed_file:
            return

        # Attempt to write the file
        success = agent.write_managed_file(agent_response.file_content.content)

        # Update response based on success
        if success:
            agent_response.changes_made.append("File written to disk")
        else:
            agent_response.warnings.append("File write failed")

    def _build_chat_response(self, agent, agent_response) -> str:
        result_text = f"🤖 **Agent {agent.state.name}:**\n\n**Status:** {agent_response.status.value}\n"
        result_text += f"**Response:** {agent_response.message}\n\n"
        if agent_response.file_content:
            result_text += f"**File Updated:** `{agent_response.file_content.filename}`\n"
        if agent_response.changes_made:
            result_text += f"**Changes:** {', '.join(agent_response.changes_made)}\n"
        if agent_response.warnings:
            result_text += f"**⚠️ Warnings:** {', '.join(agent_response.warnings)}\n"
        result_text += f"\n*📊 Tokens: {agent_response.tokens_used} | ⏱️ Time: {agent_response.processing_time:.1f}s*"
        return result_text

    def _validate_chat_args(self, args: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        if not args.get("agent_id") or not args.get("message"):
            return False, self._create_error("Missing Parameters", "agent_id and message are required")
        if not self.llm_manager.model_loaded:
            return False, self._create_error("Model Error", "Model not loaded")
        return True, None

    def _create_agent_request(self, args: dict[str, Any]) -> Any:
        return create_standard_request(
            task_type=TaskType(args.get("task_type", "update")),
            instruction=args["message"],
            context=args.get("context"),
            parameters=args.get("parameters", {}),
        )

    def _generate_agent_response(self, agent, agent_request) -> tuple[Any, dict]:
        prompt = agent.build_context_prompt(agent_request)
        return self.llm_manager.generate_response(prompt)

    def _update_agent_and_registry(self, agent, agent_request, agent_response) -> None:
        self._handle_file_update(agent, agent_response)
        agent.update_activity(agent_request.task_type)
        agent.update_success_rate(agent_response.status.value == "success")
        agent.add_conversation(agent_request, agent_response)
        self.agent_registry.save_registry()

    def _process_chat(self, agent: Any, args: dict[str, Any]) -> dict[str, Any]:
        agent_request = self._create_agent_request(args)
        agent_response, _ = self._generate_agent_response(agent, agent_request)
        self._update_agent_and_registry(agent, agent_request, agent_response)
        return self._create_success(self._build_chat_response(agent, agent_response))

    def _validate_and_get_agent_for_chat(self, args: dict[str, Any]) -> tuple[bool, dict[str, Any], Optional[Any]]:
        valid_args, error = self._validate_chat_args(args)
        if not valid_args:
            return False, error, None

        valid, error, agent = self._validate_and_get_agent(args)
        if not valid:
            return False, error, None

        return True, None, agent

    async def chat_with_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            valid, error, agent = self._validate_and_get_agent_for_chat(args)
            if not valid:
                return error

            return self._process_chat(agent, args)
        except Exception as e:
            return self._handle_exception(e, "Chat")

    def _build_system_status(self, model_info, performance, registry_stats, authenticator) -> str:
        status_text = "🖥️ **System Status Report**\n\n"
        model_loaded = model_info["model_loaded"]
        status_text += f"**🤖 Model Status:** {'✅ Loaded' if model_loaded else '❌ Not Loaded'}\n"
        if model_loaded:
            status_text += f"**Performance:** {performance.get('avg_tokens_per_second', 0)} tokens/sec\n"
        status_text += "\n**👥 Agent Registry:**\n"
        status_text += f"**Total Agents:** {registry_stats['total_agents']}\n"
        status_text += f"**Managed Files:** {registry_stats['managed_files']}\n"
        status_text += f"**Total Interactions:** {registry_stats['total_interactions']}\n"
        if authenticator:
            security_status = authenticator.get_security_status()
            status_text += "\n**🔒 Authentication:**\n"
            enabled_text = "✅ Active" if security_status["enabled"] else "⚠️ Development Mode"
            status_text += f"**Security Manager:** {enabled_text}\n"
            if security_status["enabled"]:
                status_text += f"**Active Sessions:** {security_status['active_sessions']}\n"
        status_text += "\n**🔧 System Configuration:**\n"
        status_text += "**CUDA Optimized:** ✅ RTX 1080ti + CUDA 12.9\n"
        status_text += "**JSON Schema:** ✅ Enabled\n"
        status_text += "**Authentication:** ✅ Required for MCP operations\n"
        return status_text

    async def system_status(self, args: dict[str, Any] = None, authenticator=None) -> dict[str, Any]:
        try:
            model_info = self.llm_manager.get_model_info()
            performance = self.llm_manager.get_performance_summary()
            registry_stats = self.agent_registry.get_registry_stats()
            return self._create_success(
                self._build_system_status(model_info, performance, registry_stats, authenticator)
            )
        except Exception as e:
            return self._handle_exception(e, "Status")

    # Git Tool Handlers - Delegated to MCPGitHandlers
    async def git_status(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Check git repository status and changes"""
        return await self.git_handlers.git_status(args)

    async def git_diff(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Show git diff of changes"""
        return await self.git_handlers.git_diff(args)

    async def git_commit(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create git commit with message"""
        return await self.git_handlers.git_commit(args)

    async def git_log(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Show git commit history"""
        return await self.git_handlers.git_log(args)

    # Testing & Validation Tool Handlers - Delegated to MCPValidationHandlers
    async def run_tests(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Run pytest tests for the project"""
        return await self.validation_handlers.run_tests(args)

    async def run_pre_commit(self, args: dict[str, Any] = None) -> dict[str, Any]:
        """Run pre-commit hooks for validation"""
        return await self.validation_handlers.run_pre_commit(args)

    async def validate_file_length(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check if files comply with length requirements (<300 lines)"""
        return await self.validation_handlers.validate_file_length(args)

    async def validate_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate an agent's managed file meets all requirements"""
        return await self.validation_handlers.validate_agent_file(args)
