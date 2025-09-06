/**
 * MCP JSON-RPC Client for Agent Orchestrator
 * Handles all communication with MCP tools via JSON-RPC 2.0 protocol
 */

/**
 * Core MCP communication function
 * @param {string} toolName - Name of the MCP tool to call
 * @param {object} arguments - Arguments to pass to the tool
 * @returns {Promise<object>} - MCP tool result
 */
async function callMCPTool(toolName, arguments = {}) {
    if (!authenticated) {
        const authError = new Error('Authentication required for MCP calls');
        authError.code = 'AUTH_REQUIRED';
        throw authError;
    }

    if (sessionExpiry && Date.now() >= sessionExpiry) {
        handleSessionExpiry();
        const expiredError = new Error('Session expired - please re-authenticate');
        expiredError.code = 'SESSION_EXPIRED';
        throw expiredError;
    }

    const request = {
        "jsonrpc": "2.0",
        "id": Date.now(),
        "method": "tools/call",
        "params": {
            "name": toolName,
            "arguments": arguments
        }
    };

    try {
        addTerminalLine(`🔗 MCP Call: ${toolName}`, 'info');

        const response = await fetch('/mcp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': sessionToken ? `Bearer ${sessionToken}` : undefined
            },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            await handleHTTPError(response, toolName);
        }

        const jsonrpcResponse = await response.json();

        if (jsonrpcResponse.error) {
            await handleMCPError(jsonrpcResponse.error, toolName);
        }

        if (!jsonrpcResponse.result) {
            throw new Error('No result in MCP response');
        }

        addTerminalLine(`✅ MCP Success: ${toolName}`, 'success');
        return jsonrpcResponse.result;

    } catch (error) {
        await handleMCPCallError(error, toolName);
        throw error;
    }
}



/**
 * Convert agent management request to MCP format with retry logic
 * @param {string} action - Action type (create, delete, etc.)
 * @param {object} data - Request data
 * @param {number} retryCount - Number of retry attempts (default: 1)
 * @returns {Promise<object>} - Formatted response
 */
async function executeAgentManagement(action, data, retryCount = 1) {
    const toolMapping = {
        'create': 'create_agent',
        'delete': 'delete_agent',
        'list': 'list_agents',
        'info': 'get_agent_info'
    };

    const toolName = toolMapping[action];
    if (!toolName) {
        throw new Error(`Unknown agent management action: ${action}`);
    }

    try {
        const result = await callMCPTool(toolName, data);
        const parsed = parseMCPContent(result);

        // Convert to expected format for UI compatibility
        return {
            success: !parsed.isError,
            data: parsed.data,
            message: parsed.text,
            response: parsed.data // For backwards compatibility
        };
    } catch (error) {
        if (shouldRetryAuthentication(error) && retryCount > 0) {
            addTerminalLine(`🔄 Retrying ${action} after authentication check...`, 'warning');

            // Wait a moment and retry
            await new Promise(resolve => setTimeout(resolve, 1000));
            return await executeAgentManagement(action, data, retryCount - 1);
        }

        return {
            success: false,
            message: error.message,
            error: error.code || 'OPERATION_FAILED'
        };
    }
}


/**
 * Execute agent operation (chat, file operations, etc.) with retry logic
 * @param {string} operation - Operation type
 * @param {string} agentId - Agent ID
 * @param {object} data - Operation data
 * @param {number} retryCount - Number of retry attempts (default: 1)
 * @returns {Promise<object>} - Operation result
 */
async function executeAgentOperation(operation, agentId, data, retryCount = 1) {
    const toolMapping = {
        'chat': 'chat_with_agent',
        'get_file': 'get_agent_file',
        'update_file': 'agent_update_file',
        'write_file': 'agent_write_file',
        'validate_file': 'validate_agent_file'
    };

    const toolName = toolMapping[operation];
    if (!toolName) {
        throw new Error(`Unknown agent operation: ${operation}`);
    }

    try {
        // Prepare arguments
        const args = { agent_id: agentId, ...data };

        const result = await callMCPTool(toolName, args);
        const parsed = parseMCPContent(result);

        return {
            success: !parsed.isError,
            response: {
                message: parsed.text,
                data: parsed.data,
                agent_id: agentId
            }
        };
    } catch (error) {
        if (shouldRetryAuthentication(error) && retryCount > 0) {
            addTerminalLine(`🔄 Retrying ${operation} for agent ${agentId}...`, 'warning');

            // Wait a moment and retry
            await new Promise(resolve => setTimeout(resolve, 1000));
            return await executeAgentOperation(operation, agentId, data, retryCount - 1);
        }

        return {
            success: false,
            response: {
                message: error.message,
                error: error.code || 'OPERATION_FAILED',
                agent_id: agentId
            }
        };
    }
}

/**
 * Chat with agent using MCP
 * @param {string} agentId - Agent ID
 * @param {string} message - Message to send
 * @param {string} taskType - Task type (optional)
 * @returns {Promise<object>} - Chat response
 */
async function chatWithAgent(agentId, message, taskType = 'update') {
    return await executeAgentOperation('chat', agentId, {
        message: message,
        task_type: taskType
    });
}

/**
 * Get agent file content using MCP
 * @param {string} agentId - Agent ID
 * @returns {Promise<object>} - File content
 */
async function getAgentFile(agentId) {
    const result = await executeAgentOperation('get_file', agentId, {});

    // Parse file content from response
    if (result.response && result.response.data) {
        return {
            success: true,
            file: result.response.data
        };
    }

    return result;
}

/**
 * Create agent using MCP
 * @param {object} agentData - Agent creation data
 * @returns {Promise<object>} - Creation result
 */
async function createAgent(agentData) {
    return await executeAgentManagement('create', agentData);
}

/**
 * Delete agent using MCP
 * @param {string} agentId - Agent ID to delete
 * @returns {Promise<object>} - Deletion result
 */
async function deleteAgent(agentId) {
    return await executeAgentManagement('delete', { agent_id: agentId });
}

/**
 * List all agents using MCP
 * @returns {Promise<object>} - Agents list
 */
async function listAgents() {
    return await executeAgentManagement('list', {});
}

/**
 * Get agent info using MCP
 * @param {string} agentId - Agent ID
 * @returns {Promise<object>} - Agent info
 */
async function getAgentInfo(agentId) {
    return await executeAgentManagement('info', { agent_id: agentId });
}

/**
 * Get system status using MCP
 * @returns {Promise<object>} - System status
 */
async function getSystemStatus() {
    const result = await callMCPTool('system_status', {});
    const parsed = parseMCPContent(result);

    return {
        success: !parsed.isError,
        status: parsed.data || { text: parsed.text },
        message: parsed.text
    };
}
