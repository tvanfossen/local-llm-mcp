"""MCP Tools Executor - Execute MCP Tool Calls

Responsibilities:
- Execute MCP tool calls including agent operations
- Handle tool validation and dispatch
- Provide tool definitions and metadata
- Coordinate with git tools and agent registry
"""

import logging
from typing import Any

from src.mcp.tools.agent.chat.chat import chat_with_agent

# Phase 1: Agent Tools
from src.mcp.tools.agent.create.create import create_agent
from src.mcp.tools.agent.delete.delete import delete_agent
from src.mcp.tools.agent.info.info import get_agent_info
from src.mcp.tools.agent.list.list import list_agents
from src.mcp.tools.agent.update.update import update_agent
from src.mcp.tools.file.delete.delete import delete_directory, delete_file, delete_multiple_files
from src.mcp.tools.file.list.list import find_files, list_files

# Phase 2: File Tools
from src.mcp.tools.file.read.read import get_file_info, read_file
from src.mcp.tools.file.update.update import insert_lines, replace_text, update_file_lines
from src.mcp.tools.file.write.write import append_to_file, create_file, write_file
from src.mcp.tools.git_operations.git_operations import git_tool
from src.mcp.tools.local_model.local_model import local_model_tool

# Phase 5: Self-Improvement Tools
from src.mcp.tools.improvement.analyze.analyze import analyze_code_quality, analyze_project_health
from src.mcp.tools.improvement.compliance.compliance import (
    check_project_compliance,
    ensure_compliance,
    fix_compliance_issues,
)
from src.mcp.tools.improvement.document.document import add_documentation, generate_module_docs, generate_type_hints
from src.mcp.tools.improvement.orchestrate.orchestrate import (
    auto_improve_file,
    create_improvement_plan,
    execute_improvement_plan,
)
from src.mcp.tools.improvement.refactor.refactor import (
    apply_simple_refactoring,
    generate_refactoring_plan,
    suggest_refactoring,
)
from src.mcp.tools.improvement.testing.testing import analyze_test_coverage, create_test_suite, generate_tests
from src.mcp.tools.system.all_validation.all_validation import run_all_validations

# Phase 3: Template Tools
from src.mcp.tools.template.generate.generate import (
    generate_from_template,
    generate_function_scaffold,
    render_template_preview,
)
from src.mcp.tools.template.list.list import get_template_details, list_templates
from src.mcp.tools.template.validate.validate import validate_template, validate_template_output
from src.mcp.tools.testing.precommit.precommit import run_pre_commit
from src.mcp.tools.testing.run_tests.run_tests import run_tests
from src.mcp.tools.validation.agent_file.agent_file import validate_agent_file
from src.mcp.tools.validation.file_length.file_length import validate_file_length

logger = logging.getLogger(__name__)


