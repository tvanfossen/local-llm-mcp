# Agent Operations Debug and Fix Plan

## Executive Summary
The local model is not properly integrated with MCP tools due to missing bridge infrastructure, excessive fallback mechanisms, and improper task sequencing. The agent is directly creating output files instead of following the intended metadata → tool call → validation → commit workflow.

## Critical Issues Identified

### 1. Missing MCP Bridge for Local Model
**Problem**: Local model has no mechanism to parse and execute MCP tool calls
**Impact**: Model cannot use available MCP tools
**Location**: Missing `src/core/mcp/bridge/` module

### 2. Direct File Creation Instead of Metadata
**Problem**: Agent directly writes output files instead of JSON metadata
**Impact**: Bypasses intended workflow and context control
**Location**: `src/core/agents/agent/agent.py:_handle_code_generation()`

### 3. Excessive Fallbacks and Mocks
**Problem**: Too many placeholder responses hiding real failures
**Impact**: No traceability, silent failures
**Locations**: Multiple files with "not yet implemented" returns

### 4. Task Queue Not Properly Integrated
**Problem**: MCP tools not routed through async queue
**Impact**: Synchronous execution, no nesting control
**Location**: `src/mcp/tools/executor/executor.py`

---

## Phase 1: Create MCP Bridge Infrastructure
**Priority**: CRITICAL
**Files to Create**: New module for local model tool calling

### 1.1 Create `src/core/mcp/bridge/bridge.py`
```python
"""MCP Bridge for Local Model Tool Calling"""

class MCPBridge:
    def __init__(self, task_queue, tool_executor):
        self.task_queue = task_queue
        self.tool_executor = tool_executor
        
    async def parse_and_execute(self, model_output: str):
        """Parse model output for tool calls and queue them"""
        # Extract tool calls from model output
        # Queue tool calls through task system
        # Return formatted results
```

### 1.2 Create `src/core/mcp/bridge/parser.py`
```python
"""Tool Call Parser for Local Model Output"""

class ToolCallParser:
    def extract_tool_calls(self, text: str):
        """Extract JSON tool calls from model output"""
        # Handle various formats (JSON blocks, etc)
        # Validate tool call structure
        # Return list of tool calls
```

### 1.3 Update `src/core/llm/manager/manager.py`
- Add MCP bridge integration
- Include tool definitions in prompts
- Parse responses for tool calls

---

## Phase 2: Fix Agent Metadata Workflow
**Priority**: HIGH
**Fix**: Agent creates JSON metadata, not direct files

### 2.1 Fix `src/core/agents/agent/agent.py`

**Current Problem** (Line ~336):
```python
async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
    # WRONG: Creates direct workspace tool prompt
    code_gen_prompt = f"""...
    CRITICAL: You must use explicit tool calls to complete this task.
    """
```

**Fix**:
```python
async def _handle_code_generation(self, request: AgentRequest) -> AgentResponse:
    """Generate JSON metadata for code structure"""
    # 1. Create JSON representation using JsonFileManager
    # 2. Save to .meta/{filename}.json
    # 3. Queue workspace tool to render actual file
    # 4. Queue validation tool
    # 5. Queue git commit if successful
```

### 2.2 Create `src/core/agents/agent/metadata_handler.py`
```python
"""Handle metadata generation for agent files"""

class MetadataHandler:
    def generate_initial_metadata(self, request, filename):
        """Generate initial JSON metadata for file"""
        # Parse request for code requirements
        # Create structured JSON representation
        # Return metadata for .meta/ directory
```

---

## Phase 3: Remove Fallbacks and Add Proper Error Handling
**Priority**: HIGH
**Fix**: Replace mocks with real implementations or explicit failures

### 3.1 Remove Placeholder Returns

**Files to Fix**:
- `src/core/agents/agent/agent.py` - Remove "not yet implemented" responses
- `src/mcp/tools/workspace/workspace.py` - Add actual file operations
- `src/mcp/tools/validation/validation.py` - Implement real validation

**Pattern to Remove**:
```python
return AgentResponse(
    success=True,
    content="Generic file operation not yet implemented",
    ...
)
```

**Replace With**:
```python
return AgentResponse(
    success=False,
    content=f"Failed: {specific_error_message}",
    metadata={"error_type": "unimplemented", "required_tool": tool_name}
)
```

### 3.2 Add Traceable Logging
- Log all tool call attempts with full payloads
- Log queue operations with task IDs
- Log metadata creation/updates
- Add entry/exit logging for every method

---

## Phase 4: Implement Async Task Queue for All MCP Operations
**Priority**: CRITICAL
**Fix**: Route ALL tool calls through queue with nesting limits

