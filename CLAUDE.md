# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Workflow

**CRITICAL SERVER CONSTRAINTS:**

- **TO SEE YOUR CHANGES REFLECTED IN THE SERVER YOU MUST run: inv stop && inv build && inv run --repo=/home/tvanfossen/Projects/local-llm-mcp/examples/PyChess && inv auth**

```bash
# Build and start server
inv build              # Build Docker container with CUDA support
inv run                 # Start MCP server in Docker (port 8000)
inv logs                # View all container logs
inv stop                # Stop containers
inv auth                # auth the server once started

```


## Architecture Overview

### Core Concept: Agent-Based MCP Server
This is a **local LLM MCP server** that provides Claude Code with specialized agents. Each agent owns exactly one file and uses a local CUDA-accelerated LLM for code generation with **XML-structured tool calling**.

### Key Architectural Patterns

**1. Agent File Ownership (Strict 1:1 Mapping)**
- One agent per file, one file per agent
- Agents persist per repository (not globally)
- File ownership prevents conflicts
- Delete agent to free file for new agent

**2. Async Task Queueing Architecture (FIXED)**
```
Claude Code → HTTP/MCP → Agent Registry → Individual Agents → Local LLM → Tool Execution (Async)
```

**3. Component Hierarchy**
- `local_llm_mcp_server.py` - Main orchestrator and entry point
- `src/core/agents/registry/registry.py` - Agent lifecycle and async task queue
- `src/core/llm/manager/manager.py` - Local model management with CUDA
- `src/mcp/` - MCP protocol implementation and tool execution
- `src/api/` - HTTP server with authentication and endpoints

### Critical Implementation Details

**Agent Communication Flow (Updated):**
1. MCP tool call creates/queues agent task
2. Agent uses local LLM to generate XML tool calls
3. **NEW**: Tool calls queue immediately and return `{"queued": True, "task_id": "..."}`
4. Async task queue processes tool calls independently
5. Results available via task status/result queries

**Tool Call Format (XML-First):**
- Agents receive XML-optimized prompts for Qwen2.5-7B
- Local LLM generates XML tool calls (with JSON fallback)
- Four core tools: `file_metadata`, `workspace`, `validation`, `git_operations`
- Metadata stored in `.meta/*.xml` files with structured content
- Jinja2 templates render Python code from XML metadata

**CUDA Requirements:**
- RTX 1080ti (11GB VRAM) optimized
- All GPU layers (-1), 8192 context window
- Model: `~/models/Qwen2.5-7B-Instruct-Q6_K_L.gguf`
- Expected: 15-25 tokens/second

## Current State (FULLY FUNCTIONAL)

### ✅ XML-Structured Generation System
- **Status**: XML tool calling fully implemented and tested
- **Working**: Agent creation, async task queueing, XML metadata generation, jinja2 code generation
- **Flow**: Agent → XML tool calls → file_metadata → workspace generate_from_metadata → clean Python code
- **Template System**: Jinja2 templates with proper formatting and `autoescape=False`

### ✅ Async Task Queue (RESOLVED)
- **Previous Issue**: Bridge blocked for 30 seconds waiting for tool completion
- **Resolution**: Modified `_execute_tool_call_queued` to return immediately
- **Current Behavior**: All tool calls queue asynchronously without blocking
- **Performance**: 100+ tool calls can queue concurrently

### ✅ Tool Integration
1. `file_metadata` - Creates `.meta/*.xml` structured metadata
2. `workspace generate_from_metadata` - Renders Python from XML using jinja2
3. `validation` - Tests, linting, file length checks
4. `git_operations` - Version control integration
5. `agent_operations` - Agent lifecycle management

### File Structure Context
- `.meta/` - Agent-generated XML metadata files
- `.mcp-agents/` - Persistent agent state per repository
- `src/core/agents/agent/agent.py` - Individual agent implementation
- `src/core/mcp/bridge/` - Tool call parsing and execution bridge
- `templates/python_file.j2` - Jinja2 template for code generation
- `prompts/tools/` - Unified tool descriptions

## Environment Setup

### Required Environment
- Ubuntu 22.04, NVIDIA Driver 575+, CUDA 12.9
- Docker with NVIDIA Container Toolkit
- Models directory: `~/models/`
- Workspace mounted at `/workspace` in container

