# QUEUE UNIFICATION WORKPLAN - September 17, 2025

## Objective
Unify the dual queue architecture (AgentTaskExecutor + ToolCallExecutor) into a single, coherent task queue system that handles both agent tasks and tool calls seamlessly.

## Current Problem Analysis

### Current Architecture Issues
1. **Dual Queue Complexity**:
   - `AgentTaskExecutor` in `src/core/agents/registry/task_queue.py`
   - `ToolCallExecutor` in `src/core/tasks/queue/queue.py`
   - Both process different task types with separate logic

2. **Tool Executor Configuration**:
   - Tool calls fail with "Tool executor not configured"
   - Configuration not properly propagated through queue hierarchy

3. **MCP Bridge Queue Access**:
   - Bridge bypasses agent queue wrapper: `self.task_queue._task_queue.queue_task(task)`
   - Creates inconsistent routing paths

## Proposed Solution: Unified Task Queue

### Phase 1: Consolidate Executor Logic
**Goal**: Merge AgentTaskExecutor and ToolCallExecutor into a single UnifiedTaskExecutor

**Actions**:
1. Create `src/core/tasks/queue/unified_executor.py`
2. Implement `UnifiedTaskExecutor` that handles both task types:
   - `AgentTask` ’ Route to agent processing
   - `ToolCallTask` ’ Route to tool execution
3. Remove duplicate logic from both existing executors
4. Ensure tool executor is properly configured in unified approach

### Phase 2: Simplify Queue Architecture
**Goal**: Replace dual queue system with single queue

**Actions**:
1. Update `src/core/agents/registry/registry.py`:
   - Remove TaskQueue wrapper entirely
   - Use generic TaskQueue directly with UnifiedTaskExecutor
2. Update MCP Bridge in `src/core/mcp/bridge/bridge.py`:
   - Remove `._task_queue` access workaround
   - Use direct queue access: `self.task_queue.queue_task(task)`
3. Register UnifiedTaskExecutor for all task types in generic queue

### Phase 3: Update Initialization Chain
**Goal**: Ensure tool executor reaches all components

**Actions**:
1. Update server initialization in `local_llm_mcp_server.py`:
   - Pass tool_executor directly to agent registry
   - Ensure tool_executor is available for UnifiedTaskExecutor
2. Update agent registry initialization:
   - Pass tool_executor to generic TaskQueue
   - Register UnifiedTaskExecutor with tool_executor

### Phase 4: Fix Metadata Population
**Goal**: Ensure metadata files have actual content before tool calls

**Actions**:
1. Update agent code generation in `src/core/agents/agent/agent.py`:
   - Populate metadata content field before making tool calls
   - Ensure `.meta/*.json` files contain actual code content

## Implementation Steps

### Step 1: Create UnifiedTaskExecutor
```python
# src/core/tasks/queue/unified_executor.py
class UnifiedTaskExecutor(TaskExecutor):
    def __init__(self, agent_registry=None, tool_executor=None):
        self.agent_registry = agent_registry
        self.tool_executor = tool_executor

    async def execute(self, task: Task):
        if isinstance(task, AgentTask):
            # Handle agent tasks (existing AgentTaskExecutor logic)
            return await self._execute_agent_task(task)
        elif isinstance(task, ToolCallTask):
            # Handle tool calls (existing ToolCallExecutor logic)
            return await self._execute_tool_call(task)
        else:
            raise ValueError(f"Unknown task type: {type(task)}")
```

### Step 2: Update Generic Queue
```python
# src/core/tasks/queue/queue.py - _execute_task method
async def _execute_task(self, task: Task):
    # Remove special case handling
    # Use unified executor for all tasks
    executor = self._executors.get("unified")
    if not executor:
        raise ValueError("Unified executor not registered")
    await executor.execute(task)
```

### Step 3: Update Agent Registry
```python
# src/core/agents/registry/registry.py
def __init__(self, config_manager: ConfigManager, llm_manager=None, tool_executor=None):
    # Remove TaskQueue wrapper - use generic queue directly
    self.task_queue = GenericTaskQueue(max_tasks=100, tool_executor=tool_executor)

    # Register unified executor
    unified_executor = UnifiedTaskExecutor(agent_registry=self, tool_executor=tool_executor)
    self.task_queue.register_executor("unified", unified_executor)
```

### Step 4: Update MCP Bridge
```python
# src/core/mcp/bridge/bridge.py
async def _execute_tool_call_queued(self, tool_name: str, arguments: Dict[str, Any], parent_task_id: Optional[str] = None):
    # Remove ._task_queue workaround
    task_id = self.task_queue.queue_task(task)  # Direct access
```

## Expected Outcomes

###  Benefits
1. **Simplified Architecture**: Single queue handles all task types
2. **Consistent Routing**: All tasks use same execution path
3. **Proper Tool Executor Configuration**: Tool executor accessible to all components
4. **Reduced Complexity**: Eliminate dual queue management
5. **Better Maintainability**: Single source of truth for task execution

### <¯ Success Metrics
1. **Tool Calls Execute Successfully**: No more "Tool executor not configured"
2. **Files Created**: `main.py` appears in output directory
3. **Metadata Populated**: `.meta/main.py.json` contains actual code content
4. **Unified Logging**: All tasks show consistent execution patterns
5. **Queue Integration**: Both agent and tool tasks use same queue seamlessly

## Testing Plan

### Test 1: Agent Task Execution
```bash
queue_task agent_id="a83ffa50" message="Generate your main.py file" task_type="code_generation"
```
**Expected**: Agent task routes through unified executor successfully

### Test 2: Tool Call Execution
**Expected**: Tool calls execute without timeout, files created in output directory

### Test 3: Metadata Verification
**Expected**: `.meta/main.py.json` contains populated content field with actual code

### Test 4: End-to-End Workflow
**Expected**: Complete workflow from agent ’ LLM ’ tool calls ’ file creation works seamlessly

---

## Implementation Priority: HIGH
**Rationale**: This fixes the core architectural issue blocking successful tool execution and eliminates unnecessary complexity that has caused configuration propagation problems.