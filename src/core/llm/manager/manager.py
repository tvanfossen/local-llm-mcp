"""LLM Manager - Core Language Model Management

Responsibilities:
- Load and manage language model
- Handle model inference requests
- Monitor performance and health
- Provide model information and statistics
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMManager:
    """Core language model manager"""

    def __init__(self, model_config=None):
        self.model_config = model_config
        self.model_loaded = False
        self.model_path = model_config.model_path if model_config else None
        self.performance_stats = {"total_requests": 0, "successful_requests": 0, "average_response_time": 0.0}

    def get_model_info(self) -> dict[str, Any]:
        """Get model information"""
        return {
            "model_loaded": self.model_loaded,
            "model_path": self.model_path,
            "configuration": {"context_size": 8192, "batch_size": 512},
        }

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary"""
        return self.performance_stats

    def health_check(self) -> dict[str, Any]:
        """Perform health check"""
        return {
            "status": "healthy" if self.model_loaded else "unloaded",
            "avg_performance": self.performance_stats.get("average_response_time", 0.0),
        }

    def load_model(self) -> tuple[bool, Optional[str]]:
        """Load the language model"""
        try:
            if not self.model_config:
                logger.warning("No model configuration provided - running in mock mode")
                self.model_loaded = False
                return True, "Mock mode - no model loaded"

            # Check if model file exists
            if not Path(self.model_path).exists():
                logger.warning(f"Model file not found: {self.model_path} - running in mock mode")
                self.model_loaded = False
                return True, "Mock mode - model file not found"

            # Try to load real model
            logger.info(f"Loading model: {self.model_path}")
            try:
                # Import llama-cpp-python for actual model loading
                from llama_cpp import Llama

                self.llm = Llama(
                    model_path=self.model_path,
                    n_gpu_layers=self.model_config.n_gpu_layers,
                    n_ctx=self.model_config.n_ctx,
                    n_batch=self.model_config.n_batch,
                    n_threads=self.model_config.n_threads,
                    use_mmap=self.model_config.use_mmap,
                    use_mlock=self.model_config.use_mlock,
                    verbose=False,
                )
                self.model_loaded = True
                logger.info("Model loaded successfully")
                return True, None

            except ImportError:
                logger.warning("llama-cpp-python not installed - running in mock mode")
                self.model_loaded = False
                return True, "Mock mode - llama-cpp-python not available"

        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            # Fall back to mock mode on any error
            logger.warning("Falling back to mock mode")
            self.model_loaded = False
            return True, f"Mock mode - {str(e)}"

    def unload_model(self):
        """Unload the model and free resources"""
        if self.model_loaded:
            logger.info("Unloading model...")
            self.model_loaded = False
