# Agent Interface Unification Workflow - HTML as MCP Client

**Objective**: Convert HTML orchestrator to send JSON-RPC requests to `/mcp` endpoint, making it identical to Claude Code integration.

**Current Problem**: HTML uses HTTP endpoints while Claude Code uses MCP tools, causing behavior discrepancies.

**Target Architecture**:
```
HTML Interface → JSON-RPC to /mcp → MCP Tools → Core Agent Logic
Claude Code → JSON-RPC to /mcp → MCP Tools → Core Agent Logic
                    ↑
              IDENTICAL PATH
```

**Key Principle**: HTML becomes another MCP client - no special endpoints, no duplication.

---

## Phase 1: MCP Tool Inventory & HTML Mapping

**Responsible Agent**: MCP Analysis Agent

**Files to Provide**:
- `api/mcp_handler.py`
- `static/orchestrator.html`
- `api/endpoints.py`
- `schemas/agent_schemas.py`

**Agent Prompt**:
```
You are an MCP protocol expert. Analyze existing MCP tools and map HTML interface calls to equivalent MCP tool calls.

TASKS:
1. Document all MCP tools in mcp_handler.py with their exact JSON-RPC signatures
2. Analyze all JavaScript API calls in orchestrator.html that use /api/agents/*
3. Create exact mapping from HTTP calls to MCP tool calls
4. Document required JavaScript changes for JSON-RPC format
5. Identify authentication/session handling changes needed
6. Plan response format conversion in JavaScript

OUTPUT: Create `docs/html_to_mcp_mapping.md` with:
- Complete MCP tool inventory with JSON-RPC examples
- HTTP call → MCP tool mapping table
- Required JavaScript function changes
- Authentication strategy for MCP calls
- Error handling changes needed
- Response parsing changes required

MAPPING EXAMPLES:
```
HTTP: POST /api/agents {name: "test", ...}
MCP:  POST /mcp {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "create_agent", "arguments": {...}}}

HTTP: GET /api/agents
MCP:  POST /mcp {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "list_agents", "arguments": {}}}
```

CRITICAL REQUIREMENTS:
- Every HTML operation must map to existing MCP tool
- No new MCP tools should be needed
- Authentication must work with MCP protocol
- UI behavior must remain identical
```

---

## Phase 2: HTML JavaScript MCP Conversion

**Responsible Agent**: Frontend MCP Integration Agent

**Files to Provide**:
- `docs/html_to_mcp_mapping.md` (from Phase 1)
- `static/orchestrator.html`
- `api/mcp_handler.py`

**Agent Prompt**:
```
You are a frontend MCP integration expert. Convert all HTML JavaScript to use JSON-RPC MCP calls instead of HTTP API calls.

TASKS:
1. Replace ALL /api/agents/* calls with JSON-RPC calls to /mcp
2. Implement proper JSON-RPC 2.0 request formatting
3. Update response parsing to handle JSON-RPC result format
4. Maintain identical UI behavior and error handling
5. Update authentication to work with MCP protocol
6. Keep orchestrator.html under 300 lines (split into files if needed)

CONVERSION PATTERN:
```javascript
// OLD HTTP API:
async function createAgent(data) {
    const response = await fetch('/api/agents', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    return await response.json();
}

// NEW MCP JSON-RPC:
async function createAgent(data) {
    const response = await fetch('/mcp', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            "jsonrpc": "2.0",
            "id": Date.now(),
            "method": "tools/call",
            "params": {
                "name": "create_agent",
                "arguments": data
            }
        })
    });
    const jsonrpc = await response.json();
    return jsonrpc.result;
}
```

ALL FUNCTIONS TO CONVERT:
- refreshAgents() → list_agents MCP tool
- createAgent() → create_agent MCP tool
- chatWithAgent() → chat_with_agent MCP tool
- getAgentFile() → get_agent_file MCP tool
- deleteAgent() → delete_agent MCP tool
- executeAction() → various MCP tools based on action type
- All queue processing functions → corresponding MCP tools

REQUIREMENTS:
- Exact same UI functionality
- Same error messages and handling
- Authentication via session tokens (in headers or MCP params)
- WebSocket functionality preserved
- All agent operations go through MCP tools
- No fallback to HTTP endpoints

RESPONSE HANDLING:
- Extract result from JSON-RPC response
- Handle JSON-RPC errors appropriately
- Convert MCP tool responses to expected UI format
- Maintain same error display in terminal
```

