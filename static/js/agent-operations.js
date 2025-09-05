/**
 * Agent Operations - UI Integration with MCP Tools
 * Handles agent management and operations through MCP protocol
 */

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

        if (result.success && result.data) {
            displayAgents(result.data);
            addTerminalLine(`📚 Loaded ${result.data.length} agents via MCP`, 'success');
        } else {
            // Handle case where no structured data is available
            addTerminalLine('📚 Agents loaded (check terminal for details)', 'info');
            document.getElementById('agentsList').innerHTML = '<p style="opacity: 0.7;">No agents found or data parsing failed</p>';
        }
    } catch (error) {
        addTerminalLine(`Failed to refresh agents: ${error.message}`, 'error');
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
            <div class="agent-file">📄 ${agent.managed_file || 'Unknown file'}</div>
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
    currentSelectedAgent = agent;

    // Update UI
    const selectedNameEl = document.getElementById('selectedAgentName');
    selectedNameEl.textContent = `${agent.name || agent.id} (${agent.managed_file || 'unknown'})`;
    selectedNameEl.style.color = '#00d4ff';

    // Enable tools that require agent selection
    updateToolAvailability();

    addTerminalLine(`📌 Selected agent: ${agent.name || agent.id}`, 'info');
}

/**
 * Execute selected MCP tool
 */
async function executeMCPTool() {
    const toolSelect = document.getElementById('toolSelector');
    const toolName = toolSelect.value;

    if (!toolName) {
        addTerminalLine('Please select a tool', 'warning');
        return;
    }

    if (!authenticated) {
        addTerminalLine('Authentication required', 'error');
        return;
    }

    try {
        const parameters = buildToolParameters(toolName);

        if (!validateToolParameters(toolName, parameters)) {
            return;
        }

        addTerminalLine(`🚀 Executing MCP tool: ${toolName}`, 'info');

        let result;

        switch (toolName) {
            case 'create_agent':
                result = await createAgent(parameters);
                if (result.success) {
                    refreshAgents(); // Refresh the list
                }
                break;

            case 'list_agents':
                result = await listAgents();
                if (result.success && result.data) {
                    displayAgents(result.data);
                }
                break;

            case 'get_agent_info':
                result = await getAgentInfo(parameters.agent_id);
                break;

            case 'delete_agent':
                result = await deleteAgent(parameters.agent_id);
                if (result.success) {
                    refreshAgents(); // Refresh the list
                    currentSelectedAgent = null;
                    updateSelectedAgentDisplay();
                }
                break;

            case 'chat_with_agent':
                if (!currentSelectedAgent) {
                    addTerminalLine('Please select an agent first', 'warning');
                    return;
                }
                result = await chatWithAgent(
                    currentSelectedAgent.id,
                    parameters.message,
                    parameters.task_type
                );
                break;

            case 'get_agent_file':
                if (!currentSelectedAgent) {
                    addTerminalLine('Please select an agent first', 'warning');
                    return;
                }
                result = await getAgentFile(currentSelectedAgent.id);
                break;

            case 'system_status':
                result = await getSystemStatus();
                break;

            default:
                addTerminalLine(`Unknown tool: ${toolName}`, 'error');
                return;
        }

        if (result.success) {
            addTerminalLine(`✅ ${toolName} completed successfully`, 'success');
            if (result.message) {
                addTerminalLine(`📝 ${result.message.substring(0, 100)}...`, 'info');
            }
        } else {
            addTerminalLine(`❌ ${toolName} failed: ${result.error || 'Unknown error'}`, 'error');
        }

        clearToolInputs();

    } catch (error) {
        addTerminalLine(`🚫 Tool execution error: ${error.message}`, 'error');
    }
}

/**
 * Build parameters for the selected tool from UI inputs
 * @param {string} toolName - Name of the tool
 * @returns {object} - Parameters object
 */
