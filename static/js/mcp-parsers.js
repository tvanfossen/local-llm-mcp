/**
 * MCP Response Parsers
 * Handles parsing of MCP tool responses and data extraction
 */

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
