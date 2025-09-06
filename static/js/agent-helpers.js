/**
 * Agent Operation Helpers
 * Utility functions and display helpers for agent operations
 */

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
 * Update tool availability based on selection
 */
function updateToolAvailability() {
    const executeBtn = document.getElementById('executeBtn');
    const quickChatBtn = document.getElementById('quickChatBtn');
    const toolSelect = document.getElementById('toolSelector');

    const selectedTool = toolSelect.value;
    const agentRequiredTools = ['chat_with_agent', 'get_agent_file', 'validate_agent_file'];

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
