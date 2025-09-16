# Local LLM MCP Tool Calling Integration Workplan

## Overview
Enable the local Qwen2.5-7B model to reliably make MCP tool calls with strict JSON formatting, routing all tool operations through an async task queue for consistent structured responses.

---

## Phase 1: Extract and Reorganize Task Queue Infrastructure
**Goal**: Separate task queue into generic module for broader use beyond agents

### Files to Create:

#### `src/core/tasks/queue/queue.py`
- Extract `TaskQueue` class from `src/core/agents/registry/task_queue.py`
- Make generic to handle any async operation type
- Add support for tool call tasks alongside agent tasks
- Maintain backward compatibility with existing agent registry

#### `src/core/tasks/queue/task.py`
- Define generic `Task` base class
- Keep `AgentTask` as subclass for compatibility
- Add `ToolCallTask` for MCP tool operations
- Include task lifecycle management (queued, running, completed, failed)

#### `src/core/tasks/queue/__init__.py`
- Export main classes and enums
- Maintain same interface as current implementation

### Key Changes:
- Rename task types to be more generic
- Add priority queue support for critical tool calls
- Keep existing agent functionality intact

---

## Phase 2: Create MCP Bridge for Local Model
**Goal**: Build dedicated bridge between local LLM and MCP tools with JSON validation

### Files to Create:

#### `src/core/mcp/bridge/tool_parser.py`
Adapt from society_scribe's `ToolCallParser`:
```python
- Multiple parsing strategies (JSON fence, XML tags, bare JSON)
- Smart quote and trailing comma sanitization
- Balanced brace detection for partial JSON
- Tool call signature tracking to prevent duplicates
```

#### `src/core/mcp/bridge/formatter.py`
- Strict JSON schema validation
- Tool-specific formatting templates
- Qwen2.5-specific output patterns
- Compact payload formatting for responses

#### `src/core/mcp/bridge/bridge.py`
Main bridge implementation:
- Tool call extraction from LLM output
- Validation and retry logic
- Queue integration for all tool calls
- Result formatting for model consumption

### Critical Features to Port:
1. **From society_scribe `ToolCallParser`**:
   - `TOOL_FENCE_RE` regex for code blocks
   - `TOOL_TAG_RE` for XML-style tags  
   - Smart quotes replacement
   - Trailing comma removal

2. **From society_scribe `MessageProcessor`**:
   - Compact tool payload representation
   - Result truncation for context limits
   - Tool-specific helper messages

---

## Phase 3: Enhance LLMManager for Tool Calling
**Goal**: Update LLMManager to support structured tool calling

### File to Modify: `src/core/llm/manager/manager.py`

#### Add Tool Support:
```python
def __init__(self, model_config=None, mcp_bridge=None):
    self.mcp_bridge = mcp_bridge
    self.tool_definitions = []
    
def register_tools(self, tools):
    """Register MCP tools for model use"""
    self.tool_definitions = self._format_tools_for_qwen(tools)
    
def generate_with_tools(self, prompt, tools_enabled=True):
    """Generate response with tool calling capability"""
    # Add tool definitions to prompt
    # Parse response for tool calls
    # Execute through MCP bridge
```

#### Tool Prompt Formatting:
- Create Qwen-specific tool instruction format
- Include clear JSON examples in system prompt
- Add tool call indicators for parser

---

## Phase 4: Tool Call Router Implementation
**Goal**: Route all MCP tool calls through async task queue

### Files to Create:

#### `src/core/mcp/router/router.py`
- Central routing for all tool calls
- Queue submission and result tracking
- Priority handling for validation/git operations
- Timeout management

#### `src/core/mcp/router/executor.py`
- Async execution of queued tool calls
- Error handling and retry logic
- Result caching for repeated calls
- Performance monitoring

### Integration Points:
1. **With Task Queue**: Submit tool calls as tasks
2. **With MCP Bridge**: Parse and validate calls
3. **With Agents**: Allow agents to monitor tool execution
4. **With Tool Executor**: Route to actual MCP tools

---

## Phase 5: Agent Integration Updates
**Goal**: Update agents to use new tool calling infrastructure

### File to Modify: `src/core/agents/agent/agent.py`

#### Key Changes:
```python
async def process_request(self, request):
    # Remove text parsing logic
    # Use LLMManager.generate_with_tools()
    # Monitor tool call results through queue
    # Let model self-correct via tool calls
```

#### Remove:
- Manual JSON extraction from markdown
- Complex text parsing utilities
- Error-prone string manipulation

#### Add:
- Tool call monitoring
- Structured result handling
- Self-correction loops via tools

---

## Phase 6: Tool Enhancement for Code Generation
**Goal**: Update workspace tool to accept JSON artifacts

### File to Modify: `src/mcp/tools/workspace/workspace.py`

#### Add JSON Artifact Support:
```python
def write_with_artifact(self, path, json_artifact):
    """Write file using JSON artifact and Jinja2 template"""
    # Determine template based on artifact type
    # Render using existing template system
    # Maintain .meta/ tracking
```

#### Artifact Schema:
```json
{
  "element_type": "function|class|module",
  "element_data": {
    "name": "...",
    "docstring": "...",
    "parameters": [...],
    "body": "..."
  }
}
```

---

## Implementation Order & Dependencies

### Week 1:
1. **Phase 1**: Extract task queue (no dependencies)
2. **Phase 2**: Create MCP bridge (depends on Phase 1)

### Week 2:
3. **Phase 3**: Enhance LLMManager (depends on Phase 2)
4. **Phase 4**: Implement tool router (depends on Phases 1-3)

### Week 3:
5. **Phase 5**: Update agents (depends on Phases 3-4)
6. **Phase 6**: Enhance workspace tool (can be parallel)

---

## Critical Success Factors

### Must Preserve:
- Existing agent registry functionality
- Current task queue for agent operations
- All MCP tool interfaces
- JSON file management system
- Docker containerization

### Must Achieve:
- 100% reliable JSON parsing from local model
- All tool calls routed through task queue
- No regression in existing agent behavior
- Clean separation of concerns
- Proper error handling and recovery

### Key Metrics:
- Zero JSON parsing failures
- < 100ms overhead for tool routing
- Successful self-correction loops
- No task queue bottlenecks

---

## Risk Mitigation

### Compatibility Risks:
- **Task Queue Changes**: Keep original interface intact
- **Agent Updates**: Gradual migration, one agent at a time
- **Tool Calling**: Support both old and new patterns initially

### Technical Risks:
- **Qwen JSON Output**: Multiple parsing strategies
- **Queue Performance**: Add priority levels
- **Tool Timeouts**: Implement circuit breakers

### Rollback Strategy:
- Feature flag for new tool calling
- Keep text parsing as fallback
- Parallel operation during transition

---

## Notes from Reference Implementation

The society_scribe implementation provides valuable patterns:

1. **Tool Call Extraction**: Multiple regex patterns catch different formats
2. **Duplicate Prevention**: Track recent calls to avoid loops
3. **Compact Payloads**: Truncate tool results for context efficiency
4. **Helper Messages**: Guide model toward completion after tool use
5. **Safety Stops**: Limit tool call hops to prevent runaway execution

These patterns should be adapted for our architecture while maintaining our existing strengths in task queuing and agent management.