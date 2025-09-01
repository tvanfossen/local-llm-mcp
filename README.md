# Local LLM MCP Server

Agent-based MCP server that connects Claude Code to a local CUDA-accelerated LLM for repository orchestration.

## Core Architecture

- **One Agent Per File**: Each agent manages exactly one file with strict ownership enforcement
- **Adversarial Testing**: Every functional file gets a paired pytest agent
- **JSON Schema Validation**: All agent communications use standardized Pydantic schemas
- **CUDA Optimization**: Containerized with CUDA 12.5 support for RTX 1080ti
- **Repository-Scoped**: Agents persist per repository, not globally

## Quick Start

### Prerequisites

- Docker with NVIDIA Container Toolkit
- CUDA-compatible GPU (tested on RTX 1080ti)
- Models in `~/models/` directory
- Python with invoke package

### Setup

1. **Clone and prepare:**
   ```bash
   cd ~/Projects
   git clone <your-repo>
   cd local-llm-mcp
   pip install invoke
   ```

2. **Ensure model exists:**
   ```bash
   ls ~/models/Qwen2.5-7B-Instruct-Q6_K_L.gguf
   # If missing, download from Hugging Face
   ```

3. **Build container:**
   ```bash
   inv build
   ```

4. **Start server:**
   ```bash
   inv run
   ```

5. **Verify CUDA acceleration:**
   ```bash
   inv test
   # Should return healthy status with GPU information
   ```

### Claude Code Integration

1. **Install Claude Code** (if not already installed)

2. **Configure MCP connection:**
   ```bash
   mkdir -p ~/.config/claude-code

   cat > ~/.config/claude-code/mcp.json << 'EOF'
   {
     "mcpServers": {
       "local-llm-agents": {
         "command": "curl",
         "args": ["-X", "POST", "http://localhost:8000/mcp", "-H", "Content-Type: application/json", "-d"]
       }
     }
   }
   EOF
   ```

3. **Test Claude Code connection:**
   ```bash
   claude-code
   # In Claude interface, you should see local-llm-agents tools available
   ```

## Repository Orchestration Workflow

### Phase 1: Agent Creation

Start Claude Code in your target repository:

```bash
cd ~/your-project
claude-code
```

**Create functional file agents:**
```
Use create_agent to make a database agent managing schema.sql with system prompt "You are a PostgreSQL expert focused on clean, normalized schema design. Always include proper constraints, indexes, and documentation."

Use create_agent to make a models agent managing models.py with system prompt "You are a Python ORM expert using SQLAlchemy. Create clean, type-annotated models with proper relationships and validation."

Use create_agent to make an API agent managing routes.py with system prompt "You are a FastAPI expert focused on REST API design. Create well-documented endpoints with proper error handling and validation."
```

**Verify agent creation:**
```
Use list_agents to confirm all agents and their file ownership
```

### Phase 2: Development Orchestration

**Have agents create initial structures:**
```
Use chat_with_agent to have the database agent create a user authentication schema with roles and permissions

Use chat_with_agent to have the models agent create SQLAlchemy models matching the database schema

Use chat_with_agent to have the API agent create authentication endpoints using the models
```

**Review and iterate:**
```
Use get_agent_file to review each agent's work

Use chat_with_agent to refine implementations based on cross-file dependencies
```

### Phase 3: Testing Integration

**Create test agents (adversarial):**
```
Use create_agent to make a schema test agent managing test_schema.sql with system prompt "You are a database testing expert. Create comprehensive tests for schema validation, constraint checking, and data integrity."

Use create_agent to make a models test agent managing test_models.py with system prompt "You are a pytest expert focused on ORM testing. Create comprehensive model tests including validation, relationships, and edge cases."

Use create_agent to make an API test agent managing test_routes.py with system prompt "You are a FastAPI testing expert. Create comprehensive endpoint tests including authentication, validation, and error scenarios."
```

**Generate comprehensive tests:**
```
Use chat_with_agent to have each test agent create thorough pytest suites for their corresponding functional files
```

### Phase 4: Integration and Refinement

**Cross-agent coordination:**
```
Use chat_with_agent to have the API agent update endpoints based on any model changes

Use chat_with_agent to have test agents update their tests when functional code changes

Use agent_update_file to have agents make specific targeted changes
```

**Validation:**
```
Use get_agent_file to review all generated files

Run tests locally to verify integration
```

## Agent Management Commands

### Core Agent Operations
- `create_agent` - Create new agent for specific file
- `list_agents` - Show all agents and file ownership
- `get_agent_info` - Detailed agent information
- `chat_with_agent` - Send instructions to agent
- `agent_update_file` - Have agent modify its file
- `get_agent_file` - Retrieve agent's file content
- `delete_agent` - Remove agent (frees file for new agent)
- `system_status` - Server and model status

### Development Workflow
1. Create agents for core files (models, routes, schemas)
2. Create corresponding test agents
3. Have agents build initial implementations
4. Iterate with chat_with_agent for refinements
5. Cross-reference between agents for consistency
6. Generate comprehensive test suites
7. Validate integration locally

## Container Management

```bash
inv build          # Build container
inv run             # Start server (port 8000, ~/models)
inv run --port=8080 # Custom port
inv logs            # View server logs
inv logs --follow   # Follow logs in real-time
inv stop            # Stop containers
inv shell           # Access container shell
inv clean           # Remove containers and images
inv test            # Health check
inv dev             # Build and run together
```

## File Ownership Rules

- **Strict Enforcement**: One agent per file, one file per agent
- **No Conflicts**: Cannot create agent for already-managed file
- **Clean Handoffs**: Deleting agent frees file for new agent
- **Repository Scoped**: Agent state persists per repository
- **Test Pairing**: Every functional file should have adversarial test agent

## Architecture Benefits

- **Token Efficiency**: 60-80% reduction in context usage through specialized agents
- **Privacy**: All processing happens locally on your GPU
- **Speed**: 15-25 tokens/second on RTX 1080ti
- **Consistency**: JSON schema validation prevents communication errors
- **Scalability**: Add agents as project grows
- **Testing**: Built-in adversarial test generation

## Troubleshooting

**Server won't start:**
```bash
inv logs  # Check container logs
docker ps # Verify container status
nvidia-smi # Verify GPU accessibility
```

**CUDA not working:**
```bash
inv shell
python3 -c "from llama_cpp import Llama; print('CUDA test')"
```

**Claude Code not connecting:**
- Verify server running on port 8000
- Check MCP configuration in ~/.config/claude-code/mcp.json
- Test health endpoint: `curl http://localhost:8000/health`

**Agent conflicts:**
```
Use list_agents to see current file ownership
Use delete_agent to free up files if needed
```

## Performance Tuning

For RTX 1080ti (11GB VRAM):
- Context size: 8192 tokens (can increase to 16384 if needed)
- GPU layers: -1 (all layers on GPU)
- Batch size: 512 (optimal for 1080ti)
- Expected: 15-25 tokens/second

Model fits comfortably in 11GB with room for context and multiple concurrent agents.
