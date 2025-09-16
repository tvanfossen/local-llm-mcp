# Agent System MCP-Based Architecture Plan

## Executive Summary

The current implementation is close to success but needs a fundamental architectural shift. Instead of parsing unstructured text responses from the local LLM, we should expose MCP tools directly to the model, allowing it to use structured tool calls for guaranteed reliable responses. This maintains our async task queue while ensuring 100% structured communication.

## Core Architectural Change

### Current Flawed Approach
- Agent → Local LLM → Unstructured text response → Manual parsing → Hope for valid JSON
- Prone to markdown wrappers, malformed JSON, and parsing failures
- Requires complex text processing and cleanup functions

### Proposed MCP-Based Approach
- Agent → Local LLM (with MCP tools) → Structured tool calls → Guaranteed valid responses
- LLM uses MCP tools directly for workspace operations, validation, git commands
- Eliminates parsing issues by design

## Implementation Strategy

### Phase 1: Expose MCP Tools to Local LLM

**Goal**: Make LLMManager provide MCP tools to the local model instead of just prompt completion

**Key Changes**:
1. **LLMManager Enhancement** (`src/core/llm/llm_manager.py`):
   - Add MCP tool definitions to model context
   - Enable structured tool calling in local model
   - Route tool calls through existing MCP infrastructure

2. **Agent Task Flow Modification** (`src/core/agents/agent/agent.py`):
   - Remove text parsing logic
   - Let LLM call MCP tools directly
   - Monitor tool call results for task completion

### Phase 2: MCP Tool Integration for Code Generation

**Current Flow**:
```
Agent → LLM → "```python\ncode\n```" → Parse → Write file
```

**New Flow**:
```
Agent → LLM → workspace_tool_call(json_artifact) → File created via template
```

**Required MCP Tool Updates**:

1. **Workspace Tool Enhancement**:
   - Accept JSON artifacts representing Python code structure
   - Use existing Jinja2 templates for file generation
   - Maintain .meta/ directory for file state tracking

2. **Validation Tool** (existing):
   - LLM can call validation directly
   - Returns structured error reports
   - Enables self-correction loops

3. **Git Tool** (existing):
   - LLM can commit changes when validation passes
   - Automated workflow completion

## Fibonacci Agent Example Workflow

```
1. Opus 4.1 → Claude Code: "Create Fibonacci implementation"

2. Claude Code → Creates FibonacciAgent + queues initial task

3. FibonacciAgent → Local LLM:
   "Create fibonacci function with proper error handling"

4. Local LLM → workspace_tool({
     "action": "write",
     "path": "fibonacci.py",
     "json_artifact": {
       "element_type": "function",
       "element_data": {
         "name": "fibonacci",
         "docstring": "Calculate nth Fibonacci number",
         "parameters": [{"name": "n", "type": "int", "default": null}],
         "return_type": "int",
         "body": "return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
       }
     }
   })

5. Workspace Tool → Renders fibonacci.py via python_file.j2 template

6. Local LLM → validation_tool({"file_path": "fibonacci.py"})

7. Validation Tool → Returns error: "Missing input validation"

8. Local LLM → workspace_tool(update fibonacci function with validation)

9. Local LLM → validation_tool({"file_path": "fibonacci.py"}) → Success

10. Local LLM → git_tool({"operation": "commit", "message": "Add fibonacci implementation"})

11. Agent completes task with structured success response
```

## Technical Implementation Details

### MCP Tool Exposure to Local LLM

**File**: `src/core/llm/llm_manager.py`

```python
class LLMManager:
    def __init__(self, mcp_tools: dict):
        self.mcp_tools = mcp_tools
        self.model_config = {
            "tools": self._format_tools_for_model(),
            "tool_choice": "auto"
        }

    def _format_tools_for_model(self) -> list:
        """Convert MCP tools to model-compatible format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "workspace",
                    "description": "Manage workspace files with JSON artifacts",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["read", "write", "create_dir"]},
                            "path": {"type": "string"},
                            "json_artifact": {"type": "object"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validation",
                    "description": "Validate code files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": ["tests", "file-length", "pre-commit"]},
                            "file_paths": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_operations",
                    "description": "Git operations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": ["status", "diff", "commit"]},
                            "message": {"type": "string"},
                            "files": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        ]

    async def generate_with_tools(self, prompt: str) -> dict:
        """Generate response with tool calling capability"""
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            tools=self.model_config["tools"],
            tool_choice=self.model_config["tool_choice"]
        )

        if response.choices[0].message.tool_calls:
            return {
                "type": "tool_calls",
                "tool_calls": response.choices[0].message.tool_calls
            }
        else:
            return {
                "type": "text",
                "content": response.choices[0].message.content
            }
```

### Agent Integration

**File**: `src/core/agents/agent/agent.py`

