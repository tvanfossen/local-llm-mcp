# Local LLM MCP Server - Self-Maintenance Workflow

## Overview

This repository is designed to maintain itself using the local LLM through MCP tools. The workflow leverages:
- **Schema validation hooks** for structural consistency
- **Jinja2 templates** for code generation standardization
- **Co-located tests** for immediate validation
- **Bite-sized contexts** optimized for local model consumption
- **MCP tool exposure** to the local model, server, and HTML interface

## Self-Maintenance Architecture

### Core Principle: Local Model as Primary Worker
- **Claude Code**: High-level orchestration, planning, and validation
- **Local Model**: Implementation, code generation, and detailed work
- **Schema Enforcement**: Automated validation via pre-commit hooks
- **Template System**: Consistent code generation patterns

### Workflow Components

#### 1. Schema Validation Pipeline
```bash
# Pre-commit validation
python3 scripts/schema_validator.py

# Template compliance check
python3 scripts/template_validator.py  # To be created

# Test discovery and execution
pytest src/ --tb=short
```

#### 2. Jinja2 Template System (To Be Implemented)
```
templates/
├── function/
│   ├── implementation.py.j2      # Python implementation template
│   ├── test.py.j2               # Test file template
│   ├── readme.md.j2             # Documentation template
│   └── schema.json.j2           # Interface schema template
├── helpers/
│   ├── imports.j2               # Import statement helpers
│   ├── docstrings.j2            # Docstring templates
│   └── error_handling.j2        # Error handling patterns
└── specs/
    └── function_spec.json.j2    # Specification template
```

#### 3. MCP Tool Masking Strategy
**Current State**: Individual git tools (`git_status`, `git_commit`, `git_diff`)
**Future State**: Unified `git` tool with action parameter
```json
{
  "name": "git",
  "description": "Git operations with action-based dispatch",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {"enum": ["status", "commit", "diff", "log"]},
      "message": {"type": "string"},
      "files": {"type": "array"}
    }
  }
}
```

### Invoke Task Configuration

#### Development Tasks
- `inv run` - Start the server
- `inv reload` - Reload server with changes
- `inv test` - Run tests with coverage
- `inv validate` - Run schema validation
- `inv template <function_name>` - Generate new function from template
- `inv hook-install` - Install pre-commit hooks

#### Self-Maintenance Tasks
- `inv self-diagnose` - Check system health and suggest improvements
- `inv self-improve <area>` - Let local model improve specific area
- `inv self-test` - Comprehensive validation of entire system
- `inv template-sync` - Sync templates with existing code

## Local Model Integration Points

### 1. MCP Tool Exposure
**Hierarchy**: Claude Code → Local Model → MCP Tools
- Local model receives same MCP tool access as external clients
- Standardized tool calling interface via MCP protocol
- Context-aware tool selection based on current task

### 2. Template-Driven Code Generation
**Process**:
1. Claude Code provides high-level specification
2. Local model generates implementation using templates
3. Schema validator ensures compliance
4. Co-located tests validate functionality

### 3. Bite-Sized Context Windows
**Optimization Strategy**:
- Each function directory contains complete context (≤300 lines implementation)
- README files provide full context for local model
- Schema.json files define exact interfaces
- Templates ensure consistent patterns

## Implementation Phases

### Phase 1: Template System Creation
- [ ] Create Jinja2 templates for all file types
- [ ] Implement template generator script
- [ ] Create template validation hooks
- [ ] Generate example functions using templates

### Phase 2: Invoke Task Setup
- [x] Create `tasks.py` with development tasks
- [x] Implement Docker build/run tasks for MCP workflow
- [x] Add schema validation tasks
- [x] Create basic template generation framework
- [ ] Fix template system to use Jinja2 properly
- [ ] Remove hardcoded templates from invoke tasks

### Phase 3: MCP Tool Enhancement
- [ ] Implement tool masking for git operations
- [ ] Create unified tool interfaces
- [ ] Add tool discovery and documentation
- [ ] Expose tools to HTML interface

### Phase 4: Self-Maintenance Loop
- [ ] Create self-diagnostic tools
- [ ] Implement improvement suggestion system
- [ ] Add automated maintenance tasks
- [ ] Enable local model autonomous operation

## Usage Examples

### Starting Self-Maintenance Session
```bash
# Start server with MCP tools exposed
inv run --repo=/home/tvanfossen/Projects/local-llm-mcp

# In Claude Code:
# Connect to server, gain access to MCP tools
# Use local model for implementation work
# Validate changes with schema hooks
```

### Creating New Function
```bash
# Generate function template
inv template src/mcp/tools/file/copy

# Local model implements using template
# Schema validation ensures compliance
# Tests validate functionality
```

### Tool Masking Example
```python
# Before: Multiple tools
await call_tool("git_status")
await call_tool("git_commit", {"message": "fix"})
await call_tool("git_diff", {"staged": true})

# After: Unified tool
await call_tool("git", {"action": "status"})
await call_tool("git", {"action": "commit", "message": "fix"})
await call_tool("git", {"action": "diff", "staged": true})
```

## Quality Gates

### Automated Validation
1. **Schema Compliance**: All files follow schema structure
2. **Template Compliance**: Generated code matches templates
3. **Test Coverage**: All functions have co-located tests
4. **Size Limits**: Implementation ≤300 lines, tests ≤500 lines
5. **Documentation**: Complete README for each function

### Local Model Constraints
- **Context Window**: Each function directory is self-contained
- **Template Adherence**: Must use Jinja2 templates for generation
- **Error Handling**: Standardized error patterns required
- **Testing**: Must generate tests alongside implementation

## Success Metrics

1. **Self-Maintenance**: Repository can improve itself autonomously
2. **Template Compliance**: 100% of functions generated from templates
3. **Schema Compliance**: All validation hooks pass consistently
4. **Local Model Efficiency**: Reduced token usage through templates
5. **Tool Consolidation**: Unified MCP tools reduce context complexity

## Current Status (2025-09-07)

### ✅ Completed
- Basic invoke task system for development workflow
- Docker containerization with CUDA support
- MCP server startup (in development mock mode)
- AGENT_bugs.json tracking system
- Schema validation framework
- Project reorganization to src/ structure

### 🔄 In Progress
- MCP server endpoint functionality (server runs but endpoints need fixes)
- Health check and basic API responses

### ❌ Blockers Identified
- **BUG-004**: MCP server health endpoint not responding (empty reply)
- **BUG-001**: Schema validator too restrictive for incremental development
- **Template system needs Jinja2 implementation** (currently hardcoded in invoke)

### Next Steps

1. **Immediate**: Fix health endpoint to enable MCP tool testing
2. **Next**: Create proper Jinja2 template system (remove hardcoded templates)
3. **Then**: Use MCP tools through local agent for fibonacci example
4. **Finally**: Measure token usage comparison (MCP vs direct implementation)

This workflow transforms the repository into a self-maintaining system where the local model handles implementation details while schema validation and templates ensure consistency and quality.