---

## Phase 3: HTTP Endpoints Removal

**Responsible Agent**: Endpoint Cleanup Agent

**Files to Provide**:
- `static/orchestrator.html` (updated from Phase 2)
- `api/endpoints.py`
- `api/http_server.py`
- `api/mcp_handler.py`

**Agent Prompt**:
```
You are a cleanup specialist. Remove all unnecessary HTTP agent endpoints since HTML now uses MCP tools.

TASKS:
1. Remove ALL /api/agents/* endpoints from endpoints.py
2. Remove APIEndpoints class methods for agent operations
3. Update http_server.py to remove deleted endpoint routes
4. Keep only non-agent endpoints (system status, health, etc.)
5. Verify no code references deleted endpoints
6. Clean up imports and unused code

ENDPOINTS TO DELETE:
- POST /api/agents (create_agent)
- GET /api/agents (list_agents)
- GET /api/agents/{id} (get_agent_info)
- DELETE /api/agents/{id} (delete_agent)
- POST /api/agents/{id}/chat (chat_with_agent)
- GET /api/agents/{id}/file (get_agent_file)

ENDPOINTS TO KEEP:
- GET / (root endpoint)
- GET /health (health check)
- GET /api/system/status (system status)
- POST /mcp (MCP endpoint - CRITICAL!)
- WebSocket endpoints

CLEANUP TASKS:
- Remove agent-related methods from APIEndpoints class
- Remove corresponding routes from http_server.py
- Remove unused imports in endpoints.py
- Verify endpoints.py is now much smaller
- Update any documentation references

VALIDATION:
- HTML interface must still work (now via MCP)
- MCP endpoint must remain fully functional
- No broken imports or references
- System endpoints still work
- WebSocket functionality preserved
```

---

## Phase 4: Authentication Integration

**Responsible Agent**: Authentication Integration Agent

**Files to Provide**:
- `static/orchestrator.html` (updated)
- `api/mcp_handler.py`
- `core/security.py`
- `api/orchestrator.py`

**Agent Prompt**:
```
You are an authentication expert. Ensure HTML MCP calls work with existing authentication system.

TASKS:
1. Verify MCP tool calls from HTML work with session tokens
2. Update authentication flow in HTML if needed
3. Ensure MCP handler accepts authentication from HTML interface
4. Test that orchestrator authentication still works
5. Maintain backwards compatibility with Claude Code authentication
6. Document any authentication changes needed

AUTHENTICATION FLOW:
1. HTML authenticates with private key → gets session token
2. HTML includes session token in MCP calls (how?)
3. MCP handler validates session token
4. MCP tools execute with proper authorization

INTEGRATION POINTS:
- How does HTML pass session token to MCP calls?
- Does MCP handler need updates for HTML session handling?
- Are there different auth requirements for HTML vs Claude Code?
- Does orchestrator API still work with new flow?

REQUIREMENTS:
- HTML authentication works identically to before
- Claude Code authentication unchanged
- No security regressions
- Session management works for both interfaces
- Private key authentication preserved

VALIDATION:
- HTML can authenticate and get session token
- MCP calls from HTML work with authentication
- Orchestrator deployment features work
- Claude Code authentication unaffected
- Security audit passes
```

---

## Phase 5: Testing HTML MCP Integration

**Responsible Agent**: HTML MCP Testing Agent

**Files to Provide**:
- `static/orchestrator.html` (updated)
- `api/mcp_handler.py`
- `claude_code_bridge.py`
- All existing test files