function buildToolParameters(toolName) {
    const parameters = {};

    switch (toolName) {
        case 'create_agent':
            parameters.name = getInputValue('agent_name');
            parameters.description = getInputValue('agent_description');
            parameters.system_prompt = getInputValue('agent_system_prompt');
            parameters.managed_file = getInputValue('agent_managed_file');
            parameters.initial_context = getInputValue('agent_initial_context');
            break;

        case 'get_agent_info':
        case 'delete_agent':
            parameters.agent_id = getInputValue('target_agent_id') || (currentSelectedAgent && currentSelectedAgent.id);
            break;

        case 'chat_with_agent':
            parameters.message = getInputValue('chat_message');
            parameters.task_type = getInputValue('chat_task_type') || 'update';
            parameters.context = getInputValue('chat_context');
            break;

        // No parameters needed for these tools
        case 'list_agents':
        case 'system_status':
        case 'get_agent_file':
            break;
    }

    return parameters;
}

/**
 * Validate tool parameters
 * @param {string} toolName - Tool name
 * @param {object} parameters - Parameters to validate
 * @returns {boolean} - True if valid
 */
function validateToolParameters(toolName, parameters) {
    const validationRules = {
        'create_agent': ['name', 'description', 'system_prompt', 'managed_file'],
        'get_agent_info': ['agent_id'],
        'delete_agent': ['agent_id'],
        'chat_with_agent': ['message']
    };

    const required = validationRules[toolName] || [];

    for (const field of required) {
        if (!parameters[field]) {
            addTerminalLine(`Missing required field: ${field}`, 'warning');
            return false;
        }
    }

    return true;
}

/**
 * Quick actions
 */
async function quickListAgents() {
    try {
        await refreshAgents();
    } catch (error) {
        addTerminalLine(`Quick list failed: ${error.message}`, 'error');
    }
}

async function quickChatWithAgent() {
    if (!currentSelectedAgent) {
        addTerminalLine('Please select an agent first', 'warning');
        return;
    }

    const message = document.getElementById('quickMessage').value;
    if (!message) {
        addTerminalLine('Please enter a message', 'warning');
        return;
    }

    try {
        const result = await chatWithAgent(currentSelectedAgent.id, message);

        if (result.success) {
            addTerminalLine(`💬 Chat response from ${currentSelectedAgent.name}:`, 'success');
            addTerminalLine(result.response.message.substring(0, 200) + '...', 'info');
        }

        document.getElementById('quickMessage').value = '';
    } catch (error) {
        addTerminalLine(`Chat failed: ${error.message}`, 'error');
    }
}

/**
 * Update tool availability based on selection
 */
function updateToolAvailability() {
    const executeBtn = document.getElementById('executeBtn');
    const quickChatBtn = document.getElementById('quickChatBtn');
    const toolSelect = document.getElementById('toolSelector');

    const selectedTool = toolSelect.value;
    const agentRequiredTools = ['chat_with_agent', 'get_agent_file'];

    // Enable/disable execute button
    const needsAgent = agentRequiredTools.includes(selectedTool);
    executeBtn.disabled = !authenticated || !selectedTool || (needsAgent && !currentSelectedAgent);

    // Enable/disable quick chat
    quickChatBtn.disabled = !authenticated || !currentSelectedAgent;
}

/**
 * Update selected agent display
 */
function updateSelectedAgentDisplay() {
    const selectedNameEl = document.getElementById('selectedAgentName');

    if (currentSelectedAgent) {
        selectedNameEl.textContent = `${currentSelectedAgent.name} (${currentSelectedAgent.managed_file})`;
        selectedNameEl.style.color = '#00d4ff';
    } else {
        selectedNameEl.textContent = 'No agent selected';
        selectedNameEl.style.color = '#8892b0';
    }

    updateToolAvailability();
}

/**
 * Utility functions
 */
function getInputValue(elementId) {
    const element = document.getElementById(elementId);
    return element ? element.value.trim() : '';
}

function clearToolInputs() {
    const toolInputs = document.getElementById('toolInputs');
    const inputs = toolInputs.querySelectorAll('input, textarea, select');

    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            input.checked = false;
        } else {
            input.value = '';
        }
    });
}