### 4.1 Create `src/core/tasks/queue/queue.py`
```python
"""Generic task queue with nesting depth control"""

class TaskQueue:
    def __init__(self, max_depth=3):
        self.max_depth = max_depth
        self.task_depth = {}  # task_id -> depth
        self.parent_map = {}  # task_id -> parent_id
        
    async def queue_task(self, task, parent_id=None):
        """Queue task with depth tracking"""
        if parent_id:
            parent_depth = self.task_depth.get(parent_id, 0)
            if parent_depth >= self.max_depth:
                raise MaxDepthExceeded(f"Cannot nest beyond {self.max_depth}")
            self.task_depth[task.id] = parent_depth + 1
```

### 4.2 Update `src/mcp/tools/executor/executor.py`
**Remove**: Direct tool execution
**Add**: Queue submission for every tool call

```python
async def execute_tool(self, tool_name, args):
    """Queue tool for async execution"""
    task = ToolCallTask(tool_name, args)
    task_id = await self.task_queue.queue_task(task)
    return await self.task_queue.await_result(task_id)
```

---

## Phase 5: File-by-File Review and Logging Enhancement
**Priority**: HIGH
**Approach**: Systematic review with NO FALLBACKS

### 5.1 `src/core/agents/agent/agent.py` Review

**Current Issues**:
- Line 96: `_handle_code_generation` creates workspace prompt instead of metadata
- Line 421: `_handle_file_creation` returns "not yet implemented"
- Line 431: `_handle_file_read` returns "not yet implemented"  
- Line 490: `_analyze_and_execute_file_operation` returns "not yet implemented"

**Required Changes**:
```python
# Add comprehensive logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Every method entry/exit
async def _handle_code_generation(self, request):
    self.logger.debug(f"ENTRY _handle_code_generation: request={request}")
    
    try:
        # NO FALLBACK - fail if can't create metadata
        if not self.json_file_manager:
            error = "JsonFileManager not initialized"
            self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
            return AgentResponse(success=False, content=error, ...)
            
        # Create metadata
        self.logger.info(f"Creating metadata for {filename}")
        metadata = await self._create_file_metadata(request)
        
        if not metadata:
            error = "Failed to create metadata structure"
            self.logger.error(f"EXIT _handle_code_generation: FAILED - {error}")
            return AgentResponse(success=False, content=error, ...)
            
        # Save to .meta/
        meta_path = self.system_config.workspace_root / ".meta" / f"{filename}.json"
        self.logger.info(f"Saving metadata to {meta_path}")
        
        # Queue workspace tool
        self.logger.info(f"Queueing workspace tool for {filename}")
        task_id = await self._queue_workspace_write(metadata)
        
        self.logger.debug(f"EXIT _handle_code_generation: SUCCESS - task_id={task_id}")
        return AgentResponse(success=True, content=f"Queued task {task_id}", ...)
        
    except Exception as e:
        self.logger.exception(f"EXIT _handle_code_generation: EXCEPTION - {e}")
        return AgentResponse(success=False, content=str(e), ...)
```

### 5.2 `src/mcp/tools/workspace/workspace.py` Review

**Current Issues**:
- Missing metadata-based file generation
- No integration with template system
- Insufficient logging

**Required Changes**:
```python
async def write_from_metadata(self, args):
    """Write file from JSON metadata"""
    logger.debug(f"ENTRY write_from_metadata: args={args}")
    
    filepath = args.get("filepath")
    if not filepath:
        error = "No filepath provided"
        logger.error(f"EXIT write_from_metadata: FAILED - {error}")
        return {"success": False, "error": error}
    
    # Load metadata
    meta_path = Path(self.workspace_root) / ".meta" / f"{filepath}.json"
    logger.info(f"Loading metadata from {meta_path}")
    
    if not meta_path.exists():
        error = f"No metadata found at {meta_path}"
        logger.error(f"EXIT write_from_metadata: FAILED - {error}")
        return {"success": False, "error": error}
    
    try:
        with open(meta_path) as f:
            metadata = json.load(f)
        logger.debug(f"Loaded metadata: {metadata.keys()}")
    except Exception as e:
        error = f"Failed to load metadata: {e}"
        logger.exception(f"EXIT write_from_metadata: FAILED - {error}")
        return {"success": False, "error": error}
    
    # NO FALLBACK - fail if template missing
    template_name = metadata.get("template", "python_file.j2")
    if not (Path("templates") / template_name).exists():
        error = f"Template {template_name} not found"
        logger.error(f"EXIT write_from_metadata: FAILED - {error}")
        return {"success": False, "error": error}
    
    # Render and write
    # ... actual implementation
    logger.debug(f"EXIT write_from_metadata: SUCCESS")
```

### 5.3 `src/core/agents/registry/registry.py` Review

**Current Issues**:
- Task execution doesn't check for tool availability
- No depth limiting on task creation

