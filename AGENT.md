# Local LLM MCP Server - Self-Maintenance Workflow

## Overview

This repository implements a self-maintaining codebase using a hybrid approach:
- **Claude Code (Sonnet 4)**: High-level orchestration, file management, and MCP tool execution
- **Local LLM (Qwen2.5-7B)**: Detailed implementation work via MCP agent tools
- **Schema Enforcement**: Automated validation ensuring code quality and consistency

## Current Architecture Assessment

### ✅ Working Components
- **Core Infrastructure**: HTTP server, WebSocket support, MCP handler
- **Agent Registry**: Agent creation, management, and persistence
- **Git Tools**: Status, diff, commit, log operations
- **Testing Tools**: Pytest runner, pre-commit hooks, file validation
- **Security**: Authentication bridge between orchestrator and MCP
- **System Tools**: Unified validation (run_all_validations)

### ❌ Missing Critical Components
- **MCP Agent Tools** (`src/mcp/tools/agent/*`): Empty folders preventing agent operations
- **Agent File Operations**: No tools for agents to read/write their managed files
- **Agent Communication**: Missing structured agent-to-agent messaging
- **Template Integration**: Template generator exists but not exposed as MCP tool

## Implementation Phases

### Phase 1: Complete MCP Agent Tools [Claude Code]
**Priority: CRITICAL - Blocks all agent operations**
**Best Tool: Claude Code (file creation and structure)**

Create the missing MCP tools that enable agents to perform actual work:

```bash
# Required tools to create in src/mcp/tools/agent/
- create/create.py         # Agent creation via MCP
- update/update.py         # Update agent configuration
- chat/chat.py            # Send messages to agents
- list/list.py            # List all agents
- delete/delete.py        # Remove agents
- info/info.py            # Get agent details
```

**Claude Code Prompt:**
```
Create the complete MCP agent tools in src/mcp/tools/agent/ following this structure:
1. Each tool in its own folder (create/, update/, chat/, list/, delete/, info/)
2. Each tool must return the standard MCP response format: {"content": [{"type": "text", "text": "..."}], "isError": bool}
3. Import and use the existing AgentRegistry from src/core/agents/registry/registry.py
4. Each file must be under 300 lines
5. Include proper error handling and logging
6. Follow the pattern from existing git tools in src/mcp/tools/git/
```

### Phase 2: Agent File Operations [Claude Code]
**Priority: HIGH - Enables agents to modify code**
**Best Tool: Claude Code (direct file system integration)**

Create file operation tools for agents:

```bash
# Required tools in src/mcp/tools/file/
- read/read.py           # Read file content
- write/write.py         # Write complete file
- update/update.py       # Update specific sections
- validate/validate.py   # Check file syntax/schema
```

**Claude Code Prompt:**
```
Create MCP file operation tools in src/mcp/tools/file/:
1. Each tool must respect the workspace root from SystemConfig
2. Include safety checks to prevent operations outside workspace
3. Support both absolute and relative paths
4. Return file content in markdown code blocks for readability
5. Include line number information for update operations
6. Follow existing MCP response format patterns
```

### Phase 3: Template Integration Tool [Claude.ai Opus 4.1]
**Priority: MEDIUM - Complex template logic**
**Best Tool: Opus 4.1 (complex Jinja2 template design)**

Design a sophisticated template system for code generation:

**Opus 4.1 Prompt:**
```
Design a comprehensive Jinja2 template system for the Local LLM MCP project that:

1. Creates an MCP tool wrapper around the existing template_generator.py
2. Exposes template operations as MCP tools (generate_from_template, list_templates, validate_template)
3. Designs templates for common patterns:
   - API endpoints with full CRUD operations
   - Agent task handlers with standard error handling
   - Test suites with fixtures and mocks
   - Schema validators with comprehensive checks

4. Implements a template specification format that can be consumed by the local LLM:
   - JSON schema for template variables
   - Validation rules for generated code
   - Post-generation hooks for formatting and validation

5. Creates a template inheritance system:
   - Base templates for common patterns
   - Specialized templates extending base functionality
   - Composition patterns for complex structures

The system should allow the local LLM to generate consistent, schema-compliant code without needing to understand the entire codebase structure.
```

### Phase 4: Agent Task Execution Pipeline [Claude Code]
**Priority: HIGH - Core workflow enablement**
**Best Tool: Claude Code (integration work)**

Wire up the complete agent execution pipeline:

**Claude Code Prompt:**
```
Update src/mcp/tools/executor/executor.py to:
1. Import all new agent and file tools from Phase 1 & 2
2. Register them in the available_tools dictionary
3. Ensure proper async/await patterns
4. Add comprehensive error handling
5. Include detailed logging for debugging
6. Update tool metadata with proper input schemas
```

### Phase 5: Agent Self-Improvement Loop [Claude Code]
**Priority: MEDIUM - Automation enhancement**
**Best Tool: Claude Code (workflow orchestration)**

Create tools enabling agents to improve their own code:

```bash
# Required tools in src/mcp/tools/improvement/
- analyze/analyze.py       # Code quality analysis
- refactor/refactor.py     # Automated refactoring
- optimize/optimize.py     # Performance optimization
- document/document.py     # Documentation generation
```

**Claude Code Prompt:**
```
Create self-improvement MCP tools that allow agents to:
1. Analyze their managed files for code quality issues
2. Suggest and implement refactoring improvements
3. Add missing docstrings and type hints
4. Ensure schema compliance (max 300 lines, etc.)
5. Generate comprehensive test coverage
Each tool should work with the local LLM to generate improvements
```

### Phase 6: Agent Collaboration Framework [Opus 4.1]
**Priority: LOW - Advanced feature**
**Best Tool: Opus 4.1 (complex system design)**

Design inter-agent communication protocol:

**Opus 4.1 Prompt:**
```
Design an agent collaboration framework for the MCP server that:

1. Defines a message passing protocol between agents
2. Implements dependency resolution (Agent A needs Agent B's output)
3. Creates workflow orchestration patterns:
   - Sequential task execution
   - Parallel task distribution
   - Conditional branching based on results
4. Designs conflict resolution for shared file access
5. Implements rollback mechanisms for failed operations