**Agent Prompt**:
```
You are a frontend testing expert specializing in MCP integration. Create comprehensive tests for HTML MCP integration.

TASKS:
1. Create `tests/test_html_mcp_integration.py` - test HTML uses MCP correctly
2. Create `tests/test_interface_parity.py` - test HTML and Claude Code produce identical results
3. Update existing tests to work with new HTML MCP architecture
4. Create end-to-end tests for complete HTML workflows
5. Ensure all tests pass with >90% coverage

CRITICAL PARITY TESTS:
```python
def test_agent_creation_parity():
    # Create agent via HTML MCP calls
    # Create agent via Claude Code MCP calls
    # Verify identical results and agent registry state

def test_file_operation_parity():
    # Update file via HTML MCP calls
    # Update file via Claude Code MCP calls
    # Verify identical file contents on disk

def test_chat_operation_parity():
    # Chat with agent via HTML MCP
    # Chat with agent via Claude Code MCP
    # Verify identical responses and file outputs
```

INTEGRATION TESTS:
1. HTML loads and connects to MCP
2. Authentication works through MCP protocol
3. All agent operations work via MCP tools
4. Error handling works correctly
5. WebSocket functionality preserved
6. Git deployment features work
7. File operations create identical files

VALIDATION SCENARIOS:
- Create agent via HTML → operate via Claude Code → consistent behavior
- Create agent via Claude Code → operate via HTML → consistent behavior
- Complex workflows mixing both interfaces
- Error scenarios handled identically
- Performance equivalent between interfaces

REQUIREMENTS:
- All HTML functionality works via MCP
- Interface parity tests pass
- No functionality regression
- Error handling identical between interfaces
- File operations produce same results
```

---

## Phase 6: Claude Code Validation

**Responsible Agent**: Claude Code Validation Agent

**Files to Provide**:
- `claude_code_bridge.py`
- `api/mcp_handler.py`
- `static/orchestrator.html` (updated)
- `local_llm_mcp_server.py`

**Agent Prompt**:
```
You are an MCP protocol expert. Validate that Claude Code integration works identically after HTML unification changes.

TASKS:
1. Verify claude_code_bridge.py works exactly as before
2. Test all MCP tools Claude Code uses are unchanged
3. Ensure JSON-RPC protocol compliance maintained
4. Validate no breaking changes to MCP interface
5. Test session management works correctly
6. Confirm performance is equivalent or better

VALIDATION POINTS:
- All MCP tool definitions unchanged
- JSON-RPC responses identical to before
- Tool parameter validation works
- Error responses match previous behavior
- Session handling works correctly
- Multi-tool workflows function properly

TEST SCENARIOS:
1. Claude Code can create agents (same as before)
2. Claude Code can chat with agents (same file outputs)
3. Claude Code file operations work identically
4. Error scenarios produce same responses
5. Authentication and sessions work
6. Complex multi-step workflows

REGRESSION TESTS:
- Compare Claude Code behavior before/after changes
- Verify file outputs are identical
- Check response formats unchanged
- Validate error handling consistent
- Confirm no performance degradation

REQUIREMENTS:
- Zero breaking changes for Claude Code users
- Identical MCP tool behavior
- Same file operation results
- Consistent error handling
- No performance regression
```

---

## Phase 7: File Size Compliance

**Responsible Agent**: Code Organization Agent

**Files to Provide**:
- `static/orchestrator.html` (updated)
- `api/endpoints.py` (reduced)
- `api/mcp_handler.py`
- `api/http_server.py` (updated)

**Agent Prompt**:
```
You are a code organization expert. Ensure all files comply with 300-line limits and clean organization.

TASKS:
1. Count lines in all modified files
2. Split any files exceeding 300 lines into logical modules
3. Ensure clean separation of concerns
4. Update imports across affected files
5. Organize for maximum maintainability

FILES TO ANALYZE:
- static/orchestrator.html (likely larger after MCP integration)
- api/endpoints.py (should be much smaller now)
- api/mcp_handler.py (unchanged but verify)
- api/http_server.py (routes removed)

IF ORCHESTRATOR.HTML > 300 LINES:
Split into logical components:
- static/js/mcp-client.js - MCP JSON-RPC handling
- static/js/ui-handlers.js - UI event handling
- static/js/agent-operations.js - Agent operation functions
- static/orchestrator.html - HTML structure and main script

ORGANIZATION PRINCIPLES:
- One responsibility per file
- Clear module boundaries
- Logical separation of MCP vs UI code
- Easy to understand and maintain
- Proper dependency management

REQUIREMENTS:
- All files under 300 lines
- Clear functional separation
- No duplication
- Maintainable structure
- Preserve all functionality
```

