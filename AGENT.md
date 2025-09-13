# MCP Toolchain Consolidation Agent Workflow

## Overview
Consolidate the MCP toolchain to 4 core tools (Local Model, Git, Workspace, Validation) while ensuring strict adherence to requirements: files under 300 lines, cognitive complexity ≤7, function returns ≤3, DRY principles, no mocks, no testing scripts.

## Phase 1: MCP Tools Consolidation

### Phase 1A: Remove Redundant Testing/Validation Tools
**Objective**: Consolidate testing and validation tools, removing redundancy between `src/mcp/tools/testing/` and `src/mcp/tools/validation/`

**File**: `src/mcp/tools/validation/validation.py`
**Action**: Update this single file to contain all validation functionality, removing duplicated code from testing directory

**Requirements**:
- Keep `run_tests`, `run_pre_commit`, `validate_file_length`, and `run_all_validations` functions
- Remove any duplicate functionality from testing directory
- Ensure all functions use common utilities from `src/core/utils/utils.py`
- Avoid monolith files
- Limit cognitive complexity to 7 per function
- Maximum 3 returns per function

**Prompt**: "Update src/mcp/tools/validation/validation.py to consolidate all testing and validation functionality. Remove any duplicate code patterns and ensure all functions use shared utilities from src/core/utils/utils.py. Keep the file under 300 lines with cognitive complexity ≤7 and ≤3 returns per function."

### Phase 1B: Consolidate Git Operations
**Objective**: Update git tools to use single consolidated approach

**File**: `src/mcp/tools/git_operations/git_operations.py`  
**Action**: Ensure this file contains all git functionality referenced in executor

**Requirements**:
- Consolidate all git operations into this single file
- Remove any duplicate git functionality from other locations
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function

**Prompt**: "Consolidate all git operations in src/mcp/tools/git_operations/git_operations.py. Remove any duplicate git functionality from other files and ensure all functions use shared utilities. Keep under 300 lines with cognitive complexity ≤7 and ≤3 returns per function."

### Phase 1C: Create Local Model Tool
**Objective**: Create the local model MCP tool for LLM interactions

**File**: `src/mcp/tools/local_model/local_model.py`
**Action**: Implement local model tool that interfaces with LLM manager

**Requirements**:
- Create tool for interacting with local model
- Interface with `src/core/llm/manager/manager.py`
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function
- No circular dependencies with agent system

**Prompt**: "Implement src/mcp/tools/local_model/local_model.py to provide MCP tool interface for local model interactions. Interface with the LLM manager without creating circular dependencies. Use shared utilities and maintain file size/complexity limits."

### Phase 1D: Update MCP Tool Executor
**Objective**: Update executor to use only the 4 consolidated tools

**File**: `src/mcp/tools/executor/executor.py`
**Action**: Simplify executor to only include the 4 core tools (Local Model, Git, Workspace, Validation)

**Requirements**:
- Remove all tool definitions except: local_model, git_operations, workspace operations, validation
- Consolidate workspace operations (file read/write/list) into cohesive tool set
- Keep file under 300 lines
- Ensure all tool functions use shared utilities
- Maintain complexity ≤7, ≤3 returns per function

**Prompt**: "Simplify src/mcp/tools/executor/executor.py to contain only 4 core tool categories: Local Model, Git Operations, Workspace Operations (file I/O), and Validation. Remove all other tool definitions. Consolidate related tools and ensure all use shared utilities. Keep under 300 lines with proper complexity limits."

## Phase 2: Core Agent System Integration

### Phase 2A: Update Agent Class
**Objective**: Ensure agents properly interface with consolidated MCP tools

**File**: `src/core/agents/agent/agent.py`
**Action**: Update agent to properly interface with LLM manager and MCP tools

**Requirements**:
- Remove any mock implementations
- Ensure proper integration with LLM manager for actual model inference
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function
- Implement actual task execution (not placeholders)

