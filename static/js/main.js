/**
 * Main App - With Agent Cards
 */

window.currentAgents = [];
window.availableTools = {};
window.selectedAgent = null;

// Terminal logging
function addTerminalLine(message, type = 'info') {
    const terminal = document.getElementById('terminal');
    if (!terminal) return;

    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

// Update auth UI
function updateAuthUI(isAuthenticated) {
    const indicator = document.getElementById('authIndicator');
    const statusText = document.getElementById('authStatusText');

    if (indicator) {
        indicator.style.background = isAuthenticated ? '#50fa7b' : '#ff5555';
    }

    if (statusText) {
        statusText.textContent = isAuthenticated ? 'Authenticated' : 'Not Authenticated';
    }

    // Enable/disable protected elements
    document.querySelectorAll('.auth-protected').forEach(el => {
        el.style.opacity = isAuthenticated ? '1' : '0.5';
        el.style.pointerEvents = isAuthenticated ? 'auto' : 'none';
    });
}

// Load available MCP tools dynamically
async function loadMCPTools() {
    if (!window.mcpClient) return;

    try {
        addTerminalLine('📋 Loading available MCP tools...', 'info');
        const result = await window.mcpClient.listTools();

        if (result && result.tools) {
            window.availableTools = {};
            const toolSelector = document.getElementById('toolSelector');

            // Clear and rebuild selector
            toolSelector.innerHTML = '<option value="">Select a tool...</option>';

            result.tools.forEach(tool => {
                window.availableTools[tool.name] = tool;
                const option = document.createElement('option');
                option.value = tool.name;
                option.textContent = `${tool.name} - ${tool.description || 'No description'}`;
                toolSelector.appendChild(option);
            });

            addTerminalLine(`✅ Loaded ${result.tools.length} tools`, 'success');
        }
    } catch (error) {
        addTerminalLine(`❌ Failed to load tools: ${error.message}`, 'error');
    }
}

// Parse agents from the response text
function parseAgents(responseText) {
    const agents = [];

    // Look for pattern: 🤖 **Name** (ID: xxx)
    const lines = responseText.split('\n');
    let currentAgent = null;

    for (const line of lines) {
        // Check for agent header line
        if (line.includes('🤖')) {
            // Save previous agent if exists
            if (currentAgent) {
                agents.push(currentAgent);
            }

            // Extract name and ID from line like: 🤖 **pyChessArchitect** (ID: 265b3ef2... )
            const nameMatch = line.match(/\*\*([^*]+)\*\*/);
            const idMatch = line.match(/ID:\s*([^)]+)/);

            if (nameMatch && idMatch) {
                currentAgent = {
                    name: nameMatch[1].trim(),
                    id: idMatch[1].trim().replace(/\.\.\./g, '').trim(),
                    description: '',
                    filesCount: 0,
                    interactions: 0,
                    successRate: 'N/A'
                };
            }
        } else if (currentAgent) {
            // Parse additional info for current agent
            if (line.includes('Description:')) {
                currentAgent.description = line.split('Description:')[1].trim();
            }
            if (line.includes('Managing:')) {
                const filesMatch = line.match(/(\d+)\s+file/);
                if (filesMatch) {
                    currentAgent.filesCount = parseInt(filesMatch[1]);
                }
            }
            if (line.includes('interactions')) {
                const intMatch = line.match(/(\d+)\s+interaction/);
                if (intMatch) {
                    currentAgent.interactions = parseInt(intMatch[1]);
                }
            }
            if (line.includes('Success:')) {
                const successMatch = line.match(/Success:\s*([^\s]+)/);
                if (successMatch) {
                    currentAgent.successRate = successMatch[1];
                }
            }
        }
    }

    // Don't forget the last agent
    if (currentAgent) {
        agents.push(currentAgent);
    }

    return agents;
}

// Create agent card element
function createAgentCard(agent) {
    const card = document.createElement('div');
    card.className = 'agent-card';
    card.dataset.agentId = agent.id;

    const nameDiv = document.createElement('div');
    nameDiv.className = 'agent-name';
    nameDiv.textContent = agent.name;

    const idDiv = document.createElement('div');
    idDiv.className = 'agent-id';
    idDiv.textContent = `ID: ${agent.id.substring(0, 12)}...`;

    const fileDiv = document.createElement('div');
    fileDiv.className = 'agent-file';
    fileDiv.textContent = agent.filesCount === 1 ? '📄 1 file' : `📁 ${agent.filesCount} files`;

    const statsDiv = document.createElement('div');
    statsDiv.className = 'agent-stats';
    statsDiv.innerHTML = `
        <span>🔄 ${agent.interactions}</span>
        <span>✅ ${agent.successRate}</span>
    `;

    card.appendChild(nameDiv);
    card.appendChild(idDiv);
    card.appendChild(fileDiv);
    card.appendChild(statsDiv);

    // Add click handler
    card.addEventListener('click', () => {
        // Remove selected from all cards
        document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
        // Add selected to this card
        card.classList.add('selected');
        // Store selected agent
        window.selectedAgent = agent;
        // Auto-fill agent_id if input exists
        const agentInput = document.getElementById('input_agent_id');
        if (agentInput) {
            agentInput.value = agent.id;
        }
        addTerminalLine(`Selected agent: ${agent.name}`, 'info');
    });

    return card;
}

