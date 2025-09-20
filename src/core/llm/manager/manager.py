"""LLM Manager - Core Language Model Management

Responsibilities:
- Load and manage language model
- Handle model inference requests with tool calling support
- Monitor performance and health
- Provide model information and statistics
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.mcp.bridge.bridge import MCPBridge

logger = logging.getLogger(__name__)


class LLMManager:
    """Core language model manager"""

    def __init__(self, model_config=None, tool_executor=None, task_queue=None):
        self.model_config = model_config
        self.model_loaded = False
        self.model_path = model_config.model_path if model_config else None
        self.performance_stats = {"total_requests": 0, "successful_requests": 0, "average_response_time": 0.0}

        # Initialize MCP Bridge with tool executor and task queue
        self.mcp_bridge = None
        self.tool_executor = tool_executor
        self.task_queue = task_queue
        self.available_tools = []

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
            if hasattr(self, "llm") and self.llm:
                self.unload_model()

            self.llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=getattr(self.model_config, "n_gpu_layers", -1),
                n_ctx=getattr(self.model_config, "n_ctx", 8291),
                n_batch=getattr(self.model_config, "n_batch", 512),
                n_threads=getattr(self.model_config, "n_threads", 4),
                use_mmap=getattr(self.model_config, "use_mmap", True),
                use_mlock=getattr(self.model_config, "use_mlock", False),
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
            if hasattr(self, "llm"):
                delattr(self, "llm")

            return False, f"Failed to load model: {str(e)}"

    def unload_model(self):
        """Unload the model and free resources"""
        if hasattr(self, "llm") and self.llm:
            logger.info("Unloading model...")
            # Clean up model resources
            del self.llm
            self.llm = None

        self.model_loaded = False
        logger.info("Model unloaded successfully")

    def generate_response(
        self, prompt: str, max_tokens: int = 512, temperature: float = 0.7, stop_tokens: list = None
    ) -> dict:
        """Generate response from loaded model"""
        if not self.model_loaded:
            return {"success": False, "error": "Model not loaded. Call load_model() first.", "response": None}

        if not hasattr(self, "llm") or not self.llm:
            return {"success": False, "error": "Model instance not available", "response": None}

        try:
            # Update performance stats
            import time

            start_time = time.time()

            self.performance_stats["total_requests"] += 1

            # Generate response
            response = self.llm(
                prompt, max_tokens=max_tokens, temperature=temperature, stop=stop_tokens or [], echo=False
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
                "response_time": response_time,
            }

        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return {"success": False, "error": str(e), "response": None}

    def is_ready(self) -> bool:
        """Check if model is ready for inference"""
        return self.model_loaded and hasattr(self, "llm") and self.llm is not None

    def get_model_capabilities(self) -> dict:
        """Get model capabilities and configuration"""
        if not self.model_config:
            return {"capabilities": "unknown", "config": None}

        return {
            "context_size": getattr(self.model_config, "n_ctx", 8192),
            "batch_size": getattr(self.model_config, "n_batch", 512),
            "gpu_layers": getattr(self.model_config, "n_gpu_layers", -1),
            "threads": getattr(self.model_config, "n_threads", 4),
            "use_mmap": getattr(self.model_config, "use_mmap", True),
            "use_mlock": getattr(self.model_config, "use_mlock", False),
            "model_path": self.model_path,
            "loaded": self.model_loaded,
        }

    def reset_performance_stats(self):
        """Reset performance statistics"""
        self.performance_stats = {"total_requests": 0, "successful_requests": 0, "average_response_time": 0.0}
        logger.info("Performance statistics reset")

    def register_tools(self, tools: list):
        """Register MCP tools for model use"""
        logger.debug(f"ENTRY register_tools: {len(tools)} tools")
        self.available_tools = tools

        # Initialize MCP Bridge with tools, tool executor, and task queue
        if self.tool_executor:
            self.mcp_bridge = MCPBridge(
                task_queue=self.task_queue,
                tool_executor=self.tool_executor,
                available_tools=tools,
                use_xml=True  # Enable XML mode for structured generation
            )

            # Register ToolCallExecutor with task queue if available
            if self.task_queue:
                from src.core.tasks.queue.queue import ToolCallExecutor
                tool_call_executor = ToolCallExecutor(self.tool_executor)
                # Register tool call executor with unified queue
                self.task_queue.register_executor("tool_call", tool_call_executor)
                logger.info(f"✅ MCP Bridge initialized with {len(tools)} tools and task queue")
            else:
                logger.info(f"✅ MCP Bridge initialized with {len(tools)} tools (no queue)")
        else:
            logger.warning("⚠️ No tool executor available - MCP Bridge not initialized")

        logger.debug(f"EXIT register_tools: bridge_ready={self.mcp_bridge.is_ready() if self.mcp_bridge else False}")

    def _format_tools_for_qwen(self) -> str:
        """Format tools for Qwen2.5-7B prompt"""
        if not self.mcp_bridge:
            return ""
        return self.mcp_bridge.get_tools_prompt()

    async def generate_with_tools(self, prompt: str, max_tokens: int = 512,
                                 temperature: float = 0.7, tools_enabled: bool = True) -> Dict[str, Any]:
        """Generate response with tool calling capability"""
        print(f"DEBUG: generate_with_tools called with tools_enabled={tools_enabled}")
        if not self.model_loaded:
            print(f"DEBUG: Model not loaded, returning error")
            return {
                "success": False,
                "error": "Model not loaded",
                "type": "error"
            }

        # Enhance prompt with tool definitions if available
        enhanced_prompt = prompt
        if tools_enabled and self.mcp_bridge:
            tools_prompt = self._format_tools_for_qwen()
            print(f"DEBUG: Tools available, enhanced prompt with {len(tools_prompt)} chars")
            print(f"DEBUG: Tools prompt preview: {tools_prompt[:200]}...")
            logger.info(f"🔧 TOOLS AVAILABLE: Enhanced prompt with {len(tools_prompt)} character tool definitions")
            logger.info(f"🔧 TOOLS PROMPT: {tools_prompt[:200]}...")
            enhanced_prompt = f"{tools_prompt}\n\nUser request: {prompt}\n\nResponse:"
        else:
            print(f"DEBUG: NO TOOLS - tools_enabled={tools_enabled}, mcp_bridge={self.mcp_bridge is not None}")
            logger.warning("🚨 NO TOOLS AVAILABLE: mcp_bridge not configured or tools_enabled=False")

        # Generate response using existing method with refined stop tokens
        stop_tokens = ["```\n\nassistant", "assistant:", "Human:"]
        result = self.generate_response(
            enhanced_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_tokens=stop_tokens
        )

        if not result["success"]:
            return {
                "success": False,
                "error": result["error"],
                "type": "error"
            }

        response_text = result["response"]
        print(f"DEBUG: Model generated {len(response_text)} characters")
        print(f"DEBUG: Model output: {response_text}")

        # Process output for tool calls if bridge is available
        if tools_enabled and self.mcp_bridge:
            print(f"DEBUG: Processing model output for tool calls")
            logger.info(f"🔍 PROCESSING MODEL OUTPUT for tool calls: {len(response_text)} characters")
            logger.info(f"🔍 MODEL OUTPUT PREVIEW: {response_text}...")
            processed = await self.mcp_bridge.process_model_output(response_text)

            if processed.get("type") == "tool_calls":
                logger.info(f"✅ TOOL CALLS DETECTED: {len(processed.get('tool_calls', []))} calls")
                for i, call in enumerate(processed.get('tool_calls', [])):
                    logger.info(f"🔧 TOOL CALL {i+1}: {call.get('tool_name', 'unknown')} with args: {call.get('arguments', {})}")
            else:
                logger.warning(f"⚠️ NO TOOL CALLS DETECTED: Response type is {processed.get('type')}")

            processed["success"] = True
            processed["usage"] = result.get("usage", {})
            processed["response_time"] = result.get("response_time", 0.0)
            return processed

        # Return as text response
        return {
            "success": True,
            "type": "text",
            "content": response_text,
            "usage": result.get("usage", {}),
            "response_time": result.get("response_time", 0.0)
        }
