# HTML to MCP Mapping Documentation

## Phase 1: MCP Tool Inventory & HTML Interface Analysis

### MCP Tool Inventory

Based on analysis of `api/mcp_handler.py`, the following MCP tools are available:

#### 1. Agent Management Tools

**create_agent**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_agent",
    "arguments": {
      "name": "string (required)",
      "description": "string (required)",
      "system_prompt": "string (required)",
      "managed_file": "string (required)",
      "initial_context": "string (optional)"
    }
  }
}
```

**list_agents**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_agents",
    "arguments": {}
  }
}
```

**get_agent_info**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_agent_info",
    "arguments": {
      "agent_id": "string (required)"
    }
  }
}
```

**delete_agent**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "delete_agent",
    "arguments": {
      "agent_id": "string (required)"
    }
  }
}
```

#### 2. Agent Interaction Tools

**chat_with_agent**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "chat_with_agent",
    "arguments": {
      "agent_id": "string (required)",
      "message": "string (required)",
      "task_type": "string (optional, default: update)",
      "context": "string (optional)",
      "parameters": "object (optional)"
    }
  }
}
```

#### 3. File Management Tools

**get_agent_file**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_agent_file",
    "arguments": {
      "agent_id": "string (required)"
    }
  }
}
```

**agent_update_file**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "agent_update_file",
    "arguments": {
      "agent_id": "string (required)",
      "instruction": "string (required)",
      "current_content": "string (optional)"
    }
  }
}
```

**agent_write_file**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "agent_write_file",
    "arguments": {
      "agent_id": "string (required)",
      "content": "string (required)",
      "validation_required": "boolean (optional, default: false)"
    }
  }
}
```

**validate_agent_file**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "validate_agent_file",
    "arguments": {
      "agent_id": "string (required)",
      "validation_type": "string (optional, default: syntax)"
    }
  }
}
```

#### 4. System Tools

**system_status**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "system_status",
    "arguments": {}
  }
}
```

### HTML Interface Analysis

Based on analysis of `static/orchestrator.html`, the following HTTP API calls are currently made:

#### Current HTTP API Calls

1. **Authentication** (Keep as-is)
   - `POST /api/orchestrator/authenticate`
   - `GET /api/orchestrator/validate`

2. **Agent Management** (Convert to MCP)
   - `GET /api/agents` → `list_agents`
   - `POST /api/agents` → `create_agent`
   - `GET /api/agents/{id}` → `get_agent_info`
   - `DELETE /api/agents/{id}` → `delete_agent`

3. **Agent Operations** (Convert to MCP)
   - `POST /api/agents/{id}/chat` → `chat_with_agent`
   - `GET /api/agents/{id}/file` → `get_agent_file`

4. **System Status** (Convert to MCP)
   - `GET /api/system/status` → `system_status`

5. **Deployment** (Keep as-is)
   - `/api/orchestrator/*` endpoints remain unchanged

## HTTP to MCP Mapping Table

| Current HTTP Call | MCP Tool | HTTP Method | MCP Method | Parameters Mapping |
|------------------|----------|-------------|------------|-------------------|
| `GET /api/agents` | `list_agents` | GET | POST /mcp | No parameters needed |
| `POST /api/agents` | `create_agent` | POST | POST /mcp | Direct body mapping |
| `GET /api/agents/{id}` | `get_agent_info` | GET | POST /mcp | `{agent_id: id}` |
| `DELETE /api/agents/{id}` | `delete_agent` | DELETE | POST /mcp | `{agent_id: id}` |
| `POST /api/agents/{id}/chat` | `chat_with_agent` | POST | POST /mcp | Add `agent_id` to body |
| `GET /api/agents/{id}/file` | `get_agent_file` | GET | POST /mcp | `{agent_id: id}` |
| `GET /api/system/status` | `system_status` | GET | POST /mcp | No parameters needed |

## Required JavaScript Function Changes

### 1. Core MCP Communication Function

Add new MCP communication function:

```javascript
async function callMCPTool(toolName, arguments = {}) {
    const response = await fetch('/mcp', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': sessionToken ? `Bearer ${sessionToken}` : undefined
        },
        body: JSON.stringify({
            "jsonrpc": "2.0",
            "id": Date.now(),
            "method": "tools/call",
            "params": {
                "name": toolName,
                "arguments": arguments
            }
        })
    });

    const jsonrpcResponse = await response.json();

    if (jsonrpcResponse.error) {
        throw new Error(jsonrpcResponse.error.message);
    }

    return jsonrpcResponse.result;
}
```

### 2. Function Conversions

**refreshAgents() → list_agents**
```javascript
// OLD
async function refreshAgents() {
    const response = await fetch('/api/agents');
    const data = await response.json();
    displayAgents(data.agents);
}

// NEW
async function refreshAgents() {
    const result = await callMCPTool('list_agents');
    // Extract agents from MCP tool result
    const agents = extractAgentsFromMCPResult(result);
    displayAgents(agents);
}
```

**executeAgentManagementTool() → MCP tools**
```javascript
// OLD
async function executeAgentManagementTool(action) {
    const response = await fetch(endpoint.url, requestOptions);
    const data = await response.json();
    return { success: true, response: data };
}

// NEW
async function executeAgentManagementTool(action) {
    const result = await callMCPTool(action.tool, action.parameters);
    return { success: true, response: result };
}
```