class MCPToolExecutor:
    """Executes MCP tool calls with validation"""

    def __init__(self, agent_registry, llm_manager):
        self.agent_registry = agent_registry
        self.llm_manager = llm_manager
        self.available_tools = self._build_tool_registry()

    def _build_tool_registry(self) -> dict[str, Any]:
        """Build registry of available tools"""
        return {
            # Phase 1: Agent Management Tools (New MCP Tools)
            "create_agent": {
                "name": "create_agent",
                "description": "Create a new agent to manage a file",
                "function": create_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Agent name"},
                        "description": {"type": "string", "description": "Agent description"},
                        "system_prompt": {"type": "string", "description": "System prompt for the agent"},
                        "managed_file": {"type": "string", "description": "File the agent will manage"},
                        "initial_context": {"type": "string", "description": "Initial context (optional)"},
                    },
                    "required": ["name", "description", "system_prompt", "managed_file"],
                },
            },
            "list_agents": {
                "name": "list_agents",
                "description": "List all active agents",
                "function": list_agents,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "get_agent_info": {
                "name": "get_agent_info",
                "description": "Get detailed information about an agent",
                "function": get_agent_info,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID"}},
                    "required": ["agent_id"],
                },
            },
            "update_agent": {
                "name": "update_agent",
                "description": "Update agent properties and configuration",
                "function": update_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID"},
                        "name": {"type": "string", "description": "New agent name"},
                        "description": {"type": "string", "description": "New agent description"},
                        "system_prompt": {"type": "string", "description": "New system prompt"},
                        "add_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to add to management",
                        },
                        "remove_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to remove from management",
                        },
                    },
                    "required": ["agent_id"],
                },
            },
            "delete_agent": {
                "name": "delete_agent",
                "description": "Delete an agent",
                "function": delete_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID to delete"},
                        "force": {"type": "boolean", "description": "Force deletion for active agents"},
                    },
                    "required": ["agent_id"],
                },
            },
            "chat_with_agent": {
                "name": "chat_with_agent",
                "description": "Send a message to an agent for processing",
                "function": chat_with_agent,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID"},
                        "message": {"type": "string", "description": "Message to send"},
                        "task_type": {
                            "type": "string",
                            "enum": ["update", "create", "analyze", "refactor", "debug", "document", "test"],
                            "description": "Type of task",
                        },
                    },
                    "required": ["agent_id", "message"],
                },
            },
            # Phase 2: File Operation Tools
            "read_file": {
                "name": "read_file",
                "description": "Read file contents with workspace safety checks",
                "function": read_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to read"},
                        "start_line": {"type": "integer", "description": "Start line number (1-based)"},
                        "end_line": {"type": "integer", "description": "End line number"},
                        "show_line_numbers": {"type": "boolean", "description": "Show line numbers", "default": True},
                    },
                    "required": ["file_path"],
                },
            },
            "get_file_info": {
                "name": "get_file_info",
                "description": "Get file information without reading contents",
                "function": get_file_info,
                "inputSchema": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string", "description": "File path"}},
                    "required": ["file_path"],
                },
            },
            "write_file": {
                "name": "write_file",
                "description": "Write content to file with workspace safety checks",
                "function": write_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                        "overwrite": {"type": "boolean", "description": "Allow overwriting existing files"},
                        "create_dirs": {"type": "boolean", "description": "Create parent directories", "default": True},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path", "content"],
                },
            },
            "append_to_file": {
                "name": "append_to_file",
                "description": "Append content to an existing file",
                "function": append_to_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Content to append"},
                        "newline": {"type": "boolean", "description": "Add newline", "default": True},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path", "content"],
                },
            },
            "create_file": {
                "name": "create_file",
                "description": "Create a new file with optional template",
                "function": create_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "content": {"type": "string", "description": "Initial content", "default": ""},
                        "template": {"type": "string", "description": "Template to apply"},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path"],
                },
            },
            "update_file_lines": {
                "name": "update_file_lines",
                "description": "Update specific lines in a file",
                "function": update_file_lines,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "start_line": {"type": "integer", "description": "Start line number (1-based)"},
                        "end_line": {"type": "integer", "description": "End line number"},
                        "new_content": {"type": "string", "description": "New content"},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path", "start_line", "new_content"],
                },
            },
            "replace_text": {
                "name": "replace_text",
                "description": "Replace text patterns in a file",
                "function": replace_text,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "search_text": {"type": "string", "description": "Text to search for"},
                        "replace_text": {"type": "string", "description": "Replacement text"},
                        "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
                        "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": True},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path", "search_text", "replace_text"],
                },
            },
            "insert_lines": {
                "name": "insert_lines",
                "description": "Insert lines at a specific position in a file",
                "function": insert_lines,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "line_number": {"type": "integer", "description": "Line number to insert at (1-based)"},
                        "content": {"type": "string", "description": "Content to insert"},
                        "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                    },
                    "required": ["file_path", "line_number", "content"],
                },
            },
            "list_files": {
                "name": "list_files",
                "description": "List files and directories with filtering options",
                "function": list_files,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to list", "default": "."},
                        "pattern": {"type": "string", "description": "File name pattern"},
                        "include_hidden": {"type": "boolean", "description": "Include hidden files", "default": False},
                        "recursive": {"type": "boolean", "description": "Recursive listing", "default": False},
                        "max_depth": {"type": "integer", "description": "Maximum recursion depth", "default": 3},
                        "show_details": {
                            "type": "boolean",
                            "description": "Show detailed information",
                            "default": True,
                        },
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by file extensions",
                        },
                    },
                    "required": [],
                },
            },
            "find_files": {
                "name": "find_files",
                "description": "Find files by name or pattern",
                "function": find_files,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "search_term": {"type": "string", "description": "Search term or pattern"},
                        "directory_path": {"type": "string", "description": "Directory to search in", "default": "."},
                        "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": False},
                        "max_results": {"type": "integer", "description": "Maximum results", "default": 100},
                    },
                    "required": ["search_term"],
                },
            },
            "delete_file": {
                "name": "delete_file",
                "description": "Delete a file with safety checks",
                "function": delete_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to delete"},
                        "force": {
                            "type": "boolean",
                            "description": "Force deletion of important files",
                            "default": False,
                        },
                    },
                    "required": ["file_path"],
                },
            },
            "delete_multiple_files": {
                "name": "delete_multiple_files",
                "description": "Delete multiple files",
                "function": delete_multiple_files,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Files to delete"},
                        "force": {"type": "boolean", "description": "Force deletion", "default": False},
                        "continue_on_error": {"type": "boolean", "description": "Continue on errors", "default": True},
                    },
                    "required": ["file_paths"],
                },
            },
            "delete_directory": {
                "name": "delete_directory",
                "description": "Delete a directory and its contents",
                "function": delete_directory,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to delete"},
                        "force": {"type": "boolean", "description": "Force deletion", "default": False},
                        "recursive": {"type": "boolean", "description": "Allow recursive deletion", "default": False},
                    },
                    "required": ["directory_path"],
                },
            },
            # Phase 3: Template Tools
            "generate_from_template": {
                "name": "generate_from_template",
                "description": "Generate code from a template",
                "function": generate_from_template,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_name": {"type": "string", "description": "Template name"},
                        "output_path": {"type": "string", "description": "Output file path"},
                        "variables": {"type": "object", "description": "Template variables"},
                        "template_type": {"type": "string", "description": "Template type", "default": "function"},
                        "overwrite": {"type": "boolean", "description": "Overwrite existing files", "default": False},
                    },
                    "required": ["template_name", "output_path"],
                },
            },
            "generate_function_scaffold": {
                "name": "generate_function_scaffold",
                "description": "Generate complete function scaffold with multiple files",
                "function": generate_function_scaffold,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_path": {
                            "type": "string",
                            "description": "Function path (e.g., src/domain/category/function)",
                        },
                        "variables": {"type": "object", "description": "Template variables"},
                    },
                    "required": ["function_path"],
                },
            },
            "render_template_preview": {
                "name": "render_template_preview",
                "description": "Preview template rendering without saving",
                "function": render_template_preview,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_name": {"type": "string", "description": "Template name"},
                        "variables": {"type": "object", "description": "Template variables"},
                        "template_type": {"type": "string", "description": "Template type", "default": "function"},
                        "max_lines": {"type": "integer", "description": "Maximum lines to preview", "default": 50},
                    },
                    "required": ["template_name"],
                },
            },
            "list_templates": {
                "name": "list_templates",
                "description": "List available templates",
                "function": list_templates,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_type": {"type": "string", "description": "Filter by template type"},
                        "show_details": {
                            "type": "boolean",
                            "description": "Show detailed information",
                            "default": True,
                        },
                        "include_content": {
                            "type": "boolean",
                            "description": "Include template content",
                            "default": False,
                        },
                    },
                    "required": [],
                },
            },
            "get_template_details": {
                "name": "get_template_details",
                "description": "Get detailed information about a template",
                "function": get_template_details,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_name": {"type": "string", "description": "Template name"},
                        "include_content": {
                            "type": "boolean",
                            "description": "Include template content",
                            "default": False,
                        },
                    },
                    "required": ["template_name"],
                },
            },
            "validate_template": {
                "name": "validate_template",
                "description": "Validate template syntax and structure",
                "function": validate_template,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_name": {"type": "string", "description": "Template name"},
                        "test_variables": {"type": "object", "description": "Variables for testing"},
                        "check_syntax_only": {"type": "boolean", "description": "Only check syntax", "default": False},
                    },
                    "required": ["template_name"],
                },
            },
            "validate_template_output": {
                "name": "validate_template_output",
                "description": "Validate template output against schema/rules",
                "function": validate_template_output,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_name": {"type": "string", "description": "Template name"},
                        "variables": {"type": "object", "description": "Template variables"},
                        "schema_file": {"type": "string", "description": "Schema file for validation"},
                        "validation_rules": {"type": "array", "description": "Custom validation rules"},
                    },
                    "required": ["template_name"],
                },
            },
            # Phase 5: Self-Improvement Tools
            "analyze_code_quality": {
                "name": "analyze_code_quality",
                "description": "Analyze code quality for files with comprehensive metrics",
                "function": analyze_code_quality,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File or directory path to analyze"},
                        "detailed": {"type": "boolean", "description": "Show detailed analysis", "default": True},
                        "max_files": {"type": "integer", "description": "Maximum files to analyze", "default": 50},
                        "file_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File patterns to match",
                            "default": ["*.py", "*.js", "*.ts", "*.md"],
                        },
                    },
                    "required": ["file_path"],
                },
            },
            "analyze_project_health": {
                "name": "analyze_project_health",
                "description": "Analyze overall project health metrics and calculate health score",
                "function": analyze_project_health,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "suggest_refactoring": {
                "name": "suggest_refactoring",
                "description": "Suggest refactoring opportunities for better code structure",
                "function": suggest_refactoring,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to analyze"},
                        "priority_filter": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Filter by priority",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            "generate_refactoring_plan": {
                "name": "generate_refactoring_plan",
                "description": "Generate comprehensive refactoring plan for multiple files",
                "function": generate_refactoring_plan,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to analyze", "default": "."},
                        "file_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File patterns",
                            "default": ["*.py"],
                        },
                        "max_files": {"type": "integer", "description": "Maximum files to analyze", "default": 20},
                    },
                    "required": [],
                },
            },
            "apply_simple_refactoring": {
                "name": "apply_simple_refactoring",
                "description": "Apply simple, safe refactoring automatically",
                "function": apply_simple_refactoring,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to refactor"},
                        "refactoring_type": {
                            "type": "string",
                            "enum": ["remove_unused_import", "extract_constant", "format_code"],
                            "description": "Type of refactoring to apply",
                        },
                    },
                    "required": ["file_path", "refactoring_type"],
                },
            },
            "add_documentation": {
                "name": "add_documentation",
                "description": "Add missing documentation and docstrings to files",
                "function": add_documentation,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to document"},
                        "style": {
                            "type": "string",
                            "enum": ["google", "numpy", "sphinx"],
                            "description": "Docstring style",
                            "default": "google",
                        },
                        "dry_run": {"type": "boolean", "description": "Dry run mode", "default": True},
                    },
                    "required": ["file_path"],
                },
            },
            "generate_type_hints": {
                "name": "generate_type_hints",
                "description": "Generate missing type hints for Python functions",
                "function": generate_type_hints,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Python file path"},
                    },
                    "required": ["file_path"],
                },
            },
            "generate_module_docs": {
                "name": "generate_module_docs",
                "description": "Generate module-level documentation",
                "function": generate_module_docs,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                    },
                    "required": ["file_path"],
                },
            },
            "ensure_compliance": {
                "name": "ensure_compliance",
                "description": "Ensure file meets project compliance standards",
                "function": ensure_compliance,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to check"},
                        "auto_fix": {"type": "boolean", "description": "Apply automatic fixes", "default": False},
                        "report_only": {"type": "boolean", "description": "Report only mode", "default": True},
                    },
                    "required": ["file_path"],
                },
            },
            "check_project_compliance": {
                "name": "check_project_compliance",
                "description": "Check compliance across multiple files in project",
                "function": check_project_compliance,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to check", "default": "."},
                        "file_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File patterns",
                            "default": ["*.py"],
                        },
                        "max_files": {"type": "integer", "description": "Maximum files to check", "default": 50},
                    },
                    "required": [],
                },
            },
            "fix_compliance_issues": {
                "name": "fix_compliance_issues",
                "description": "Automatically fix simple compliance issues",
                "function": fix_compliance_issues,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "issue_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of issues to fix",
                            "default": ["trailing_whitespace", "excessive_blank_lines"],
                        },
                    },
                    "required": ["file_path"],
                },
            },
            "generate_tests": {
                "name": "generate_tests",
                "description": "Generate comprehensive tests for a file",
                "function": generate_tests,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_file": {"type": "string", "description": "Source file to test"},
                        "test_file": {"type": "string", "description": "Test file path (optional)"},
                        "generate_code": {"type": "boolean", "description": "Generate test code", "default": False},
                        "test_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of tests",
                            "default": ["unit", "integration", "edge_cases"],
                        },
                    },
                    "required": ["source_file"],
                },
            },
            "analyze_test_coverage": {
                "name": "analyze_test_coverage",
                "description": "Analyze test coverage for project or directory",
                "function": analyze_test_coverage,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to analyze", "default": "."},
                        "coverage_threshold": {
                            "type": "number",
                            "description": "Coverage threshold percentage",
                            "default": 80.0,
                        },
                    },
                    "required": [],
                },
            },
            "create_test_suite": {
                "name": "create_test_suite",
                "description": "Create a complete test suite for a file",
                "function": create_test_suite,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_file": {"type": "string", "description": "Source file"},
                    },
                    "required": ["source_file"],
                },
            },
            "auto_improve_file": {
                "name": "auto_improve_file",
                "description": "Orchestrate comprehensive improvement of a single file",
                "function": auto_improve_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to improve"},
                        "dry_run": {"type": "boolean", "description": "Dry run mode", "default": True},
                        "improvement_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Areas to improve",
                            "default": ["all"],
                        },
                        "priority_threshold": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Priority threshold",
                            "default": "medium",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            "create_improvement_plan": {
                "name": "create_improvement_plan",
                "description": "Create comprehensive improvement plan for project",
                "function": create_improvement_plan,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory path", "default": "."},
                        "file_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File patterns",
                            "default": ["*.py"],
                        },
                        "max_files": {"type": "integer", "description": "Maximum files to analyze", "default": 20},
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Focus areas",
                            "default": ["quality", "compliance", "testing"],
                        },
                    },
                    "required": [],
                },
            },
            "execute_improvement_plan": {
                "name": "execute_improvement_plan",
                "description": "Execute a comprehensive improvement plan",
                "function": execute_improvement_plan,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Target file or directory"},
                        "plan_type": {
                            "type": "string",
                            "enum": ["conservative", "aggressive", "comprehensive"],
                            "description": "Plan type",
                            "default": "conservative",
                        },
                        "max_changes": {"type": "integer", "description": "Maximum changes", "default": 10},
                        "backup": {"type": "boolean", "description": "Create backup", "default": True},
                    },
                    "required": ["target"],
                },
            },
            # System Tools
            "system_status": {
                "name": "system_status",
                "description": "Get system and model status",
                "function": self._system_status,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            # Git Tools
            "git_operations": {
                "name": "git_operations",
                "description": "Unified git operations (status, diff, commit, log, branch, stash, remote)",
                "function": git_tool,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Git operation to perform",
                            "enum": ["status", "diff", "commit", "log", "branch", "stash", "remote"]
                        },
                        "message": {"type": "string", "description": "Commit message (for commit operation)"},
                        "add_all": {"type": "boolean", "description": "Add all files (for commit)", "default": False},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "Files to commit"},
                        "staged": {"type": "boolean", "description": "Show staged changes (for diff)", "default": False},
                        "file_path": {"type": "string", "description": "Specific file path"},
                        "limit": {"type": "integer", "description": "Number of log entries (for log)", "default": 10},
                        "action": {"type": "string", "description": "Action for branch/stash operations"},
                        "name": {"type": "string", "description": "Branch or stash name"},
                        "short": {"type": "boolean", "description": "Short status format", "default": False}
                    },
                    "required": ["operation"]
                }
            },
            # Testing & Validation Tools
            "run_tests": {
                "name": "run_tests",
                "description": "Run pytest with optional coverage",
                "function": run_tests,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test_path": {"type": "string", "description": "Path to tests (default: src/)"},
                        "coverage": {"type": "boolean", "description": "Generate coverage report (default: true)"},
                        "verbose": {"type": "boolean", "description": "Verbose output (default: false)"},
                    },
                    "required": [],
                },
            },
            "run_pre_commit": {
                "name": "run_pre_commit",
                "description": "Run pre-commit hooks for validation",
                "function": run_pre_commit,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hook": {"type": "string", "description": "Specific hook to run (optional)"},
                        "all_files": {"type": "boolean", "description": "Run on all files (default: false)"},
                    },
                    "required": [],
                },
            },
            "validate_file_length": {
                "name": "validate_file_length",
                "description": "Validate file line counts against limits",
                "function": validate_file_length,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to validate",
                        },
                        "max_lines": {"type": "integer", "description": "Maximum lines allowed (default: 300)"},
                    },
                    "required": ["file_paths"],
                },
            },
            "validate_agent_file": {
                "name": "validate_agent_file",
                "description": "Validate agent's managed file meets requirements",
                "function": validate_agent_file,
                "inputSchema": {
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent ID to validate"}},
                    "required": ["agent_id"],
                },
            },
            # Unified validation tool
            "run_all_validations": {
                "name": "run_all_validations",
                "description": "Run all tests, pre-commit hooks, and validations",
                "function": run_all_validations,
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        }

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools with schemas"""
        return [
            {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": tool_info.get("inputSchema", {"type": "object", "properties": {}, "required": []}),
            }
            for tool_info in self.available_tools.values()
        ]

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], user_context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Execute a tool with given arguments with comprehensive logging and error handling"""
        import asyncio
        import time
        import traceback

        start_time = time.time()

        # Enhanced logging for tool execution
        arg_keys = list(arguments.keys()) if arguments else []
        context_keys = list(user_context.keys()) if user_context else []
        logger.info(f"🚀 Starting tool execution: {tool_name} | Args: {arg_keys} | Context: {context_keys}")

        # Log argument details in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Tool: {tool_name} - Full arguments: {arguments}")
            if user_context:
                logger.debug(f"Tool: {tool_name} - User context: {user_context}")

        # Validate tool exists
        if tool_name not in self.available_tools:
            available_tools = sorted(self.available_tools.keys())
            error_msg = f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}"
            logger.error(f"🚫 Tool validation failed: {error_msg}")
            return {
                "content": [{"type": "text", "text": f"❌ **Tool Not Found:** {error_msg}"}],
                "isError": True,
            }

        try:
            tool_info = self.available_tools[tool_name]
            tool_function = tool_info["function"]

            logger.debug(f"🔧 Tool info loaded: {tool_name} -> {tool_function.__name__}")

            # Enhanced argument validation with detailed logging
            if "inputSchema" in tool_info:
                validation_warnings = self._validate_arguments(arguments, tool_info["inputSchema"])
                if validation_warnings:
                    logger.warning(f"⚠️ Argument validation issues for {tool_name}: {'; '.join(validation_warnings)}")
                    # Log each warning separately for better tracking
                    for warning in validation_warnings:
                        logger.debug(f"Validation warning: {warning}")
                else:
                    logger.debug(f"✅ Argument validation passed for {tool_name}")

            # Add user context to arguments if provided
            if user_context:
                arguments = {**arguments, "_user_context": user_context}
                logger.debug(f"📎 Added user context to arguments for {tool_name}")

            # Enhanced async/sync detection and execution
            if asyncio.iscoroutinefunction(tool_function):
                logger.debug(f"⚡ Executing async tool: {tool_name}")
                try:
                    # Add timeout for async operations (10 minutes)
                    result = await asyncio.wait_for(tool_function(arguments), timeout=600.0)
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Async tool {tool_name} timed out after 10 minutes")
                    raise
            else:
                logger.debug(f"🔄 Executing sync tool: {tool_name}")
                # Wrap sync function in async executor with timeout
                loop = asyncio.get_event_loop()
                try:
                    # Add timeout for sync operations (5 minutes)
                    result = await asyncio.wait_for(loop.run_in_executor(None, tool_function, arguments), timeout=300.0)
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Sync tool {tool_name} timed out after 5 minutes")
                    raise

            logger.debug(f"🎯 Tool {tool_name} execution completed, validating response format")

            # Enhanced response validation
            if not self._is_valid_mcp_response(result):
                logger.warning(f"📋 Tool {tool_name} returned invalid MCP response format, normalizing")
                logger.debug(f"Invalid response structure: {type(result)} - {str(result)[:200]}...")
                result = self._normalize_mcp_response(result)
            else:
                logger.debug(f"✅ Valid MCP response format for {tool_name}")

            execution_time = time.time() - start_time

            # Log success with performance metrics
            success_msg = f"✅ Tool {tool_name} completed successfully in {execution_time:.3f}s"
            if execution_time > 5.0:
                logger.warning(f"🐌 {success_msg} (slow execution)")
            else:
                logger.info(success_msg)

            # Log response summary in debug mode
            if logger.isEnabledFor(logging.DEBUG):
                content_count = len(result.get("content", []))
                is_error = result.get("isError", False)
                logger.debug(f"Response summary: {content_count} content items, error={is_error}")

            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            timeout_msg = f"Tool '{tool_name}' execution timed out after {execution_time:.3f}s"
            logger.error(f"⏰ Timeout: {timeout_msg}")
            return {
                "content": [{"type": "text", "text": f"⏰ **Execution Timeout:** {timeout_msg}"}],
                "isError": True,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            error_type = type(e).__name__
            error_msg = str(e)

            # Enhanced error logging with context
            logger.error(
                f"💥 Tool execution failed: {tool_name} | "
                f"Error: {error_type}: {error_msg} | "
                f"Time: {execution_time:.3f}s",
                exc_info=True,
            )

            # Create detailed error response
            detailed_error = f"❌ **{error_type}:** {error_msg}"

            # Add context information in debug mode
            if logger.isEnabledFor(logging.DEBUG):
                detailed_error += f"\n\n**Tool:** {tool_name}"
                detailed_error += f"\n**Arguments:** {list(arguments.keys()) if arguments else 'None'}"
                detailed_error += f"\n**Execution Time:** {execution_time:.3f}s"
                detailed_error += f"\n\n**Traceback:**\n```\n{traceback.format_exc()}\n```"
            else:
                # Provide helpful hint in production
                detailed_error += "\n\n*Enable debug logging for detailed traceback*"

            return {
                "content": [{"type": "text", "text": detailed_error}],
                "isError": True,
            }

    def _validate_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> list[str]:
        """Validate arguments against JSON schema"""
        warnings = []

        try:
            # Check required fields
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in arguments:
                    warnings.append(f"Missing required field: {field}")
                elif arguments[field] is None or arguments[field] == "":
                    warnings.append(f"Required field '{field}' is empty")

            # Check field types for provided arguments
            properties = schema.get("properties", {})
            for field, value in arguments.items():
                if field in properties:
                    expected_type = properties[field].get("type")
                    if expected_type and not self._check_type(value, expected_type):
                        warnings.append(f"Field '{field}' should be {expected_type}, got {type(value).__name__}")

        except Exception as e:
            warnings.append(f"Schema validation error: {str(e)}")

        return warnings

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON schema type"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        return True

    def _is_valid_mcp_response(self, response: Any) -> bool:
        """Check if response follows MCP format"""
        if not isinstance(response, dict):
            return False

        required_fields = ["content", "isError"]
        for field in required_fields:
            if field not in response:
                return False

        # Check content format
        content = response.get("content")
        if not isinstance(content, list):
            return False

        for item in content:
            if not isinstance(item, dict) or "type" not in item or "text" not in item:
                return False

        # Check isError format
        if not isinstance(response.get("isError"), bool):
            return False

        return True

    def _normalize_mcp_response(self, response: Any) -> dict[str, Any]:
        """Convert response to valid MCP format if possible"""
        if isinstance(response, dict) and self._is_valid_mcp_response(response):
            return response

        # Try to convert various response formats
        if isinstance(response, str):
            return {
                "content": [{"type": "text", "text": response}],
                "isError": False,
            }
        elif isinstance(response, dict):
            # Try to extract meaningful content
            text_content = str(response)
            if len(text_content) > 1000:
                text_content = text_content[:1000] + "... (truncated)"

            return {
                "content": [{"type": "text", "text": text_content}],
                "isError": response.get("error", False),
            }
        else:
            return {
                "content": [{"type": "text", "text": str(response)}],
                "isError": False,
            }

    # Legacy system status method (kept for compatibility)
    async def get_agent_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get agent's managed file content (legacy method for compatibility)"""
        # Delegate to new read_file tool
        try:
            agent_id = args.get("agent_id")
            agent = self.agent_registry.get_agent(agent_id)

            if not agent or not agent.managed_files:
                return {
                    "content": [{"type": "text", "text": "📭 **No Files:** Agent has no managed files"}],
                    "isError": False,
                }

            # Get first managed file and use read_file tool
            file_path = list(agent.managed_files)[0]
            return await read_file({"file_path": file_path, "show_line_numbers": True})

        except Exception as e:
            logger.error(f"Failed to get agent file: {e}")
            return {"content": [{"type": "text", "text": f"❌ **Get File Failed:** {str(e)}"}], "isError": True}

    async def _system_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get system status"""
        try:
            # Get model info
            model_info = self.llm_manager.get_model_info()

            # Get agent stats
            registry_stats = self.agent_registry.get_registry_stats()

            status = "📊 **System Status Report:**\n\n"

            # Model status
            model_status = "✅ Loaded" if model_info["model_loaded"] else "❌ Not Loaded"
            status += f"**🤖 Model Status:** {model_status}\n"
            if model_info.get("model_path"):
                status += f"**Model Path:** `{model_info['model_path']}`\n"

            # Configuration
            if model_info.get("configuration"):
                config = model_info["configuration"]
                status += f"**Context Size:** {config.get('context_size', 'N/A')} tokens\n"
                status += f"**Batch Size:** {config.get('batch_size', 'N/A')}\n"

            # Agent statistics
            status += "\n**👥 Agent Statistics:**\n"
            status += f"**Total Agents:** {registry_stats['total_agents']}\n"
            status += f"**Managed Files:** {registry_stats['managed_files']}\n"
            status += f"**Total Interactions:** {registry_stats['total_interactions']}\n"
            status += f"**Average Success Rate:** {registry_stats['average_success_rate']:.2%}\n"

            if registry_stats.get("most_active_agent"):
                status += f"**Most Active Agent:** {registry_stats['most_active_agent']}\n"

            return {"content": [{"type": "text", "text": status}], "isError": False}
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {"content": [{"type": "text", "text": f"❌ **System Status Failed:** {str(e)}"}], "isError": True}
