/**
 * Agent Operations - UI Integration with MCP Tools
 * Handles agent management and operations through MCP protocol
 */

// Global variable for current selected agent
window.currentSelectedAgent = null;

/**
 * List agents using MCP tool
 * @returns {object} Result with success flag, message, and data
 */
async function listAgents() {
    if (!window.mcpClient || !window.authenticated) {
        console.error('MCP client not ready or not authenticated');
        return { success: false, message: 'Not authenticated', data: [] };
    }

    try {
        const response = await window.mcpClient.callTool('list_agents', {});
        
        // Debug logging
        console.log('Raw list_agents response:', response);
        
        if (response.isError) {
            console.error('Error from MCP:', response);
            return { 
                success: false, 
                message: response.content?.[0]?.text || 'Unknown error',
                data: [] 
            };
        }

        // Parse the response using the parser
        const agents = window.MCPParsers.parseListAgentsResponse(response);
        
        // Store globally for debugging
        window.currentAgents = agents;
        
        return {
            success: true,
            message: response.content?.[0]?.text || '',
            data: agents,
            response: response
        };
        
    } catch (error) {
        console.error('Failed to list agents:', error);
        return { 
            success: false, 
            message: error.message,
            data: [] 
        };
    }
}

/**
 * Refresh agents list using MCP
 */
async function refreshAgents() {
    if (!authenticated) {
        addTerminalLine('Please authenticate first', 'warning');
        return;
    }

    try {
        addTerminalLine('🔄 Refreshing agents via MCP...', 'info');
        const result = await listAgents();

        if (result.success) {
            if (result.data && result.data.length > 0) {
                displayAgents(result.data);
                addTerminalLine(`📚 Loaded ${result.data.length} agents via MCP`, 'success');
            } else if (result.message.includes('No agents found')) {
                document.getElementById('agentsList').innerHTML = 
                    '<p style="opacity: 0.7;">No agents available. Use the create agent tool to create your first agent.</p>';
                addTerminalLine('📚 No agents found in registry', 'info');
            } else {
                // Agents exist but parsing may have issues - show raw message
                document.getElementById('agentsList').innerHTML = 
                    '<div style="color: #ff9500; padding: 10px; background: rgba(255,149,0,0.1); border-radius: 4px;">' +
                    '<strong>⚠️ Agent data present but display parsing failed</strong><br>' +
                    '<pre style="font-size: 0.8em; margin-top: 10px;">' + 
                    result.message.substring(0, 500) + '...</pre></div>';
                addTerminalLine('⚠️ Agent data received but display parsing incomplete', 'warning');
            }
        } else {
            addTerminalLine(`❌ Failed to refresh agents: ${result.message}`, 'error');
            document.getElementById('agentsList').innerHTML = 
                `<p style="color: #ff5555;">Error: ${result.message}</p>`;
        }
    } catch (error) {
        console.error('Error refreshing agents:', error);
        addTerminalLine(`❌ Error: ${error.message}`, 'error');
    }
}

/**
 * Display agents in the UI
 * @param {array} agents - Array of agent objects
 */
function displayAgents(agents) {
    const container = document.getElementById('agentsList');
    container.innerHTML = '';

    if (!agents || agents.length === 0) {
        container.innerHTML = '<p style="opacity: 0.7;">No agents available</p>';
        return;
    }

    agents.forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-card';
        card.innerHTML = `
            <div class="agent-name">${agent.name || agent.id}</div>
            <div class="agent-file">📄 ${agent.managed_file || `${agent.managed_files_count || 0} files`}</div>
            <div class="agent-stats">
                <span>📊 ${agent.total_interactions || 0} interactions</span>
                <span>✅ ${Math.round((agent.success_rate || 0) * 100)}%</span>
            </div>
        `;

        card.onclick = () => selectAgent(agent, card);
        container.appendChild(card);
    });
}

/**
 * Select an agent for operations
 * @param {object} agent - Agent object
 * @param {HTMLElement} card - Agent card element
 */