```python
async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
    """Handle code generation via MCP tools"""

    # Enhanced prompt for tool-based workflow
    prompt = f"""You are an expert Python developer working on {self.state.specialized_files[0]}.

Task: {request.message}

Use the available MCP tools to:
1. Create/update code using workspace tool with JSON artifacts
2. Validate your code using validation tool
3. Fix any issues and re-validate
4. Commit working code using git_operations tool

JSON artifact format for Python functions:
{{
  "element_type": "function",
  "element_data": {{
    "name": "function_name",
    "docstring": "Description",
    "parameters": [{{"name": "param", "type": "str", "default": null}}],
    "return_type": "str",
    "body": "return 'result'"
  }}
}}

Start by calling the workspace tool to implement the requested functionality."""

    # Generate with tool calling
    llm_response = await self.llm_manager.generate_with_tools(prompt)

    if llm_response["type"] == "tool_calls":
        # Execute tool calls through MCP
        for tool_call in llm_response["tool_calls"]:
            await self._execute_mcp_tool(tool_call)

        return AgentResponse(
            success=True,
            content=f"Code generation completed using MCP tools",
            agent_id=self.state.agent_id,
            task_type=request.task_type
        )
    else:
        # Fallback to text response
        return AgentResponse(
            success=False,
            content="LLM did not use tools as expected",
            agent_id=self.state.agent_id,
            task_type=request.task_type
        )

async def _execute_mcp_tool(self, tool_call) -> dict:
    """Execute MCP tool call from LLM"""
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)

    result = await self.tool_executor.execute_tool(tool_name, tool_args)

    # Log tool execution for monitoring
    logger.info(f"Tool {tool_name} executed: {result.get('success', False)}")

    return result
```

### Task Nesting Control

**File**: `src/core/agents/registry/task_queue.py`

```python
class TaskQueue:
    def __init__(self, max_nesting_depth: int = 3):
        self.max_nesting_depth = max_nesting_depth
        self.task_depth_tracking = {}

    async def queue_task(self, task: AgentTask, parent_task_id: str = None) -> str:
        """Queue task with nesting depth control"""

        if parent_task_id:
            parent_depth = self.task_depth_tracking.get(parent_task_id, 0)
            if parent_depth >= self.max_nesting_depth:
                raise ValueError(f"Maximum nesting depth {self.max_nesting_depth} exceeded")

            self.task_depth_tracking[task.task_id] = parent_depth + 1
        else:
            self.task_depth_tracking[task.task_id] = 0

        return await self._add_to_queue(task)
```

## Benefits of MCP-Based Approach

### 1. **Guaranteed Structure**
- No more JSON parsing failures
- No markdown wrapper issues
- 100% reliable tool-based communication

### 2. **Self-Correcting Workflows**
- LLM can validate its own output
- Automatic retry loops for failed validation
- Built-in error handling and recovery

### 3. **Consistent Code Quality**
- All code generated via proven Jinja2 templates
- Automatic type hints and docstring formatting
- Pre-commit hooks as final validation layer

### 4. **Scalable Architecture**
- Easy to add new MCP tools for additional capabilities
- Model-agnostic (works with any tool-calling LLM)
- Clean separation of concerns

### 5. **Minimal Existing Code Changes**
- Leverages existing MCP infrastructure
- Keeps async task queue system
- Maintains JSON file management system

## Migration Path

### Week 1: Core Infrastructure
- [ ] Enhance LLMManager with MCP tool definitions
- [ ] Update workspace tool to accept JSON artifacts
- [ ] Test basic tool calling with local LLM

### Week 2: Agent Integration
- [ ] Modify agent code generation logic
- [ ] Implement tool call execution pipeline
- [ ] Add task nesting depth controls

### Week 3: Testing & Validation
- [ ] End-to-end Fibonacci example testing
- [ ] PyChess agent orchestration testing
- [ ] Performance and reliability validation

### Week 4: Advanced Features
- [ ] Multi-file agent management (main + test files)
- [ ] Advanced workflow templates
- [ ] Monitoring and debugging tools

## Success Metrics

### Must Achieve:
- [ ] 100% reliable code generation (no parsing failures)
- [ ] LLM successfully uses MCP tools for file operations
- [ ] Agents can self-validate and self-correct code
- [ ] Task nesting controls prevent runaway recursion
- [ ] Generated code passes all validation checks

### Should Achieve:
- [ ] <500ms overhead for tool-based vs direct generation
- [ ] Agents complete complex multi-step workflows autonomously
- [ ] Clear audit trail of all MCP tool calls
- [ ] Easy debugging and monitoring of agent behavior

## Current System Preservation

**Keep Working**:
- Async task queue (excellent foundation)
- JSON file management with Jinja2 templates
- MCP tool infrastructure (workspace, validation, git)
- Agent specialization and registry
- Docker containerization

**Replace**:
- Text-based LLM responses → Tool-based responses
- Manual JSON parsing → Structured tool calls
- Error-prone text processing → Guaranteed tool semantics

## Risk Mitigation

### Technical Risks:
- **Local LLM tool calling support**: Test extensively with Qwen2.5-7B
- **Performance overhead**: Benchmark tool calls vs direct generation
- **Tool call complexity**: Start with simple tools, add complexity gradually

### Mitigation Strategies:
- **Hybrid approach**: Support both tool calls and text fallback initially
- **Comprehensive testing**: Tool calling capability validation before rollout
- **Gradual migration**: One agent type at a time
- **Rollback plan**: Keep existing text-based system as backup

## Conclusion

This MCP-based architecture eliminates the root cause of JSON parsing issues while leveraging the excellent infrastructure already built. It represents a clean, scalable solution that aligns with modern LLM capabilities and provides the reliability needed for production use.

The shift from "prompt and parse" to "prompt and execute tools" is the key insight that will unlock the full potential of the agent system while maintaining all existing strengths.