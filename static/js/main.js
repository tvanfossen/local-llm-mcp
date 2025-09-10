/**
 * Main App - Simplified
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

// Refresh agents list
async function refreshAgents() {
    if (!window.mcpClient) return;
    
    try {
        addTerminalLine('🔄 Refreshing agents...', 'info');
        const result = await window.mcpClient.callTool('list_agents', {});
        
        // Parse response
        const text = result.content?.[0]?.text || '';
        const agentsContainer = document.getElementById('agentsList');
        
        if (text.includes('No agents found')) {
            agentsContainer.innerHTML = '<p style="opacity: 0.7;">No agents found</p>';
            addTerminalLine('No agents found', 'info');
        } else {
            // Simple parsing - just display the raw text for now
            agentsContainer.innerHTML = `<pre style="font-size: 0.85em; color: #8892b0;">${text}</pre>`;
            addTerminalLine('Agents loaded', 'success');
        }
        
    } catch (error) {
        addTerminalLine(`❌ Failed to refresh agents: ${error.message}`, 'error');
    }
}

// Tool selection changed
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
            
            if (prop.type === 'string' && prop.description && prop.description.includes('multi-line')) {
                const textarea = document.createElement('textarea');
                textarea.id = `input_${key}`;
                textarea.className = 'text-area';
                textarea.placeholder = prop.description || '';
                if (isRequired) textarea.required = true;
                div.appendChild(textarea);
            } else if (prop.type === 'boolean') {
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = `input_${key}`;
                div.appendChild(checkbox);
            } else {
                const input = document.createElement('input');
                input.type = prop.type === 'number' ? 'number' : 'text';
                input.id = `input_${key}`;
                input.className = 'tool-input';
                input.placeholder = prop.description || '';
                if (isRequired) input.required = true;
                div.appendChild(input);
            }
            
            toolInputs.appendChild(div);
        });
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