**Required Changes**:
```python
async def execute_agent_task(self, task_id: str):
    """Execute queued agent task with proper limits"""
    logger.debug(f"ENTRY execute_agent_task: task_id={task_id}")
    
    task = self.task_queue.get_task(task_id)
    if not task:
        error = f"Task {task_id} not found"
        logger.error(f"EXIT execute_agent_task: FAILED - {error}")
        raise TaskNotFound(error)
    
    # Check nesting depth
    depth = self._get_task_depth(task_id)
    logger.info(f"Task {task_id} at depth {depth}")
    
    if depth >= self.MAX_NESTING_DEPTH:
        error = f"Max nesting depth {self.MAX_NESTING_DEPTH} exceeded"
        logger.error(f"EXIT execute_agent_task: FAILED - {error}")
        task.status = "failed"
        task.error = error
        return
    
    # NO FALLBACK - fail if agent missing
    agent = self.agents.get(task.agent_id)
    if not agent:
        error = f"Agent {task.agent_id} not found"
        logger.error(f"EXIT execute_agent_task: FAILED - {error}")
        task.status = "failed"
        task.error = error
        return
```

### 5.4 `src/mcp/tools/agent_operations/agent_operations.py` Review

**Current Issues**:
- Line 97: `specialized_files` type confusion
- Missing async task queue integration

**Required Changes**:
```python
elif operation == "create":
    logger.debug(f"ENTRY create operation: args={args}")
    
    # NO TYPE GUESSING - fail if wrong type
    specialized_files = args.get("specialized_files", [])
    if not isinstance(specialized_files, list):
        error = f"specialized_files must be list, got {type(specialized_files)}"
        logger.error(f"EXIT create operation: FAILED - {error}")
        return create_mcp_response(False, error)
    
    # Validate each file
    for file in specialized_files:
        if not isinstance(file, str):
            error = f"Each file must be string, got {type(file)} for {file}"
            logger.error(f"EXIT create operation: FAILED - {error}")
            return create_mcp_response(False, error)
    
    # Create agent with task queue
    logger.info(f"Creating agent {name} for files {specialized_files}")
    try:
        agent_id = await self._create_agent_with_queue(name, description, specialized_files)
        
        # Queue initial metadata task
        task = AgentTask(
            agent_id=agent_id,
            operation="create_initial_metadata",
            files=specialized_files
        )
        task_id = await self.task_queue.queue_task(task)
        
        logger.debug(f"EXIT create operation: SUCCESS - agent_id={agent_id}, task_id={task_id}")
        return create_mcp_response(True, f"Created agent {agent_id}, queued task {task_id}")
        
    except Exception as e:
        logger.exception(f"EXIT create operation: EXCEPTION - {e}")
        return create_mcp_response(False, str(e))
```

---

## Phase 6: Local Model Tool Calling Sequence
**Priority**: CRITICAL
**Fix**: Enable proper tool calling flow

### 6.1 Update `src/core/llm/manager/manager.py`

```python
async def generate_with_tools(self, prompt: str, enable_tools=True):
    """Generate with tool calling support"""
    logger.debug(f"ENTRY generate_with_tools: enable_tools={enable_tools}")
    
    if not self.model:
        error = "Model not loaded"
        logger.error(f"EXIT generate_with_tools: FAILED - {error}")
        raise ModelNotLoaded(error)
    
    # Add tool definitions to prompt
    if enable_tools and self.mcp_bridge:
        tool_prompt = self.mcp_bridge.get_tool_prompt()
        full_prompt = f"{tool_prompt}\n\n{prompt}"
        logger.debug(f"Added {len(self.mcp_bridge.tools)} tool definitions")
    else:
        full_prompt = prompt
    
    # Generate response
    logger.info("Generating model response")
    response = self.model(full_prompt, max_tokens=512)
    
    # Parse for tool calls
    if enable_tools and self.mcp_bridge:
        logger.info("Parsing response for tool calls")
        tool_calls = await self.mcp_bridge.parse_and_execute(response['choices'][0]['text'])
        
        if tool_calls:
            logger.info(f"Found {len(tool_calls)} tool calls")
            # Queue each tool call
            for call in tool_calls:
                task_id = await self._queue_tool_call(call)
                logger.debug(f"Queued tool call {call['name']} as task {task_id}")
    
    logger.debug(f"EXIT generate_with_tools: SUCCESS")
    return response
```

---

## Phase 7: Complete File Review List
**Priority**: HIGH  
**Approach**: Every file needs explicit failure handling and verbose logging

### Files Requiring Complete Review and Fixes:

#### Core Agent Files
- `src/core/agents/agent/agent.py` - Remove ALL "not yet implemented" returns
- `src/core/agents/registry/registry.py` - Add task depth checking, remove fallbacks
- `src/core/agents/registry/task_queue.py` - Extract to generic module, add depth limits

