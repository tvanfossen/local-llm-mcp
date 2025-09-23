"""MCP Bridge module for local model tool calling"""

from .bridge import MCPBridge
from .formatter import ToolPromptFormatter

__all__ = ['MCPBridge', 'ToolPromptFormatter']