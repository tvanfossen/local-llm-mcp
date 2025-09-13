"""Local Model Tool - Interface for Local LLM Operations

Path: src/mcp/tools/local_model/local_model.py
Responsibilities:
- Interface with local language model through LLM manager
- Handle inference requests
- Provide model status and information
- Manage model lifecycle operations
"""

import logging
from typing import Any, Optional

from src.core.utils.utils import create_mcp_response, handle_exception

logger = logging.getLogger(__name__)


class LocalModelTool:
    """Local model operations handler"""
    
    def __init__(self, llm_manager=None):
        """Initialize with LLM manager reference"""
        self.llm_manager = llm_manager
        
    def get_model_status(self) -> dict[str, Any]:
        """Get current model status"""
        if not self.llm_manager:
            return {"status": "manager_unavailable", "loaded": False}
            
        info = self.llm_manager.get_model_info()
        health = self.llm_manager.health_check()
        performance = self.llm_manager.get_performance_summary()
        
        return {
            "status": health["status"],
            "loaded": info["model_loaded"],
            "model_path": info["model_path"],
            "configuration": info["configuration"],
            "performance": performance
        }
    
    def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> dict[str, Any]:
        """Generate response from local model"""
        if not self.llm_manager:
            return {"success": False, "error": "LLM manager not available"}
            
        if not self.llm_manager.model_loaded:
            return {
                "success": False, 
                "error": "Model not loaded. Use load_model operation first.",
                "mock_response": f"Mock response to: {prompt[:100]}..."
            }
        
        try:
            # Update performance stats
            self.llm_manager.performance_stats["total_requests"] += 1
            
            # Generate response using loaded model
            response = self.llm_manager.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                echo=False
            )
            
            self.llm_manager.performance_stats["successful_requests"] += 1
            
            return {
                "success": True,
                "response": response["choices"][0]["text"],
                "usage": {
                    "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": response.get("usage", {}).get("total_tokens", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return {"success": False, "error": str(e)}
    
    def load_model(self) -> dict[str, Any]:
        """Load the language model"""
        if not self.llm_manager:
            return {"success": False, "error": "LLM manager not available"}
            
        success, message = self.llm_manager.load_model()
        return {
            "success": success,
            "message": message or "Model loaded successfully",
            "mock_mode": not self.llm_manager.model_loaded
        }
    
    def unload_model(self) -> dict[str, Any]:
        """Unload the language model"""
        if not self.llm_manager:
            return {"success": False, "error": "LLM manager not available"}
            
        try:
            self.llm_manager.unload_model()
            return {"success": True, "message": "Model unloaded successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global tool instance (will be initialized by system)
_local_model_tool: Optional[LocalModelTool] = None


def initialize_local_model_tool(llm_manager) -> None:
    """Initialize the local model tool with LLM manager"""
    global _local_model_tool
    _local_model_tool = LocalModelTool(llm_manager)


async def local_model_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Local model MCP tool interface
    
    Operations:
    - status: Get model status and information
    - generate: Generate response from prompt
    - load: Load the language model
    - unload: Unload the language model
    """
    operation = args.get("operation")
    
    if not operation:
        return create_mcp_response(
            False, "Operation parameter required. Available: status, generate, load, unload"
        )
    
    if not _local_model_tool:
        return create_mcp_response(
            False, "Local model tool not initialized. Contact system administrator."
        )
    
    try:
        if operation == "status":
            result = _local_model_tool.get_model_status()
            status_text = f"**Model Status: {result['status']}**\n"
            status_text += f"Loaded: {result['loaded']}\n"
            if result['model_path']:
                status_text += f"Path: {result['model_path']}\n"
            status_text += f"Performance: {result['performance']['total_requests']} total requests, "
            status_text += f"{result['performance']['successful_requests']} successful"
            return create_mcp_response(True, status_text)
            
        elif operation == "generate":
            prompt = args.get("prompt", "")
            if not prompt:
                return create_mcp_response(False, "Prompt parameter required for generate operation")
                
            max_tokens = args.get("max_tokens", 512)
            temperature = args.get("temperature", 0.7)
            
            result = _local_model_tool.generate_response(prompt, max_tokens, temperature)
            
            if result["success"]:
                response_text = f"**Generated Response:**\n\n{result['response']}\n\n"
                response_text += f"**Usage:** {result['usage']['total_tokens']} tokens"
                return create_mcp_response(True, response_text)
            else:
                error_msg = result["error"]
                if "mock_response" in result:
                    error_msg += f"\n\n**Mock Response:** {result['mock_response']}"
                return create_mcp_response(False, error_msg)
                
        elif operation == "load":
            result = _local_model_tool.load_model()
            
            if result["success"]:
                message = result["message"]
                if result.get("mock_mode"):
                    message = f"   {message}"
                else:
                    message = f" {message}"
                return create_mcp_response(True, message)
            else:
                return create_mcp_response(False, result["error"])
                
        elif operation == "unload":
            result = _local_model_tool.unload_model()
            
            if result["success"]:
                return create_mcp_response(True, f" {result['message']}")
            else:
                return create_mcp_response(False, result["error"])
                
        else:
            return create_mcp_response(False, f"Unknown operation '{operation}'")
            
    except Exception as e:
        return handle_exception(e, "Local Model Tool")