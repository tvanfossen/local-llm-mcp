# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Workflow

DONT START THE SERVER YOURSELF - WAIT FOR ME AND I WILL DO IT
```bash
# Build and start server
inv build              # Build Docker container with CUDA support
inv run                 # Start MCP server in Docker (port 8000)
inv logs                # View all container logs
inv logs --follow       # Follow logs in real-time
inv stop                # Stop containers
inv test                # Health check server

# Testing
inv test                # Run pytest with coverage
inv test --verbose      # Verbose test output
python3 -m pytest src/path/to/test_file.py::test_function  # Single test
```

### Container Management
```bash
# Server is always run in Docker with GPU acceleration
inv run --port=8080     # Custom port
inv run --repo=/path    # Mount different workspace
docker logs local-llm-mcp-server  # Direct container logs
```

## Architecture Overview

### Core Concept: Agent-Based MCP Server
This is a **local LLM MCP server** that provides Claude Code with specialized agents. Each agent owns exactly one file and uses a local CUDA-accelerated LLM for code generation.

### Key Architectural Patterns

**1. Agent File Ownership (Strict 1:1 Mapping)**
- One agent per file, one file per agent
- Agents persist per repository (not globally)
- File ownership prevents conflicts
- Delete agent to free file for new agent

**2. MCP Bridge Architecture**
```
Claude Code → HTTP/MCP → Agent Registry → Individual Agents → Local LLM → Tool Execution
```

**3. Component Hierarchy**
- `local_llm_mcp_server.py` - Main orchestrator and entry point
- `src/core/agents/registry/registry.py` - Agent lifecycle and task queue
- `src/core/llm/manager/manager.py` - Local model management with CUDA
- `src/mcp/` - MCP protocol implementation and tool execution
- `src/api/` - HTTP server with authentication and endpoints

### Critical Implementation Details

**Agent Communication Flow:**
1. MCP tool call creates/queues agent task
2. Agent uses local LLM to generate tool calls (JSON format)
3. Generated tool calls execute against workspace/validation/git tools
4. Results flow back through MCP to Claude Code

**Tool Call Format:**
- Agents receive JSON prompts optimized for Qwen2.5-7B
- Local LLM generates JSON tool calls (not XML)
- Three core tools: `workspace`, `validation`, `git_operations`
- Metadata stored in `.meta/*.json` files before actual file creation

**CUDA Requirements:**
- RTX 1080ti (11GB VRAM) optimized
- All GPU layers (-1), 8192 context window
- Model: `~/models/Qwen2.5-7B-Instruct-Q6_K_L.gguf`
- Expected: 15-25 tokens/second

## Current State and Known Issues

### JSON Tool Call Baseline
- **Current Status**: Reverted to JSON tool calls after XML implementation issues
- **Working**: Agent creation, task queueing, basic tool execution
- **Issue**: Model generates text responses instead of JSON tool calls in some cases
- **Debug**: Model output logging enabled in agent code

### Agent Workflow (JSON Baseline)
1. Agent creates `.meta/*.json` metadata file
2. Uses JSON prompts to call local LLM
3. LLM should generate JSON tool calls for workspace/validation/git
4. Tools execute and create actual files
5. **Current Problem**: LLM generating text instead of tool calls

### File Structure Context
- `.meta/` - Agent-generated metadata (JSON format)
- `.mcp-agents/` - Persistent agent state per repository
- `src/core/agents/agent/agent.py` - Individual agent implementation
- `src/core/mcp/bridge/` - Tool call parsing and execution bridge

## Environment Setup

### Required Environment
- Ubuntu 22.04, NVIDIA Driver 575, CUDA 12.9
- Docker with NVIDIA Container Toolkit
- Models directory: `~/models/`
- Workspace mounted at `/workspace` in container

### Authentication
- Server requires session-based auth for MCP calls
- Health endpoint publicly accessible
- Orchestrator UI provides auth token management

## Development Notes

### When Working on Agent Code
- Always test with `inv run` then create agent and queue task - end user MUST authenticate before this functions
- Monitor `inv logs` for model output debugging
- Agent responses should be JSON tool calls, not text
- Check `.meta/*.json` files for proper metadata generation

### When Working on MCP Integration
- MCP endpoints in `src/api/http/handlers/handlers.py`
- Tool definitions in `local_llm_mcp_server.py`
- Bridge logic in `src/core/mcp/bridge/bridge.py`

### When Working on LLM Integration
- Model management in `src/core/llm/manager/manager.py`
- Tool call parsing in `src/core/mcp/bridge/parser.py`
- Prompt formatting for Qwen2.5 in `src/core/mcp/bridge/formatter.py`