#### MCP Tool Files  
- `src/mcp/tools/executor/executor.py` - Route ALL through queue, no direct execution
- `src/mcp/tools/agent_operations/agent_operations.py` - Fix type handling, add queue integration
- `src/mcp/tools/workspace/workspace.py` - Implement metadata-based writing, remove mocks
- `src/mcp/tools/validation/validation.py` - Real validation only, fail if not implemented
- `src/mcp/tools/local_model/local_model.py` - Add tool calling support

#### LLM Manager
- `src/core/llm/manager/manager.py` - Add MCP bridge, tool prompts, response parsing

#### Configuration
- `src/core/config/manager/manager.py` - Add MCP bridge configuration

#### New Files to Create
- `src/core/mcp/bridge/bridge.py` - Main bridge implementation  
- `src/core/mcp/bridge/parser.py` - Tool call extraction
- `src/core/mcp/bridge/formatter.py` - Tool prompt formatting
- `src/core/tasks/queue/queue.py` - Generic task queue
- `src/core/tasks/queue/task.py` - Task definitions
- `src/core/agents/agent/metadata_handler.py` - JSON metadata generation

---

## Critical Code Patterns to Remove

### Pattern 1: Placeholder Returns
```python
# REMOVE THIS PATTERN:
return AgentResponse(
    success=True,  # WRONG - lying about success
    content="Not yet implemented",
    ...
)

# REPLACE WITH:
return AgentResponse(
    success=False,  
    content=f"Operation {operation_name} not implemented",
    metadata={"error_type": "not_implemented", "operation": operation_name}
)
```

### Pattern 2: Silent Fallbacks
```python
# REMOVE THIS PATTERN:
try:
    result = some_operation()
except:
    result = default_value  # WRONG - hiding failure

# REPLACE WITH:
try:
    result = some_operation()
except Exception as e:
    logger.exception(f"Operation failed: {e}")
    raise OperationFailed(f"Failed to {operation_name}: {e}")
```

### Pattern 3: Type Guessing
```python
# REMOVE THIS PATTERN:
if isinstance(value, str):
    value = [value]  # WRONG - guessing intent
elif not isinstance(value, list):
    value = []  # WRONG - making up data

# REPLACE WITH:
if not isinstance(value, list):
    raise TypeError(f"Expected list, got {type(value)}: {value}")
```

---

## Logging Standards

### Entry/Exit Pattern for Every Method
```python
async def any_method(self, param1, param2):
    logger.debug(f"ENTRY {self.__class__.__name__}.any_method: param1={param1}, param2={param2}")
    
    try:
        # Method logic
        result = await do_something()
        logger.debug(f"EXIT {self.__class__.__name__}.any_method: SUCCESS - result={result}")
        return result
        
    except Exception as e:
        logger.exception(f"EXIT {self.__class__.__name__}.any_method: EXCEPTION - {e}")
        raise
```

### State Change Logging
```python
# Log before and after state changes
logger.info(f"State change: {field} {old_value} -> {new_value}")
```

### Tool Call Logging
```python
logger.info(f"Tool call: {tool_name} with args: {json.dumps(args, indent=2)}")
logger.info(f"Tool response: {json.dumps(response, indent=2)}")
```

---

## Error Handling Requirements

### No Empty Catches
```python
# NEVER DO THIS:
except:
    pass

# ALWAYS DO THIS:
except Exception as e:
    logger.exception(f"Unexpected error in {context}: {e}")
    raise
```

### Specific Error Types
```python
class AgentNotFound(Exception):
    """Raised when agent ID doesn't exist"""

class TaskQueueFull(Exception):
    """Raised when task queue at capacity"""

class MaxDepthExceeded(Exception):
    """Raised when task nesting too deep"""

class MetadataInvalid(Exception):
    """Raised when JSON metadata malformed"""

class ToolNotAvailable(Exception):
    """Raised when requested tool not registered"""
```

### Error Response Format
```python
{
    "success": False,
    "error": "Human readable error message",
    "error_type": "specific_error_code",
    "metadata": {
        "file": __file__,
        "function": function_name,
        "line": line_number,
        "context": additional_context
    }
}
```

---

## Summary of Key Changes

1. **NO FALLBACKS** - Every operation either succeeds or returns explicit failure
2. **METADATA FIRST** - Agents create JSON metadata, not direct files  
3. **QUEUE EVERYTHING** - All MCP tool calls go through async queue
4. **DEPTH LIMITS** - Maximum 3 levels of task nesting (configurable)
5. **VERBOSE LOGGING** - Entry/exit for every method, state changes logged
6. **EXPLICIT ERRORS** - Specific exception types, no silent failures
7. **TOOL INTEGRATION** - Local model gets MCP bridge for proper tool calling
8. **TRACEABLE FLOW** - Can follow entire execution path through logs