"""Code Generation Tool

This tool is responsible for generating Python code from JSON metadata files
using Jinja2 templates. It provides a clean separation from file system
operations and focuses solely on code generation concerns.
"""

from .code_generation import code_generation_tool

__all__ = ["code_generation_tool"]