function selectAgent(agent, card) {
    // Remove previous selection
    document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));

    // Update selection
    card.classList.add('selected');
    window.currentSelectedAgent = agent;

    // Update UI
    const selectedNameEl = document.getElementById('selectedAgentName');
    if (selectedNameEl) {
        selectedNameEl.textContent = `${agent.name || agent.id} (${agent.managed_file || 'files'})`;
        selectedNameEl.style.color = '#00d4ff';
    }

    // Enable tools that require agent selection
    updateToolAvailability();

    addTerminalLine(`📌 Selected agent: ${agent.name || agent.id}`, 'info');
}

/**
 * Update tool availability based on selection
 */
function updateToolAvailability() {
    const executeBtn = document.getElementById('executeBtn');
    const quickChatBtn = document.getElementById('quickChatBtn');
    const toolSelect = document.getElementById('toolSelector');

    if (!executeBtn || !toolSelect) return;

    const selectedTool = toolSelect.value;
    const agentRequiredTools = [
        'chat_with_agent', 
        'get_agent_info',
        'update_agent',
        'delete_agent',
        'validate_agent_file'
    ];

    // Enable/disable execute button
    const needsAgent = agentRequiredTools.includes(selectedTool);
    executeBtn.disabled = !authenticated || !selectedTool || (needsAgent && !window.currentSelectedAgent);

    // Enable/disable quick chat
    if (quickChatBtn) {
        quickChatBtn.disabled = !authenticated || !window.currentSelectedAgent;
    }
}

/**
 * Quick list agents action
 */
async function quickListAgents() {
    if (!authenticated) {
        addTerminalLine('Please authenticate first', 'warning');
        return;
    }

    await refreshAgents();
}

/**
 * Quick chat with selected agent
 */
async function quickChatWithAgent() {
    if (!window.currentSelectedAgent) {
        addTerminalLine('Please select an agent first', 'warning');
        return;
    }

    const messageEl = document.getElementById('quickMessage');
    const message = messageEl?.value?.trim();

    if (!message) {
        addTerminalLine('Please enter a message', 'warning');
        return;
    }

    try {
        addTerminalLine(`💬 Sending message to ${window.currentSelectedAgent.name}...`, 'info');
        
        const result = await window.mcpClient.callTool('chat_with_agent', {
            agent_id: window.currentSelectedAgent.id,
            message: message,
            task_type: 'analyze'
        });

        const parsed = window.MCPParsers.parseGenericResponse(result);
        
        if (parsed.success) {
            addTerminalLine(`✅ Agent response received`, 'success');
            addTerminalLine(parsed.message, 'info');
        } else {
            addTerminalLine(`❌ Agent error: ${parsed.message}`, 'error');
        }

        // Clear message input
        if (messageEl) messageEl.value = '';
        
    } catch (error) {
        console.error('Chat error:', error);
        addTerminalLine(`❌ Failed to chat: ${error.message}`, 'error');
    }
}

/**
 * Get system status
 */
async function getSystemStatus() {
    if (!authenticated) {
        addTerminalLine('Please authenticate first', 'warning');
        return;
    }

    try {
        addTerminalLine('🔍 Getting system status...', 'info');
        
        const result = await window.mcpClient.callTool('system_status', {});
        const status = window.MCPParsers.parseSystemStatusResponse(result);
        
        if (status) {
            addTerminalLine('📊 System Status:', 'success');
            addTerminalLine(`  Server: ${status.server.status || 'Unknown'}`, 'info');
            addTerminalLine(`  Version: ${status.server.version || 'Unknown'}`, 'info');
            addTerminalLine(`  Agents: ${status.agents.total || 0} total, ${status.agents.active || 0} active`, 'info');
            addTerminalLine(`  Managed Files: ${status.agents.managedFiles || 0}`, 'info');
        } else {
            // Fallback to raw message
            const parsed = window.MCPParsers.parseGenericResponse(result);
            addTerminalLine(parsed.message, 'info');
        }
        
    } catch (error) {
        console.error('Status error:', error);
        addTerminalLine(`❌ Failed to get status: ${error.message}`, 'error');
    }
}

// Export functions for global use
window.listAgents = listAgents;
window.refreshAgents = refreshAgents;
window.displayAgents = displayAgents;
window.selectAgent = selectAgent;
window.updateToolAvailability = updateToolAvailability;
window.quickListAgents = quickListAgents;
window.quickChatWithAgent = quickChatWithAgent;
window.getSystemStatus = getSystemStatus;