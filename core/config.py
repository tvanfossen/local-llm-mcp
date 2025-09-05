# File: ~/Projects/local-llm-mcp/core/config.py
"""Configuration Management with Repository Integration

Responsibilities:
- Model configuration (CUDA settings, paths, parameters)
- Server configuration (host, port, logging)
- Repository path detection and workspace management
- Container environment detection for /workspace integration
- Hardware optimization settings for RTX 1080ti + CUDA 12.9
Workspace: Container /workspace or host-based paths with .mcp-agents/ structure
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelConfig:
    """Model configuration optimized for RTX 1080ti with CUDA 12.9"""

    # Model settings
    model_path: str
    n_gpu_layers: int = -1  # -1 = all layers on GPU
    n_ctx: int = 8192  # Context window
    n_batch: int = 512  # Batch size for processing
    n_threads: int = 8  # CPU threads (i7-7700k has 8)

    # Memory optimization
    use_mmap: bool = True
    use_mlock: bool = False
    f16_kv: bool = True  # Half precision key/value cache
    logits_all: bool = False

    # CUDA optimization
    tensor_split: list | None = None
    main_gpu: int = 0

    # Generation defaults
    temperature: float = 0.1
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    max_tokens: int = 2048

    # Logging
    verbose: bool = False

    @classmethod
    def from_env(cls) -> "ModelConfig":
        """Create config from environment variables"""
        return cls(
            model_path=os.getenv("MODEL_PATH", "./models/Qwen2.5-7B-Instruct-Q6_K_L.gguf"),
            n_gpu_layers=int(os.getenv("N_GPU_LAYERS", "-1")),
            n_ctx=int(os.getenv("N_CTX", "8192")),
            n_batch=int(os.getenv("N_BATCH", "512")),
            n_threads=int(os.getenv("N_THREADS", "8")),
            use_mmap=os.getenv("USE_MMAP", "True").lower() == "true",
            use_mlock=os.getenv("USE_MLOCK", "False").lower() == "true",
            verbose=os.getenv("VERBOSE", "False").lower() == "true",
            temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("DEFAULT_MAX_TOKENS", "2048")),
        )

    def validate(self) -> bool:
        """Validate configuration"""
        if not Path(self.model_path).exists():
            return False
        if self.n_ctx <= 0 or self.n_batch <= 0:
            return False
        return True


@dataclass
class ServerConfig:
    """Server configuration for HTTP and WebSocket"""

    host: str = "0.0.0.0"  # nosec B104
    port: int = 8000

    # CORS settings
    allow_origins: list = None
    allow_credentials: bool = True

    # Logging
    log_level: str = "info"
    access_log: bool = True

    # WebSocket settings
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 20

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create config from environment variables"""
        return cls(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "info"),
            access_log=os.getenv("ACCESS_LOG", "true").lower() == "true",
        )

    def __post_init__(self):
        if self.allow_origins is None:
            self.allow_origins = ["*"]