### Authentication
- Server requires session-based auth for MCP calls
- Health endpoint publicly accessible
- Orchestrator UI provides auth token management

## Tool Usage Patterns

### Creating and Using Agents
```python
# 1. Create specialized agent
mcp__local-llm-agents__agent_operations({
    "operation": "create",
    "name": "BoardArchitect",
    "description": "Expert in chess board data structures",
    "specialized_files": ["core/board.py"]
})

# 2. Queue code generation task (async)
mcp__local-llm-agents__agent_operations({
    "operation": "queue_task",
    "agent_id": "agent_id_here",
    "task_type": "code_generation",
    "message": "Create ChessBoard class with 8x8 representation..."
})

# 3. Check task status
mcp__local-llm-agents__agent_operations({
    "operation": "task_status",
    "agent_id": "agent_id_here",
    "task_id": "task_id_here"
})

# 4. Get task result when completed
mcp__local-llm-agents__agent_operations({
    "operation": "task_result",
    "agent_id": "agent_id_here",
    "task_id": "task_id_here"
})
```

### Manual Tool Operations
```python
# Generate Python from existing XML metadata
mcp__local-llm-agents__workspace({
    "action": "generate_from_metadata",
    "path": "core/board.py"
})

# Validate generated code
mcp__local-llm-agents__validation({
    "operation": "tests",
    "file_paths": ["core/board.py"]
})

# Commit changes
mcp__local-llm-agents__git_operations({
    "operation": "commit",
    "message": "Add ChessBoard class",
    "add_all": True
})
```

## Project Orchestration

### Sample Project Structure
See `sample_prompt.xml` for complete PyChess game orchestration:

```xml
<project_orchestration>
    <project>
        <name>PyChess</name>
        <entry_point>chess.py</entry_point>
    </project>
    <agents>
        <agent name="BoardArchitect" managed_file="core/board.py"/>
        <agent name="PieceDesigner" managed_file="core/pieces.py"/>
        <agent name="GameMaster" managed_file="core/game.py"/>
        <agent name="UIDesigner" managed_file="gui/interface.py"/>
        <agent name="AIStrategist" managed_file="ai/engine.py"/>
    </agents>
    <workflow>
        <phase name="agent_creation">Create all specialized agents</phase>
        <phase name="code_generation">Queue tasks for each component</phase>
        <phase name="validation">Test and validate all code</phase>
        <phase name="integration">Commit and finalize</phase>
    </workflow>
</project_orchestration>
```

## Development Notes

### When Working on Agent Code
- Monitor `inv logs` for model output debugging
- Agent responses should be XML tool calls
- Check `.meta/*.xml` files for proper metadata generation
- Use async task status checking rather than blocking

### When Working on MCP Integration
- MCP endpoints in `src/api/http/handlers/handlers.py`
- Tool definitions in `local_llm_mcp_server.py`
- Bridge logic in `src/core/mcp/bridge/bridge.py`
- Tool descriptions in `prompts/tools/`

### When Working on LLM Integration
- Model management in `src/core/llm/manager/manager.py`
- Tool call parsing in `src/core/mcp/bridge/unified_parser.py`
- Prompt formatting in `src/core/mcp/bridge/formatter.py`
- Template rendering in `src/core/files/file_manager.py`

### When Working on Templates
- Jinja2 templates in `templates/`
- Test with `workspace generate_from_metadata`
- Ensure proper newlines and formatting
- Use `autoescape=False` for code generation

## Recent Major Fixes

### ✅ Async Queueing Resolution
- **Problem**: Tool calls blocked Claude Code for 30+ seconds
- **Solution**: Modified bridge to return immediately with task IDs
- **Impact**: Unlimited concurrent tool calls, no more timeouts

### ✅ Template System Enhancement
- **Problem**: Generated code had formatting issues
- **Solution**: Fixed jinja2 templates with proper spacing
- **Impact**: Clean, properly formatted Python code generation

### ✅ Tool Description Unification
- **Problem**: Tool descriptions scattered across codebase
- **Solution**: Centralized in `prompts/tools/` directory
- **Impact**: Maintainable, consistent tool documentation