---

## Phase 8: Final Validation & Documentation

**Responsible Agent**: System Validation Agent

**Files to Provide**:
- All updated files
- All test files
- `README.md`
- `docs/html_to_mcp_mapping.md`

**Agent Prompt**:
```
You are a system validation expert. Perform final validation and document the unified MCP architecture.

TASKS:
1. Run complete end-to-end testing of HTML MCP integration
2. Validate both HTML and Claude Code produce identical results
3. Update README.md with unified architecture documentation
4. Create troubleshooting guide
5. Document the unification benefits
6. Create deployment procedures

FINAL VALIDATION CHECKLIST:
- [ ] HTML orchestrator works exactly as before (via MCP)
- [ ] Claude Code integration works exactly as before
- [ ] Same agent operations produce identical file outputs via both interfaces
- [ ] All pre-commit checks pass
- [ ] All files under 300 lines
- [ ] Test coverage >90%
- [ ] No functionality regression
- [ ] Error handling identical between interfaces
- [ ] Authentication works for both paths
- [ ] WebSocket functionality preserved
- [ ] Git deployment features work via HTML
- [ ] No HTTP agent endpoints remain

ULTIMATE VALIDATION TEST:
Create a comprehensive workflow that:
1. Creates agent via HTML → file created
2. Modifies agent via Claude Code → same file modified
3. Further operations via HTML → consistent file state
4. Error scenarios via both → identical error responses
5. Complex deployment workflows → work via both interfaces

ARCHITECTURE DOCUMENTATION:
- Update README.md with "Unified MCP Architecture" section
- Document benefits: single code path, zero duplication, guaranteed consistency
- Explain how HTML is now just another MCP client
- Document troubleshooting for MCP-related issues
- Create developer guide for the unified system

SUCCESS CRITERIA:
✅ HTML sends JSON-RPC to /mcp (same as Claude Code)
✅ No /api/agents/* endpoints exist anymore
✅ Identical behavior regardless of interface used
✅ All files under 300 lines
✅ >90% test coverage
✅ Zero duplication between interfaces
✅ Same MCP tools handle both HTML and Claude Code
```

---

## Architecture Benefits

**🎯 True Unification**: HTML and Claude Code use identical JSON-RPC → MCP path
**🗑️ Zero Duplication**: No separate HTTP endpoints for agent operations
**🐛 Bug Elimination**: Impossible for interfaces to behave differently
**🧪 Simplified Testing**: Test MCP tools once, covers both interfaces automatically
**📉 Reduced Codebase**: Eliminated entire HTTP endpoint layer
**🔒 Guaranteed Consistency**: Both interfaces use same code path by design

## Before vs After

**Before (Problematic)**:
```
HTML Interface → /api/agents/* → endpoints.py → Agent Logic
Claude Code → /mcp → mcp_handler.py → Agent Logic
             (Different paths = different bugs)
```

**After (Unified)**:
```
HTML Interface → /mcp → mcp_handler.py → Agent Logic
Claude Code → /mcp → mcp_handler.py → Agent Logic
             (Same path = same behavior)
```

## The Key Insight

HTML becomes **just another MCP client** that sends JSON-RPC requests. No special treatment, no separate endpoints, no duplication. This is the cleanest possible architecture and eliminates your current issue by making it architecturally impossible.

## Success Validation

**The Ultimate Test**: Your original problem (file creation discrepancy) becomes impossible because both interfaces literally use the same MCP tool methods. If it works for Claude Code, it works for HTML, because they're the same code path.