// Refresh agents list - NEW VERSION WITH CARDS
async function refreshAgents() {
    if (!window.mcpClient) return;

    try {
        addTerminalLine('🔄 Refreshing agents...', 'info');
        const result = await window.mcpClient.callTool('agent_operations', {operation: 'list'});

        // Get the text from the response
        let responseText = '';
        if (result && result.content && result.content[0]) {
            responseText = result.content[0].text || '';
        }

        const agentsContainer = document.getElementById('agentsList');

        if (!responseText || responseText.includes('No agents found')) {
            agentsContainer.innerHTML = '<p style="opacity: 0.7;">No agents found</p>';
            addTerminalLine('No agents found', 'info');
            return;
        }

        // Parse agents from response
        const agents = parseAgents(responseText);
        window.currentAgents = agents;

        if (agents.length > 0) {
            // Clear container
            agentsContainer.innerHTML = '';

            // Create and add agent cards
            agents.forEach(agent => {
                const card = createAgentCard(agent);
                agentsContainer.appendChild(card);
            });

            addTerminalLine(`Loaded ${agents.length} agents as cards`, 'success');
        } else {
            // Couldn't parse - show raw text as fallback
            agentsContainer.innerHTML = `<pre style="font-size: 0.85em; color: #8892b0;">${responseText}</pre>`;
            addTerminalLine('Showing raw agent data (parsing failed)', 'warning');
        }

    } catch (error) {
        addTerminalLine(`❌ Failed to refresh agents: ${error.message}`, 'error');
    }
}

// Tool selection changed - WITH AGENT AUTO-FILL
function onToolSelected() {
    const toolSelector = document.getElementById('toolSelector');
    const toolInputs = document.getElementById('toolInputs');
    const selectedTool = toolSelector.value;

    toolInputs.innerHTML = '';

    if (!selectedTool || !window.availableTools[selectedTool]) {
        return;
    }

    const tool = window.availableTools[selectedTool];

    // Generate inputs based on tool schema
    if (tool.inputSchema && tool.inputSchema.properties) {
        const props = tool.inputSchema.properties;
        const required = tool.inputSchema.required || [];

        Object.keys(props).forEach(key => {
            const prop = props[key];
            const isRequired = required.includes(key);

            const div = document.createElement('div');
            div.className = 'form-group';

            const label = document.createElement('label');
            label.textContent = `${key}${isRequired ? ' *' : ''}:`;
            div.appendChild(label);

            let inputElement;

            if (prop.type === 'string' && prop.description && prop.description.includes('multi-line')) {
                inputElement = document.createElement('textarea');
                inputElement.className = 'text-area';
            } else if (prop.type === 'boolean') {
                inputElement = document.createElement('input');
                inputElement.type = 'checkbox';
            } else {
                inputElement = document.createElement('input');
                inputElement.type = prop.type === 'number' ? 'number' : 'text';
                inputElement.className = 'tool-input';
            }

            inputElement.id = `input_${key}`;
            inputElement.placeholder = prop.description || '';
            if (isRequired && inputElement.type !== 'checkbox') {
                inputElement.required = true;
            }

            // AUTO-FILL AGENT_ID IF SELECTED
            if (key === 'agent_id' && window.selectedAgent) {
                inputElement.value = window.selectedAgent.id;
            }

            div.appendChild(inputElement);
            toolInputs.appendChild(div);
        });

        // Show selected agent info if relevant
        if (props.agent_id && window.selectedAgent) {
            const info = document.createElement('div');
            info.style.cssText = 'margin-top: 10px; padding: 8px; background: rgba(0,212,255,0.1); border-radius: 4px; color: #00d4ff; font-size: 0.9em;';
            info.textContent = `✅ Using selected agent: ${window.selectedAgent.name}`;
            toolInputs.appendChild(info);
        }
    } else {
        toolInputs.innerHTML = '<p style="opacity: 0.7;">No parameters required</p>';
    }
}

// Execute selected tool
async function executeTool() {
    const toolSelector = document.getElementById('toolSelector');
    const selectedTool = toolSelector.value;

    if (!selectedTool || !window.mcpClient) {
        addTerminalLine('Select a tool first', 'warning');
        return;
    }

    const tool = window.availableTools[selectedTool];
    const args = {};

    // Gather inputs
    if (tool.inputSchema && tool.inputSchema.properties) {
        Object.keys(tool.inputSchema.properties).forEach(key => {
            const input = document.getElementById(`input_${key}`);
            if (input) {
                if (input.type === 'checkbox') {
                    args[key] = input.checked;
                } else if (input.value) {
                    args[key] = input.value;
                }
            }
        });
    }

    try {
        addTerminalLine(`🔧 Executing: ${selectedTool}`, 'info');
        const result = await window.mcpClient.callTool(selectedTool, args);

        const text = result.content?.[0]?.text || 'No response';
        addTerminalLine(`✅ Success: ${text.substring(0, 200)}...`, 'success');

        // Refresh agents if it was an agent-related operation
        if (selectedTool.includes('agent')) {
            await refreshAgents();
        }

    } catch (error) {
        addTerminalLine(`❌ Error: ${error.message}`, 'error');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    addTerminalLine('🚀 MCP Debug Interface Ready', 'info');
    updateAuthUI(false);
});
