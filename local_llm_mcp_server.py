#!/usr/bin/env python3

"""File: ~/Projects/local-llm-mcp/local_llm_mcp_server.py
Main Entry Point - Agent-Based Local LLM MCP Server

Responsibilities:
- Orchestrate system initialization
- Start HTTP server with MCP endpoint
- Handle graceful shutdown
- Minimal coordination between components

Environment: Ubuntu 22.04, NVIDIA Driver 575, CUDA 12.9, RTX 1080ti (11GB VRAM)
Usage: uv run local_llm_mcp_server.py
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

from src.api.http.server.server import create_http_server
from src.core.agents.registry.registry import AgentRegistry
from src.core.config.manager.manager import ConfigManager
from src.core.llm.manager.manager import LLMManager
from src.core.utils.utils import handle_exception
from src.mcp.tools.executor.executor import ConsolidatedToolExecutor

# Add src to Python path for new structure
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ServerOrchestrator:
    """Minimal orchestrator that coordinates system components

    Responsibilities:
    - Initialize configuration
    - Create and wire components
    - Start/stop HTTP server
    - Handle graceful shutdown
    """

    def __init__(self):
        self.config_manager = None
        self.llm_manager = None
        self.agent_registry = None
        self.tool_executor = None
        self.server = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self) -> bool:
        """Initialize all system components - simplified error handling"""
        try:
            # Initialize components in sequence for consolidated 4-tool system
            initialization_steps = [
                ("config", self._initialize_config),
                ("LLM manager", self._initialize_llm),
                ("agent registry", self._initialize_agent_registry),
                ("consolidated tool executor", self._initialize_tool_executor),
            ]

            for step_name, step_func in initialization_steps:
                success = await step_func() if asyncio.iscoroutinefunction(step_func) else step_func()
                if not success:
                    logger.error(f"Failed to initialize {step_name}")
                    return False

            logger.info("✅ All components initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            # Use shared utility for consistent error handling
            error_response = handle_exception(e, "Server Initialization")
            logger.error(f"Error details: {error_response}")
            return False

    async def start_server(self):
        """Start the HTTP server with MCP endpoint"""
        try:
            # Create HTTP application with consolidated toolchain
            app = create_http_server(
                agent_registry=self.agent_registry,
                llm_manager=self.llm_manager,
                config=self.config_manager,
            )

            # Configure uvicorn
            config = uvicorn.Config(
                app=app,
                host=self.config_manager.server.host,
                port=self.config_manager.server.port,
                log_level=self.config_manager.server.log_level.lower(),
                access_log=self.config_manager.server.access_log,
            )

            self.server = uvicorn.Server(config)

            # Log startup info
            self._log_startup_info()

            # Start server
            await self.server.serve()

        except Exception as e:
            logger.error(f"Server startup failed: {e}")
            raise

    def _log_startup_info(self):
        """Log server startup information"""
        logger.info(
            f"🚀 Starting Consolidated MCP Server on {self.config_manager.server.host}:{self.config_manager.server.port}"
        )
        logger.info("📡 MCP endpoint: POST /mcp (for Claude Code)")
        logger.info("🔧 HTTP API: /api/* (for testing/debugging)")
        logger.info("❤️ Health check: GET /health")
        logger.info("📊 System info: GET /")
        logger.info("🛠️  4 Core Tools: local_model, git_operations, workspace, validation")

        # Model and agent info
        model_info = self.config_manager.get_model_info()
        logger.info(f"🤖 Model: {model_info['model_path']}")
        logger.info(f"⚡ GPU Layers: {model_info['gpu_layers']}")
        logger.info(f"🧠 Context: {model_info['context_size']} tokens")

        agent_stats = self.agent_registry.get_registry_stats()
        logger.info(f"👥 Active Agents: {agent_stats['total_agents']}")
        logger.info(f"📂 Managed Files: {agent_stats['managed_files']}")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down server...")

        try:
            # Stop HTTP server
            if self.server:
                self.server.should_exit = True
                await asyncio.sleep(0.1)  # Give server time to stop

            # Save agent states
            if self.agent_registry:
                logger.info("💾 Saving agent states...")
                self.agent_registry.save_registry()

            # Unload model to free GPU memory
            if self.llm_manager:
                logger.info("🔄 Unloading model...")
                self.llm_manager.unload_model()

            logger.info("✅ Shutdown completed successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, _frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _initialize_config(self) -> bool:
        """Initialize and validate configuration"""
        logger.info("Initializing configuration...")
        self.config_manager = ConfigManager()

        # Validate configuration
        valid, errors = self.config_manager.validate_all()
        if not valid:
            logger.error(f"Configuration validation failed: {errors}")
            return False

        return True

    async def _initialize_llm(self) -> bool:
        """Initialize LLM manager and load model"""
        logger.info("Initializing LLM manager...")
        self.llm_manager = LLMManager(self.config_manager.model)

        # Load model
        logger.info("Loading model...")
        success, error = self.llm_manager.load_model()
        if not success:
            logger.error(f"Model loading failed: {error}")
            return False

        return True

    def _initialize_tool_executor(self) -> bool:
        """Initialize consolidated tool executor and update agent registry"""
        logger.info("Initializing consolidated tool executor (4 core tools)...")
        self.tool_executor = ConsolidatedToolExecutor(self.agent_registry, self.llm_manager)

        # Update agent registry with consolidated toolchain
        self.agent_registry.update_toolchain(self.llm_manager, self.tool_executor)

        logger.info("✅ Tool executor ready with: local_model, git_operations, workspace, validation")
        logger.info("✅ Agent registry updated with consolidated toolchain")
        return True

    def _initialize_agent_registry(self):
        """Initialize agent registry"""
        logger.info("Initializing agent registry...")
        self.agent_registry = AgentRegistry(self.config_manager)
        return True


async def main():
    """Main entry point"""
    orchestrator = ServerOrchestrator()

    try:
        # Setup signal handlers
        orchestrator.setup_signal_handlers()

        # Initialize system
        logger.info("🔧 Initializing Consolidated 4-Tool MCP Server...")
        success = await orchestrator.initialize()

        if not success:
            logger.error("❌ Initialization failed, exiting")
            sys.exit(1)

        # Start server
        await orchestrator.start_server()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