**Chat Functions → chat_with_agent**
```javascript
// OLD
async function chatWithAgent(agentId, message, taskType) {
    const response = await fetch(`/api/agents/${agentId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ message, task_type: taskType })
    });
    return await response.json();
}

// NEW
async function chatWithAgent(agentId, message, taskType) {
    const result = await callMCPTool('chat_with_agent', {
        agent_id: agentId,
        message: message,
        task_type: taskType
    });
    return result;
}
```

### 3. Response Format Conversion

MCP tools return structured content that needs to be adapted:

```javascript
function extractAgentsFromMCPResult(mcpResult) {
    // MCP result contains content array with text
    const content = mcpResult.content[0].text;
    // Parse the markdown-formatted response to extract agent data
    return parseAgentListFromMarkdown(content);
}

function parseAgentListFromMarkdown(text) {
    // Parse the markdown response to extract structured agent data
    // This will need to parse the formatted text response from MCP tools
    // and convert it back to the expected JSON structure
}
```

## Authentication Strategy for MCP Calls

### Current Authentication
- Uses session tokens via `Authorization: Bearer {token}` headers
- Session tokens obtained from `/api/orchestrator/authenticate`

### MCP Authentication Strategy
1. **Keep existing auth flow**: Authentication remains via orchestrator endpoints
2. **Pass session token in headers**: Include `Authorization` header in MCP calls
3. **MCP handler validation**: Modify MCP handler to validate session tokens

### Implementation
```javascript
// Include session token in all MCP calls
headers: {
    'Content-Type': 'application/json',
    'Authorization': sessionToken ? `Bearer ${sessionToken}` : undefined
}
```

## Error Handling Changes

### Current Error Handling
```javascript
if (response.ok) {
    const data = await response.json();
    return { success: true, response: data };
} else {
    const error = await response.json();
    return { success: false, error: error.error };
}
```

### New MCP Error Handling
```javascript
const jsonrpcResponse = await response.json();

if (jsonrpcResponse.error) {
    return {
        success: false,
        error: jsonrpcResponse.error.message
    };
}

if (jsonrpcResponse.result.isError) {
    return {
        success: false,
        error: extractErrorFromMCPContent(jsonrpcResponse.result.content)
    };
}

return {
    success: true,
    response: parseMCPResponse(jsonrpcResponse.result)
};
```

## Response Parsing Changes Required

### MCP Response Structure
MCP tools return responses in this format:
```json
{
    "content": [
        {
            "type": "text",
            "text": "Formatted response text with agent data"
        }
    ],
    "isError": false
}
```

### Required Parsers
1. **Agent List Parser**: Convert markdown agent list to JSON array
2. **Agent Info Parser**: Extract structured agent data from formatted text
3. **File Content Parser**: Extract file content from formatted response
4. **Status Parser**: Convert status text to structured data

### Example Parser Implementation
```javascript
function parseAgentListFromMCPResponse(mcpResult) {
    const text = mcpResult.content[0].text;

    // Parse the formatted text response
    const agents = [];
    const agentMatches = text.match(/• \*\*([\w-]+)\*\* - (.+)/g);

    if (agentMatches) {
        agentMatches.forEach(match => {
            // Extract agent data from formatted text
            const agentData = parseAgentFromText(match);
            agents.push(agentData);
        });
    }

    return agents;
}
```

## Implementation Priority

1. **High Priority** (Convert first)
   - `refreshAgents()` → `list_agents`
   - `executeAgentManagementTool()` for basic CRUD operations
   - Core MCP communication function

2. **Medium Priority**
   - Chat functionality → `chat_with_agent`
   - File operations → `get_agent_file`, `agent_update_file`
   - System status → `system_status`

3. **Low Priority**
   - Advanced file operations
   - Tool validation and error handling refinements

## Validation Checklist

- [x] Complete MCP tool inventory documented
- [x] All HTML API calls mapped to MCP tools
- [x] Required JavaScript changes identified
- [x] Authentication strategy defined
- [x] Error handling changes planned
- [x] Response parsing requirements documented
- [ ] All agent CRUD operations work via MCP
- [ ] Chat functionality maintains identical behavior
- [ ] File operations produce same results
- [ ] Error handling provides same user experience
- [ ] Authentication works with MCP calls
- [ ] UI behavior remains unchanged
- [ ] Response parsing handles all MCP response formats
- [ ] Performance is equivalent or better

## Key Implementation Notes

1. **No New MCP Tools Needed**: All existing HTML functionality maps to existing MCP tools
2. **Authentication Compatibility**: Existing session token system works with MCP calls
3. **Response Format Challenge**: Main complexity is converting MCP text responses back to JSON structures expected by UI
4. **Backwards Compatibility**: Deployment endpoints remain unchanged during this phase
5. **Error Handling**: Need to handle both JSON-RPC errors and MCP tool errors consistently

## Phase 1 Completion Status

✅ **PHASE 1 COMPLETE**

**Deliverables:**
- Complete MCP tool inventory with JSON-RPC signatures
- HTTP call → MCP tool mapping table
- Required JavaScript function changes documented
- Authentication strategy for MCP calls defined
- Error handling and response parsing requirements identified

**Key Findings:**
- All 7 agent management functions map cleanly to existing MCP tools
- No new MCP tools required
- Session token authentication compatible with MCP calls
- Main challenge: Converting MCP markdown responses back to JSON for UI

**Ready for Phase 2**: HTML JavaScript MCP Conversion
