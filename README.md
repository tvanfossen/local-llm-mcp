# File: ~/Projects/local-llm-mcp/README.md

# Standardized Agent-Based Local LLM MCP Server

A clean, modular HTTP server for Claude Code with persistent agents using standardized JSON schemas.

## 🎯 Core Architecture Principles

- **One Agent Per File**: Hard-enforced rule, zero exceptions
- **JSON Schema Validation**: All communications follow strict Pydantic schemas  
- **Separation of Concerns**: Each module has single, focused responsibility
- **No Monoliths**: Clean interfaces between components
- **Agent Orchestration**: Claude Code orchestrates, agents specialize

## 🏗️ Architecture

```
local_llm_mcp_server.py  # Entry point - minimal orchestration only
├── core/                # Business logic layer
│   ├── config.py        # Configuration management
│   ├── agent.py         # Individual agent behavior
│   ├── llm_manager.py   # Model loading & inference  
│   └── agent_registry.py# Agent lifecycle & file ownership
├── api/                 # Interface layer
│   ├── mcp_handler.py   # MCP protocol for Claude Code
│   ├── http_server.py   # Starlette application setup
│   ├── endpoints.py     # HTTP API endpoints
│   └── websocket_handler.py # Real-time communication
└── schemas/             # Data contracts
    └── agent_schemas.py # JSON schema definitions
```

## 🚀 Quick Start

```bash
# Prerequisites: uv installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup project
cd ~/Projects/local-llm-mcp
./setup.sh

# Add your model to models/ directory
# Place your .gguf file as: models/qwen2.5-coder-7b-instruct.gguf

# Start server
uv run local_llm_mcp_server.py

# Test (in another terminal)
uv run test.py
```

## 📡 Claude Code Integration

The server provides a `/mcp` endpoint that Claude Code automatically discovers:

```json
// ~/.config/claude-code/mcp.json
{
  "mcpServers": {
    "standardized-agent-http": {
      "command": "bash",
      "args": ["-c", "cd /home/$USER/Projects/local-llm-mcp && uv run local_llm_mcp_server.py"]
    }
  }
}
```

## 🤖 Agent Workflow

```bash
# In Claude Code:
claude

# Create specialized agents:
"Use create_agent to make a database agent managing schema.sql"
"Use create_agent to make an API agent managing routes.py"
"Use create_agent to make a frontend agent managing index.html"

# Each agent becomes expert in their single file:
"Use chat_with_agent to have the database agent design user tables"
"Use agent_update_file to have the API agent create authentication endpoints"

# Get results:
"Use get_agent_file to see what the database agent created"
```

## 📋 JSON Schema Communication

### Agent Request Format
```json
{
  "task_type": "create|update|analyze|refactor|debug|document|test",
  "instruction": "Detailed instruction for the agent",
  "context": "Additional context (optional)",
  "parameters": {},
  "expected_output": "Description of expected format"
}
```

### Agent Response Format
```json
{
  "status": "success|error|warning|partial",
  "message": "Human-readable description",
  "file_content": {
    "filename": "managed_file.py",
    "content": "complete file content",
    "language": "python"
  },
  "changes_made": ["list of specific changes"],
  "warnings": ["any warnings or notes"],
  "tokens_used": 1234,
  "processing_time": 2.5
}
```

## 🖥️ Hardware Optimization

**Target:** RTX 1080ti (11GB VRAM) + CUDA 12.9 + Ubuntu 22.04

- **GPU Layers**: -1 (all layers on GPU)
- **Context Window**: 8192 tokens
- **Batch Size**: 512 (optimized for 1080ti)
- **Expected Performance**: 15-25 tokens/second

## 🔧 Development

```bash
# Install dependencies
uv sync

# Run with development mode
uv run local_llm_mcp_server.py

# Code formatting
uv run black .
uv run isort .

# Type checking
uv run mypy .

# Tests
uv run pytest
```

## 📂 File Organization Rules

1. **One Agent Per File**: Each agent manages exactly one file
2. **No Conflicts**: File ownership strictly enforced
3. **Clean Separation**: Core logic separate from API interfaces
4. **JSON Schemas**: All communications validated via Pydantic
5. **Git Managed**: State and workspaces gitignored, code versioned

## 🌐 API Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `POST /mcp` - **MCP endpoint for Claude Code**
- `GET /api/agents` - List agents (HTTP API)
- `POST /api/agents/{id}/chat` - Chat with agent
- `WS /ws` - WebSocket for real-time communication

## 💡 Usage Patterns

### Single Agent Task
```bash
# Create agent for specific file
"Use create_agent: name='DB Schema', managed_file='schema.sql', system_prompt='Database expert'"

# Have agent work on file
"Use chat_with_agent to design user authentication tables"

# Get final result
"Use get_agent_file to see the complete schema"
```

### Multi-Agent Orchestration
```bash
# Create agents for different files
"Create agents: DB agent (schema.sql), API agent (routes.py), UI agent (index.html)"

# Orchestrate work across agents
"Have DB agent design tables, then API agent create endpoints using those tables"

# Coordinate final integration
"Review all agent files and ensure they work together properly"
```

## 🎯 Benefits

- **Token Efficiency**: 60-80% cost reduction for large projects
- **Privacy**: Sensitive code never leaves your machine
- **Speed**: Local GPU inference at 15-25 tokens/second
- **Persistence**: Agents remember context across sessions
- **Clean Architecture**: Maintainable, testable, extensible
- **JSON Standardization**: Type-safe, validated communications