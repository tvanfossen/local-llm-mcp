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
        throw new Error('Authentication required for MCP calls');
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
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const jsonrpcResponse = await response.json();

        if (jsonrpcResponse.error) {
            const error = jsonrpcResponse.error;
            throw new Error(`MCP Error [${error.code}]: ${error.message}`);
        }

        if (!jsonrpcResponse.result) {
            throw new Error('No result in MCP response');
        }

        addTerminalLine(`✅ MCP Success: ${toolName}`, 'success');
        return jsonrpcResponse.result;

    } catch (error) {
        addTerminalLine(`❌ MCP Error: ${error.message}`, 'error');
        throw error;
    }
}

/**
 * Parse MCP tool response content to extract structured data
 * @param {object} mcpResult - MCP tool result
 * @returns {object} - Parsed data
 */
function parseMCPContent(mcpResult) {
    if (!mcpResult.content || !Array.isArray(mcpResult.content)) {
        return { text: 'No content available', data: null };
    }

    const textContent = mcpResult.content
        .filter(item => item.type === 'text')
        .map(item => item.text)
        .join('\n');

    return {
        text: textContent,
        data: extractStructuredData(textContent),
        isError: mcpResult.isError || false
    };
}

/**
 * Extract structured data from MCP markdown responses
 * @param {string} text - Markdown formatted text from MCP
 * @returns {object|null} - Extracted structured data
 */
function extractStructuredData(text) {
    try {
        // Try to extract agent list from markdown
        if (text.includes('Active Agents:')) {
            return parseAgentList(text);
        }

        // Try to extract agent info
        if (text.includes('Agent Information:')) {
            return parseAgentInfo(text);
        }

        // Try to extract file content
        if (text.includes('File Content:')) {
            return parseFileContent(text);
        }

        // Try to extract system status
        if (text.includes('System Status Report')) {
            return parseSystemStatus(text);
        }

        return null;
    } catch (error) {
        console.warn('Failed to parse structured data:', error);
        return null;
    }
}

/**
 * Parse agent list from MCP markdown response
 * @param {string} text - Markdown text
 * @returns {array} - Array of agent objects
 */
function parseAgentList(text) {
    const agents = [];
    const agentRegex = /• \*\*([\w-]+)\*\* - (.+?)\n\s+📄 File: `(.+?)`\n\s+📝 (.+?)\n\s+🔢 Interactions: (\d+)\n\s+📊 Success Rate: ([\d.]+)/g;

    let match;
    while ((match = agentRegex.exec(text)) !== null) {
        agents.push({
            id: match[1],
            name: match[2],
            managed_file: match[3],
            description: match[4],
            total_interactions: parseInt(match[5]),
            success_rate: parseFloat(match[6])
        });
    }

    return agents;
}

/**
 * Parse agent info from MCP markdown response
 * @param {string} text - Markdown text
 * @returns {object} - Agent info object
 */
function parseAgentInfo(text) {
    const info = {};

    // Extract basic info
    const idMatch = text.match(/\*\*ID:\*\* (.+)/);
    const nameMatch = text.match(/\*\*Name:\*\* (.+)/);
    const fileMatch = text.match(/\*\*Managed File:\*\* `(.+?)`/);
    const descMatch = text.match(/\*\*Description:\*\* (.+)/);

    if (idMatch) info.id = idMatch[1];
    if (nameMatch) info.name = nameMatch[1];
    if (fileMatch) info.managed_file = fileMatch[1];
    if (descMatch) info.description = descMatch[1];

    return info;
}

/**
 * Parse file content from MCP markdown response
 * @param {string} text - Markdown text
 * @returns {object} - File content object
 */
function parseFileContent(text) {
    const fileMatch = text.match(/\*\*File Content:\*\* `(.+?)`/);
    const sizeMatch = text.match(/\*\*Size:\*\* (\d+) characters/);

    // Extract code block content
    const codeBlockMatch = text.match(/```[\w]*\n([\s\S]*?)\n```/);

    return {
        filename: fileMatch ? fileMatch[1] : 'unknown',
        size: sizeMatch ? parseInt(sizeMatch[1]) : 0,
        content: codeBlockMatch ? codeBlockMatch[1] : '',
        exists: !text.includes('does not exist yet')
    };
}

/**
 * Parse system status from MCP markdown response
 * @param {string} text - Markdown text
 * @returns {object} - System status object
 */
function parseSystemStatus(text) {
    const status = {};

    // Extract model status
    const modelMatch = text.match(/\*\*🤖 Model Status:\*\* (.+)/);
    if (modelMatch) {
        status.model_loaded = modelMatch[1].includes('✅');
    }

    // Extract agent counts
    const agentsMatch = text.match(/\*\*Total Agents:\*\* (\d+)/);
    const filesMatch = text.match(/\*\*Managed Files:\*\* (\d+)/);

    if (agentsMatch) status.total_agents = parseInt(agentsMatch[1]);
    if (filesMatch) status.managed_files = parseInt(filesMatch[1]);

    return status;
}

/**
 * Convert agent management request to MCP format
 * @param {string} action - Action type (create, delete, etc.)
 * @param {object} data - Request data
 * @returns {Promise<object>} - Formatted response
 */
async function executeAgentManagement(action, data) {
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

    const result = await callMCPTool(toolName, data);
    const parsed = parseMCPContent(result);

    // Convert to expected format for UI compatibility
    return {
        success: !parsed.isError,
        data: parsed.data,
        message: parsed.text,
        response: parsed.data // For backwards compatibility
    };
}

/**
 * Execute agent operation (chat, file operations, etc.)
 * @param {string} operation - Operation type
 * @param {string} agentId - Agent ID
 * @param {object} data - Operation data
 * @returns {Promise<object>} - Operation result
 */
async function executeAgentOperation(operation, agentId, data) {
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
