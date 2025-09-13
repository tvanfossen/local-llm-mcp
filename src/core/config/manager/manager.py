# File: ~/Projects/local-llm-mcp/src/core/config/manager/manager.py
"""Configuration Management with Repository Integration

Responsibilities:
- Model configuration (CUDA settings, paths, parameters)
- Server configuration (host, port, logging)
- Repository path detection and workspace management
- Container environment detection for /workspace integration
- Hardware optimization settings for RTX 1080ti + CUDA 12.9
Workspace: Container /workspace or host-based paths with .mcp-agents/ structure
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from src.core.utils.utils import get_workspace_root


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
    use_mlock: bool = False  # True for production, False for development
    low_vram: bool = False  # False for RTX 1080ti (8GB VRAM)

    # Performance tuning
    rope_scaling_type: int = 1  # RoPE scaling
    rope_freq_base: float = 10000.0
    rope_freq_scale: float = 1.0

    # Generation settings
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Only warn about missing model path, don't fail
        if not Path(self.model_path).exists():
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Model path does not exist: {self.model_path}")


@dataclass
class ServerConfig:
    """Server configuration for HTTP and WebSocket endpoints"""

    host: str = "0.0.0.0"  # Bind to all interfaces for Docker compatibility
    port: int = 8000
    log_level: str = "INFO"

    # CORS settings
    allow_origins: list[str] = None
    allow_credentials: bool = True

    # Request limits
    max_request_size: int = 50 * 1024 * 1024  # 50MB
    request_timeout: float = 300.0  # 5 minutes
    access_log: bool = True

    def __post_init__(self):
        """Set defaults for mutable fields"""
        if self.allow_origins is None:
            self.allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]


@dataclass
class SystemConfig:
    """System paths and workspace configuration"""

    workspace_root: Path
    state_dir: Path
    agents_dir: Path
    logs_dir: Path
    temp_dir: Path

    # Container detection
    is_container: bool = False
    container_workspace: Path = Path("/workspace")

    def __post_init__(self):
        """Ensure all directories exist with proper permissions"""
        import os
        import stat

        for directory in [self.workspace_root, self.state_dir, self.agents_dir, self.logs_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)

            # Ensure directories are user-writable (fixes container permission issues)
            try:
                os.chmod(directory, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            except (OSError, PermissionError):
                # If we can't set permissions, at least log it but don't fail
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not set permissions on directory: {directory}")

    def is_container_environment(self) -> bool:
        """Check if running in container environment"""
        return self.is_container or self.container_workspace.exists()

    def get_workspace_root(self) -> Path:
        """Get appropriate workspace root for environment"""
        if self.is_container_environment():
            return self.container_workspace
        return self.workspace_root


class ConfigManager:
    """Central configuration manager with automatic path detection"""

    def __init__(self, config_path: str = None):
        self.model = self._create_model_config()
        self.server = ServerConfig()
        self.system = self._create_system_config()

        if config_path:
            self._load_from_file(config_path)

    def _create_model_config(self) -> ModelConfig:
        """Create model configuration with automatic path detection"""
        # Common model paths
        possible_paths = [
            Path.home() / "models" / "Qwen2.5-7B-Instruct-Q6_K_L.gguf",
            Path("/models/Qwen2.5-7B-Instruct-Q6_K_L.gguf"),
            Path("./models/Qwen2.5-7B-Instruct-Q6_K_L.gguf"),
        ]

        for path in possible_paths:
            if path.exists():
                return ModelConfig(model_path=str(path))

        # Default path (may not exist)
        return ModelConfig(model_path=str(possible_paths[0]))

    def _create_system_config(self) -> SystemConfig:
        """Create system configuration with workspace detection"""
        # Detect if we're in a container
        is_container = Path("/.dockerenv").exists() or os.environ.get("CONTAINER") == "true"

        if is_container or Path("/workspace").exists():
            # Container environment
            workspace = Path("/workspace")
            return SystemConfig(
                workspace_root=workspace,
                state_dir=workspace / ".mcp-state",
                agents_dir=workspace / ".mcp-agents",
                logs_dir=workspace / ".mcp-logs",
                temp_dir=workspace / ".mcp-tmp",
                is_container=True,
            )
        else:
            # Host environment - use shared utility
            workspace = get_workspace_root()
            return SystemConfig(
                workspace_root=workspace,
                state_dir=workspace / ".mcp-state",
                agents_dir=workspace / ".mcp-agents",
                logs_dir=workspace / ".mcp-logs",
                temp_dir=workspace / ".mcp-tmp",
                is_container=False,
            )

    def _load_from_file(self, config_path: str):
        """Load configuration from file (TOML/JSON/YAML)"""
        # Implementation would depend on preferred config format
        # For now, this is a placeholder
        pass

    def get_effective_config(self) -> dict:
        """Get effective configuration as dictionary"""
        return {
            "model": {
                "path": self.model.model_path,
                "gpu_layers": self.model.n_gpu_layers,
                "context_size": self.model.n_ctx,
                "batch_size": self.model.n_batch,
                "temperature": self.model.temperature,
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "cors_origins": self.server.allow_origins,
            },
            "system": {
                "workspace": str(self.system.workspace_root),
                "is_container": self.system.is_container_environment(),
                "agents_dir": str(self.system.agents_dir),
                "state_dir": str(self.system.state_dir),
            },
        }

    def validate_all(self) -> tuple[bool, list[str]]:
        """Validate complete configuration - alias for validate_config"""
        return self.validate_config()

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate complete configuration"""
        errors = []

        # Validate model (warn only in development)
        if not Path(self.model.model_path).exists():
            # Only fail validation in production, warn in development
            import os

            if os.environ.get("ENVIRONMENT") == "production":
                errors.append(f"Model file not found: {self.model.model_path}")
            # Development mode: continue without model

        # Validate server
        if not (1024 <= self.server.port <= 65535):
            errors.append(f"Invalid port number: {self.server.port}")

        # Validate system paths
        try:
            self.system.__post_init__()
        except Exception as e:
            errors.append(f"Failed to create system directories: {e}")

        return len(errors) == 0, errors

    def get_model_info(self) -> dict:
        """Get model configuration information"""
        return {
            "model_path": self.model.model_path,
            "gpu_layers": self.model.n_gpu_layers,
            "context_size": self.model.n_ctx,
            "batch_size": self.model.n_batch,
            "temperature": self.model.temperature,
        }


# Global configuration instance
_config_instance = None


def get_config() -> ConfigManager:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def set_config(config: ConfigManager):
    """Set global configuration instance"""
    global _config_instance
    _config_instance = config