@dataclass
class SystemConfig:
    """System-wide configuration with repository integration"""

    # Base directory paths
    base_dir: Path
    state_dir: Path
    workspaces_dir: Path
    logs_dir: Path

    # Repository integration
    repo_path: Path | None = None

    # Agent settings
    max_agents: int = 100
    max_conversation_history: int = 1000

    # File management
    max_file_size: int = 1024 * 1024  # 1MB
    allowed_extensions: list = None

    def __init__(self, base_dir: Path | None = None, repo_path: Path | None = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.repo_path = repo_path

        # Set up directory structure based on environment
        if self.is_container_environment():
            self._setup_container_directories()
        else:
            self._setup_host_directories()

        if self.allowed_extensions is None:
            self.allowed_extensions = [
                ".py",
                ".js",
                ".html",
                ".css",
                ".sql",
                ".md",
                ".json",
                ".yaml",
                ".toml",
            ]

    def _setup_container_directories(self):
        """Setup directories for container environment"""
        # In container: workspace is /workspace, state/logs are in /app
        self.state_dir = self.base_dir / "state"
        self.logs_dir = self.base_dir / "logs"
        # Workspaces now managed in repository .mcp-agents directory
        workspace_root = self.get_workspace_root()
        self.workspaces_dir = workspace_root / ".mcp-agents"

    def _setup_host_directories(self):
        """Setup directories for host environment (backward compatibility)"""
        # Host environment: traditional structure
        self.state_dir = self.base_dir / "state"
        self.workspaces_dir = self.base_dir / "workspaces"
        self.logs_dir = self.base_dir / "logs"

    def is_container_environment(self) -> bool:
        """Detect if running in container environment"""
        workspace_path = Path("/workspace")
        return workspace_path.exists() and workspace_path.is_dir()

    def get_workspace_root(self) -> Path:
        """Get workspace root directory"""
        if self.is_container_environment():
            return Path("/workspace")
        elif self.repo_path:
            return self.repo_path
        else:
            return self.base_dir

    def get_agents_metadata_dir(self) -> Path:
        """Get .mcp-agents directory for agent metadata"""
        return self.get_workspace_root() / ".mcp-agents"

    def get_registry_file(self) -> Path:
        """Get agent registry file location"""
        if self.is_container_environment():
            # In container: registry in .mcp-agents for persistence
            return self.get_agents_metadata_dir() / "registry.json"
        else:
            # Host: traditional location for backward compatibility
            return self.state_dir / "agents.json"

    def ensure_directories(self):
        """Ensure all required directories exist"""
        directories_to_create = [self.state_dir, self.logs_dir]

        # Always create .mcp-agents structure
        agents_dir = self.get_agents_metadata_dir()
        directories_to_create.append(agents_dir)

        # Create workspaces_dir only in host mode for backward compatibility
        if not self.is_container_environment():
            directories_to_create.append(self.workspaces_dir)

        for directory in directories_to_create:
            directory.mkdir(parents=True, exist_ok=True)

    def get_agent_workspace_dir(self, agent_id: str) -> Path:
        """Get workspace directory for specific agent"""
        if self.is_container_environment():
            # Container: agent metadata in .mcp-agents, files in workspace root
            return self.get_agents_metadata_dir() / agent_id
        else:
            # Host: traditional workspace structure
            return self.workspaces_dir / agent_id

    def get_environment_info(self) -> dict:
        """Get environment and workspace information"""
        return {
            "container_environment": self.is_container_environment(),
            "workspace_root": str(self.get_workspace_root()),
            "agents_metadata_dir": str(self.get_agents_metadata_dir()),
            "registry_file": str(self.get_registry_file()),
            "repo_integration": self.repo_path is not None,
        }


class ConfigManager:
    """Centralized configuration management with repository integration"""

    def __init__(self, repo_path: Path | None = None):
        self.model = ModelConfig.from_env()
        self.server = ServerConfig.from_env()
        self.system = SystemConfig(repo_path=repo_path)

        # Ensure directories exist
        self.system.ensure_directories()

    def validate_all(self) -> tuple[bool, list[str]]:
        """Validate all configurations"""
        errors = []

        if not self.model.validate():
            errors.append(f"Model file not found: {self.model.model_path}")

        if not (1 <= self.server.port <= 65535):
            errors.append(f"Invalid port: {self.server.port}")

        # Validate workspace access in container environment
        if self.system.is_container_environment():
            workspace_root = self.system.get_workspace_root()
            if not workspace_root.exists():
                errors.append(f"Workspace root not accessible: {workspace_root}")

        return len(errors) == 0, errors

    def get_model_info(self) -> dict:
        """Get model configuration info"""
        return {
            "model_path": self.model.model_path,
            "gpu_layers": self.model.n_gpu_layers,
            "context_size": self.model.n_ctx,
            "batch_size": self.model.n_batch,
            "threads": self.model.n_threads,
            "cuda_optimized": True,
        }

    def get_server_info(self) -> dict:
        """Get server configuration info"""
        return {
            "host": self.server.host,
            "port": self.server.port,
            "cors_enabled": len(self.server.allow_origins) > 0,
            "websocket_enabled": True,
        }

    def get_environment_info(self) -> dict:
        """Get environment and workspace information"""
        return {
            "container_environment": self.system.is_container_environment(),
            "workspace_root": str(self.system.get_workspace_root()),
            "agents_metadata_dir": str(self.system.get_agents_metadata_dir()),
            "registry_file": str(self.system.get_registry_file()),
            "repo_integration": self.system.repo_path is not None,
        }