**Prompt**: "Update src/core/agents/agent/agent.py to properly integrate with the LLM manager for actual model inference. Remove any mock implementations or placeholder responses. Ensure agents can execute real tasks using the consolidated MCP toolchain. Use shared utilities and maintain size/complexity limits."

### Phase 2B: Update Agent Registry
**Objective**: Ensure registry properly manages agents with new toolchain

**File**: `src/core/agents/registry/registry.py`
**Action**: Update registry to work with consolidated toolchain

**Requirements**:
- Ensure proper agent lifecycle management
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function
- Remove any unnecessary complexity

**Prompt**: "Update src/core/agents/registry/registry.py to properly manage agents with the consolidated MCP toolchain. Simplify any overly complex logic and ensure all functions use shared utilities. Maintain file size and complexity limits."

## Phase 3: LLM Manager Integration

### Phase 3A: Update LLM Manager
**Objective**: Ensure LLM manager properly instantiates model with MCP tools access

**File**: `src/core/llm/manager/manager.py`
**Action**: Fix model instantiation to properly work with MCP toolchain

**Requirements**:
- Remove mock mode implementations
- Ensure model is properly loaded and accessible to agents
- Integrate with MCP toolchain for model operations
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function
- Do NOT create circular dependency with local_model tool

**Prompt**: "Update src/core/llm/manager/manager.py to properly instantiate and manage the local model. Remove mock implementations and ensure the model is accessible to the agent system. Avoid circular dependencies with the MCP toolchain. Use shared utilities and maintain size/complexity limits."

## Phase 4: Configuration and Utilities Cleanup

### Phase 4A: Update Core Utilities
**Objective**: Ensure utilities support all consolidated tools

**File**: `src/core/utils/utils.py`
**Action**: Add any missing utility functions needed by consolidated tools

**Requirements**:
- Provide all common functions needed by the 4 core tools
- Remove any unused utility functions
- Under 300 lines, complexity ≤7, ≤3 returns per function
- Follow DRY principles

**Prompt**: "Update src/core/utils/utils.py to provide all common utility functions needed by the consolidated MCP toolchain. Remove any unused functions and ensure DRY principles are followed. Maintain file size and complexity limits."

### Phase 4B: Update Configuration Manager
**Objective**: Ensure configuration supports consolidated toolchain

**File**: `src/core/config/manager/manager.py`
**Action**: Simplify configuration for 4-tool system

**Requirements**:
- Remove unnecessary configuration complexity
- Support the 4 core tools only
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function

**Prompt**: "Simplify src/core/config/manager/manager.py to support only the 4 core MCP tools. Remove unnecessary configuration complexity and ensure the system can properly initialize with the consolidated toolchain. Use shared utilities and maintain limits."

## Phase 5: System Integration and Cleanup

### Phase 5A: Update MCP Handler
**Objective**: Ensure MCP handler works with consolidated toolchain

**File**: `src/mcp/handler.py`
**Action**: Update handler to work with 4-tool system

**Requirements**:
- Support only the 4 core tools
- Remove unnecessary complexity
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function

**Prompt**: "Update src/mcp/handler.py to work with the consolidated 4-tool MCP system. Remove any unnecessary complexity and ensure proper integration with the simplified toolchain. Use shared utilities and maintain limits."

### Phase 5B: Final System Validation
**Objective**: Ensure entire system works cohesively

**File**: `local_llm_mcp_server.py`
**Action**: Update main server to work with consolidated system

**Requirements**:
- Ensure proper initialization of all components
- Remove any unused imports or complexity
- Use utilities from `src/core/utils/utils.py`
- Under 300 lines, complexity ≤7, ≤3 returns per function

**Prompt**: "Update local_llm_mcp_server.py to properly initialize the consolidated 4-tool MCP system. Ensure all components integrate correctly and remove any unused complexity. Use shared utilities and maintain limits."

---
