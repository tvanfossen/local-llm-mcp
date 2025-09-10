/**
 * MCP Response Parsers
 * Parse MCP tool responses into structured data
 */

/**
 * Parse list_agents response
 * @param {object} response - MCP response object
 * @returns {array} Array of agent objects
 */
function parseListAgentsResponse(response) {
    if (!response || !response.content) {
        console.warn('Invalid response structure:', response);
        return [];
    }

    const text = response.content[0]?.text || '';
    
    // If response indicates no agents
    if (text.includes('No agents found')) {
        return [];
    }

    const agents = [];
    
    // Parse agent entries - Format: 🤖 **AgentName** (ID: `agent_id...`)
    const agentPattern = /🤖\s+\*\*([^*]+)\*\*\s+\(ID:\s+`([^`]+)`\)[\s\S]*?(?=🤖|📊)/g;
    let match;
    
    while ((match = agentPattern.exec(text)) !== null) {
        const name = match[1].trim();
        const idPart = match[2].trim();
        const blockText = match[0];
        
        // Extract details from the block
        const descMatch = blockText.match(/📄\s+Description:\s+([^\n]+)/);
        const filesMatch = blockText.match(/📁\s+Managing:\s+(\d+)\s+files?/);
        const interactionsMatch = blockText.match(/🔄\s+(\d+)\s+interactions?/);
        const successMatch = blockText.match(/✅\s+Success:\s+([\d.]+%|N\/A)/);
        
        // Extract managed file if mentioned
        let managedFile = 'unknown';
        if (filesMatch && parseInt(filesMatch[1]) === 1) {
            // For single file, try to extract from description or other context
            managedFile = descMatch ? descMatch[1].replace(/^Manage[s]?\s+/, '').trim() : 'unknown';
        }
        
        const agent = {
            id: idPart.replace('...', ''), // Remove ellipsis
            name: name,
            description: descMatch ? descMatch[1].trim() : '',
            managed_file: managedFile,
            managed_files_count: filesMatch ? parseInt(filesMatch[1]) : 0,
            total_interactions: interactionsMatch ? parseInt(interactionsMatch[1]) : 0,
            success_rate: 0
        };
        
        // Parse success rate
        if (successMatch && successMatch[1] !== 'N/A') {
            agent.success_rate = parseFloat(successMatch[1]) / 100;
        }
        
        agents.push(agent);
    }
    
    console.log(`Parsed ${agents.length} agents from response`);
    return agents;
}

/**
 * Parse get_agent_info response
 * @param {object} response - MCP response object
 * @returns {object} Agent details object
 */
function parseAgentInfoResponse(response) {
    if (!response || !response.content) {
        return null;
    }

    const text = response.content[0]?.text || '';
    
    // Extract agent details
    const idMatch = text.match(/Agent ID:\s+`([^`]+)`/);
    const nameMatch = text.match(/Name:\s+([^\n]+)/);
    const descMatch = text.match(/Description:\s+([^\n]+)/);
    const createdMatch = text.match(/Created:\s+([^\n]+)/);
    const filesMatch = text.match(/Managed Files:\s+(\d+)/);
    const interactionsMatch = text.match(/Total Interactions:\s+(\d+)/);
    const successMatch = text.match(/Success Rate:\s+([\d.]+%|N\/A)/);
    
    if (!idMatch || !nameMatch) {
        return null;
    }
    
    const agent = {
        id: idMatch[1],
        name: nameMatch[1].trim(),
        description: descMatch ? descMatch[1].trim() : '',
        created: createdMatch ? createdMatch[1].trim() : '',
        managed_files_count: filesMatch ? parseInt(filesMatch[1]) : 0,
        total_interactions: interactionsMatch ? parseInt(interactionsMatch[1]) : 0,
        success_rate: 0
    };
    
    // Parse success rate
    if (successMatch && successMatch[1] !== 'N/A') {
        agent.success_rate = parseFloat(successMatch[1]) / 100;
    }
    
    // Extract managed files list
    const filesSection = text.match(/📁\s+\*\*Managed Files:\*\*[\s\S]*?(?=\n\n|$)/);
    if (filesSection) {
        const filesList = filesSection[0].match(/•\s+`([^`]+)`/g);
        if (filesList) {
            agent.managed_files = filesList.map(f => f.replace(/•\s+`|`/g, ''));
            if (agent.managed_files.length === 1) {
                agent.managed_file = agent.managed_files[0];
            }
        }
    }
    
    return agent;
}

/**
 * Parse system_status response
 * @param {object} response - MCP response object
 * @returns {object} System status object
 */
function parseSystemStatusResponse(response) {
    if (!response || !response.content) {
        return null;
    }

    const text = response.content[0]?.text || '';
    
    const status = {
        server: {},
        model: {},
        agents: {},
        validation: {}
    };
    
    // Parse server status
    const serverMatch = text.match(/MCP Server:\s+([^\n]+)/);
    const versionMatch = text.match(/Version:\s+([^\n]+)/);
    const startedMatch = text.match(/Started:\s+([^\n]+)/);
    
    if (serverMatch) status.server.status = serverMatch[1].trim();
    if (versionMatch) status.server.version = versionMatch[1].trim();
    if (startedMatch) status.server.started = startedMatch[1].trim();
    
    // Parse model status
    const modelNameMatch = text.match(/Model:\s+([^\n]+)/);
    const modelStatusMatch = text.match(/Status:\s+([^\n]+)/);
    
    if (modelNameMatch) status.model.name = modelNameMatch[1].trim();
    if (modelStatusMatch) status.model.status = modelStatusMatch[1].trim();
    
    // Parse agent statistics
    const totalAgentsMatch = text.match(/Total Agents:\s+(\d+)/);
    const activeAgentsMatch = text.match(/Active Agents:\s+(\d+)/);
    const managedFilesMatch = text.match(/Managed Files:\s+(\d+)/);
    
    if (totalAgentsMatch) status.agents.total = parseInt(totalAgentsMatch[1]);
    if (activeAgentsMatch) status.agents.active = parseInt(activeAgentsMatch[1]);
    if (managedFilesMatch) status.agents.managedFiles = parseInt(managedFilesMatch[1]);
    
    return status;
}

/**
 * Parse generic success/error responses
 * @param {object} response - MCP response object
 * @returns {object} Parsed response with success flag and message
 */
function parseGenericResponse(response) {
    if (!response) {
        return { success: false, message: 'No response received' };
    }
    
    if (response.isError) {
        const errorText = response.content?.[0]?.text || 'Unknown error';
        return { success: false, message: errorText };
    }
    
    const text = response.content?.[0]?.text || '';
    const isSuccess = text.includes('✅') || text.includes('Success') || !response.isError;
    
    return {
        success: isSuccess,
        message: text
    };
}

// Export parsers
window.MCPParsers = {
    parseListAgentsResponse,
    parseAgentInfoResponse,
    parseSystemStatusResponse,
    parseGenericResponse
};