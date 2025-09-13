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
        if not self.model_config:
            logger.error("No model configuration provided")
            return False, "No model configuration provided"
        
        if not self.model_path:
            logger.error("No model path specified")
            return False, "No model path specified"

        # Check if model file exists
        if not Path(self.model_path).exists():
            logger.error(f"Model file not found: {self.model_path}")
            return False, f"Model file not found: {self.model_path}"

        # Check for llama-cpp-python
        try:
            from llama_cpp import Llama
        except ImportError:
            logger.error("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
            return False, "llama-cpp-python not installed"

        # Load model
        try:
            logger.info(f"Loading model: {self.model_path}")
            
            # Unload existing model if any
            if hasattr(self, 'llm') and self.llm:
                self.unload_model()
            
            self.llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=getattr(self.model_config, 'n_gpu_layers', 0),
                n_ctx=getattr(self.model_config, 'n_ctx', 2048),
                n_batch=getattr(self.model_config, 'n_batch', 512),
                n_threads=getattr(self.model_config, 'n_threads', 4),
                use_mmap=getattr(self.model_config, 'use_mmap', True),
                use_mlock=getattr(self.model_config, 'use_mlock', False),
                verbose=False,
            )
            
            self.model_loaded = True
            logger.info("Model loaded successfully")
            
            # Reset performance stats for new model
            self.reset_performance_stats()
            
            return True, "Model loaded successfully"

        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            self.model_loaded = False
            
            # Clean up partial initialization
            if hasattr(self, 'llm'):
                delattr(self, 'llm')
            
            return False, f"Failed to load model: {str(e)}"


    def unload_model(self):
        """Unload the model and free resources"""
        if hasattr(self, 'llm') and self.llm:
            logger.info("Unloading model...")
            # Clean up model resources
            del self.llm
            self.llm = None
        
        self.model_loaded = False
        logger.info("Model unloaded successfully")
    
    def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7, stop_tokens: list = None) -> dict:
        """Generate response from loaded model"""
        if not self.model_loaded:
            return {
                "success": False,
                "error": "Model not loaded. Call load_model() first.",
                "response": None
            }
        
        if not hasattr(self, 'llm') or not self.llm:
            return {
                "success": False,
                "error": "Model instance not available",
                "response": None
            }
        
        try:
            # Update performance stats
            import time
            start_time = time.time()
            
            self.performance_stats["total_requests"] += 1
            
            # Generate response
            response = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop_tokens or [],
                echo=False
            )
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Update performance stats
            self.performance_stats["successful_requests"] += 1
            
            # Update average response time
            total_successful = self.performance_stats["successful_requests"]
            current_avg = self.performance_stats["average_response_time"]
            new_avg = ((current_avg * (total_successful - 1)) + response_time) / total_successful
            self.performance_stats["average_response_time"] = new_avg
            
            return {
                "success": True,
                "error": None,
                "response": response["choices"][0]["text"],
                "usage": response.get("usage", {}),
                "response_time": response_time
            }
            
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": None
            }
    
    def is_ready(self) -> bool:
        """Check if model is ready for inference"""
        return self.model_loaded and hasattr(self, 'llm') and self.llm is not None
    
    def get_model_capabilities(self) -> dict:
        """Get model capabilities and configuration"""
        if not self.model_config:
            return {"capabilities": "unknown", "config": None}
        
        return {
            "context_size": getattr(self.model_config, 'n_ctx', 2048),
            "batch_size": getattr(self.model_config, 'n_batch', 512),
            "gpu_layers": getattr(self.model_config, 'n_gpu_layers', 0),
            "threads": getattr(self.model_config, 'n_threads', 4),
            "use_mmap": getattr(self.model_config, 'use_mmap', True),
            "use_mlock": getattr(self.model_config, 'use_mlock', False),
            "model_path": self.model_path,
            "loaded": self.model_loaded
        }
    
    def reset_performance_stats(self):
        """Reset performance statistics"""
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "average_response_time": 0.0
        }
        logger.info("Performance statistics reset")
