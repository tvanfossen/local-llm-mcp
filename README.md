# Local LLM MCP Server

A **Model Context Protocol (MCP) server** that provides Claude Code with specialized agents powered by local CUDA-accelerated LLMs. Each agent owns exactly one file and uses structured **JSON-based tool calling** for autonomous code generation.


## Overview

This system enables Claude Code to orchestrate local agents that generate code using a local LLM (Qwen2.5-7B-Instruct). The architecture supports async task queueing, JSON-structured generation, and jinja2 template rendering for clean, executable Python code.

### Key Features

- 🤖 **Agent-based architecture**: One agent per file, persistent per repository
- ⚡ **Async task queueing**: Non-blocking tool calls with independent processing
- 📝 **JSON-structured generation**: Metadata-driven code generation with jinja2 templates
- 🚀 **CUDA acceleration**: Optimized for RTX 1080ti with 15-25 tokens/second
- 🔗 **MCP integration**: Seamless Claude Code integration via HTTP/MCP bridge
- ✅ **100% Success Rate**: Working on tested examples with full implementations

## Architecture

```
Claude Code → HTTP/MCP → Agent Registry → Individual Agents → Local LLM → Tool Execution
```


## Quick Start

### Prerequisites

- Ubuntu 22.04 with NVIDIA Driver 575+ and CUDA 12.9
- Docker with NVIDIA Container Toolkit
- Models directory: `~/models/Qwen2.5-7B-Instruct-Q6_K_L.gguf`

### Development Workflow

```bash
# Build and start server
inv build                  # Build Docker container with CUDA support
inv run --repo=<path>     # Start MCP server pointing to workspace
inv logs                  # View all container logs
inv logs --follow         # Follow logs in real-time
inv stop                  # Stop containers
inv test                  # Health check server
inv auth                  # Authenticate with server

# Example
inv run --repo=/home/user/Projects/local-llm-mcp/examples/CalculatorLocalModel
```

### Features Demonstrated

- ✅ Class definitions
- ✅ Method implementations with parameters and return types
- ✅ If/else conditional logic
- ✅ Exception raising (ZeroDivisionError)
- ✅ Type annotations
- ✅ Docstrings


## Tool System

### Available Tools

1. **file_metadata** - Creates structured JSON metadata for Python files
   - Actions: create_file, add_import, add_class, add_function, add_variable
   - Stores in `.meta/*.json` files

2. **workspace** - File operations and code generation
   - Actions: read, write, delete, list, search, tree
   - **generate_from_metadata** - Renders Python from JSON metadata via jinja2

3. **validation** - Code quality checks
   - Actions: tests, pre-commit, file-length, validate

4. **git_operations** - Version control
   - Actions: status, diff, commit, log, branch

5. **agent_operations** - Agent management
   - Actions: create, list, queue_task, task_status, task_result

### Supported Operations

The `operations` field in `file_metadata` supports:

- ✅ **return** - Return statement with value
- ✅ **assignment** - Variable assignment
- ✅ **validation** - Input validation with exceptions
- ✅ **function_call** - Call other functions
- ✅ **if** - Conditional logic with then/else branches
- ✅ **raise** - Exception raising
- ⏳ **for/while** - Loop operations (TODO)
- ⏳ **try/except** - Error handling (TODO)

## Agent Usage

### Creating an Agent

```python
# Via MCP tool
mcp__local-llm-agents__agent_operations({
    "operation": "create",
    "name": "CalculatorAgent",
    "description": "Expert in calculator functionality",
    "specialized_files": ["calculator.py"]
})
```

### Queuing a Task

```python
# Queue code generation task
mcp__local-llm-agents__agent_operations({
    "operation": "queue_task",
    "agent_id": "agent_id_here",
    "task_type": "code_generation",
    "message": "Create Calculator class with add, subtract, multiply, divide methods"
})
```

### Checking Task Status

```python
# Check if task completed
mcp__local-llm-agents__agent_operations({
    "operation": "task_status",
    "agent_id": "agent_id_here",
    "task_id": "task_id_here"
})
```


## File Structure

```
local-llm-mcp/
├── src/
│   ├── core/
│   │   ├── agents/          # Agent system
│   │   ├── llm/             # LLM management
│   │   ├── mcp/             # MCP bridge
│   │   ├── files/           # File manager
│   │   └── prompts/         # Prompt system
│   ├── mcp/
│   │   └── tools/           # MCP tool implementations
│   ├── schemas/             # Python file schemas
│   └── api/                 # HTTP server
├── templates/               # Jinja2 templates
├── prompts/                 # Tool and system prompts
├── examples/                # Working examples
│   └── CalculatorLocalModel/  # Calculator demo
└── tests/                   # Test suite
```

## License

[License information here]

## Contributing

[Contributing guidelines here]

## Contact

[Contact information here]
