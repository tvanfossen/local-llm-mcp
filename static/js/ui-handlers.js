/**
 * UI Event Handlers
 * Handles all UI interactions and updates
 */

/**
 * Handle tool selection change
 */
function handleToolSelectionChange() {
    const toolSelector = document.getElementById('toolSelector');
    const toolInputs = document.getElementById('toolInputs');
    const executeBtn = document.getElementById('executeBtn');
    
    if (!toolSelector || !toolInputs) return;
    
    const selectedTool = toolSelector.value;
    
    // Clear previous inputs
    toolInputs.innerHTML = '';
    
    if (!selectedTool) {
        if (executeBtn) executeBtn.disabled = true;
        return;
    }
    
    // Generate inputs based on tool
    const inputs = generateToolInputs(selectedTool);
    toolInputs.innerHTML = inputs;
    
    // Update button availability
    updateToolAvailability();
    
    // Add event listeners to new inputs
    attachInputValidation();
}

/**
 * Generate input fields for selected tool
 * @param {string} toolName - Name of the selected tool
 * @returns {string} HTML string for inputs
 */
function generateToolInputs(toolName) {
    const toolInputConfigs = {
        'create_agent': [
            { name: 'name', label: 'Agent Name', type: 'text', required: true },
            { name: 'description', label: 'Description', type: 'text', required: true },
            { name: 'managed_file', label: 'File to Manage', type: 'text', required: true },
            { name: 'system_prompt', label: 'System Prompt', type: 'textarea', required: true }
        ],
        'chat_with_agent': [
            { name: 'agent_id', label: 'Agent ID', type: 'agent-select', required: true },
            { name: 'message', label: 'Message', type: 'textarea', required: true },
            { name: 'task_type', label: 'Task Type', type: 'select', 
              options: ['analyze', 'update', 'create', 'refactor', 'debug', 'document', 'test'],
              required: true }
        ],
        'update_agent': [
            { name: 'agent_id', label: 'Agent ID', type: 'agent-select', required: true },
            { name: 'name', label: 'New Name', type: 'text' },
            { name: 'description', label: 'New Description', type: 'text' },
            { name: 'system_prompt', label: 'New System Prompt', type: 'textarea' }
        ],
        'delete_agent': [
            { name: 'agent_id', label: 'Agent ID', type: 'agent-select', required: true },
            { name: 'force', label: 'Force Delete', type: 'checkbox' }
        ],
        'read_file': [
            { name: 'file_path', label: 'File Path', type: 'text', required: true },
            { name: 'start_line', label: 'Start Line', type: 'number', min: 1 },
            { name: 'end_line', label: 'End Line', type: 'number', min: 1 },
            { name: 'show_line_numbers', label: 'Show Line Numbers', type: 'checkbox', checked: true }
        ],
        'write_file': [
            { name: 'file_path', label: 'File Path', type: 'text', required: true },
            { name: 'content', label: 'Content', type: 'textarea', required: true },
            { name: 'overwrite', label: 'Overwrite if Exists', type: 'checkbox' },
            { name: 'create_dirs', label: 'Create Directories', type: 'checkbox', checked: true }
        ],
        'list_files': [
            { name: 'directory_path', label: 'Directory', type: 'text', placeholder: '.' },
            { name: 'pattern', label: 'Pattern', type: 'text', placeholder: '*.py' },
            { name: 'recursive', label: 'Recursive', type: 'checkbox' },
            { name: 'include_hidden', label: 'Include Hidden', type: 'checkbox' }
        ],
        'git_commit': [
            { name: 'message', label: 'Commit Message', type: 'text', required: true },
            { name: 'files', label: 'Files (comma-separated)', type: 'text', placeholder: 'Leave empty for all' }
        ],
        'run_tests': [
            { name: 'test_path', label: 'Test Path', type: 'text', placeholder: 'src/' },
            { name: 'coverage', label: 'Generate Coverage', type: 'checkbox', checked: true },
            { name: 'verbose', label: 'Verbose Output', type: 'checkbox' }
        ]
    };
    
    const config = toolInputConfigs[toolName] || [];
    
    if (config.length === 0) {
        return '<p style="opacity: 0.7;">No parameters required for this tool</p>';
    }
    
    return config.map(input => {
        const requiredAttr = input.required ? 'required' : '';
        const inputId = `tool_input_${input.name}`;
        
        let html = `<div class="form-group">`;
        html += `<label for="${inputId}">${input.label}${input.required ? ' *' : ''}</label>`;
        
        switch(input.type) {
            case 'textarea':
                html += `<textarea id="${inputId}" name="${input.name}" 
                        class="text-area" ${requiredAttr}></textarea>`;
                break;
                
            case 'checkbox':
                html += `<input type="checkbox" id="${inputId}" name="${input.name}" 
                        ${input.checked ? 'checked' : ''}>`;
                break;
                
            case 'number':
                html += `<input type="number" id="${inputId}" name="${input.name}" 
                        class="tool-input" ${input.min ? `min="${input.min}"` : ''} 
                        ${input.max ? `max="${input.max}"` : ''} ${requiredAttr}>`;
                break;
                
            case 'select':
                html += `<select id="${inputId}" name="${input.name}" class="tool-selector" ${requiredAttr}>`;
                html += `<option value="">Select...</option>`;
                input.options.forEach(opt => {
                    html += `<option value="${opt}">${opt}</option>`;
                });
                html += `</select>`;
                break;
                
            case 'agent-select':
                html += `<select id="${inputId}" name="${input.name}" class="tool-selector" ${requiredAttr}>`;
                html += `<option value="">Select agent...</option>`;
                if (window.currentAgents) {
                    window.currentAgents.forEach(agent => {
                        const selected = window.currentSelectedAgent?.id === agent.id ? 'selected' : '';
                        html += `<option value="${agent.id}" ${selected}>${agent.name || agent.id}</option>`;
                    });
                }
                html += `</select>`;
                break;
                
            default:
                html += `<input type="${input.type || 'text'}" id="${inputId}" 
                        name="${input.name}" class="tool-input" 
                        ${input.placeholder ? `placeholder="${input.placeholder}"` : ''} 
                        ${requiredAttr}>`;
        }
        
        html += `</div>`;
        return html;
    }).join('');
}

/**
 * Execute selected MCP tool
 */
async function executeMCPTool() {
    const toolSelector = document.getElementById('toolSelector');
    const selectedTool = toolSelector?.value;
    
    if (!selectedTool) {
        addTerminalLine('Please select a tool', 'warning');
        return;
    }
    
    // Gather input values
    const inputs = {};
    document.querySelectorAll('#toolInputs input, #toolInputs textarea, #toolInputs select').forEach(el => {
        if (el.type === 'checkbox') {
            inputs[el.name] = el.checked;
        } else if (el.value) {
            // Parse arrays if needed
            if (el.name === 'files' && el.value.includes(',')) {
                inputs[el.name] = el.value.split(',').map(f => f.trim()).filter(f => f);
            } else {
                inputs[el.name] = el.value;
            }
        }
    });
    
    // Validate required fields
    const requiredFields = document.querySelectorAll('#toolInputs [required]');
    for (let field of requiredFields) {
        if (!field.value) {
            addTerminalLine(`Missing required field: ${field.previousElementSibling.textContent}`, 'error');
            field.focus();
            return;
        }
    }
    
    try {
        updateMCPStatus('processing');
        addTerminalLine(`🔧 Executing tool: ${selectedTool}`, 'info');
        
        const result = await window.mcpClient.callTool(selectedTool, inputs);
        
        // Parse response based on tool type
        let parsed;
        if (selectedTool === 'list_agents') {
            const agents = window.MCPParsers.parseListAgentsResponse(result);
            if (agents.length > 0) {
                window.currentAgents = agents;
                displayAgents(agents);
            }
            parsed = window.MCPParsers.parseGenericResponse(result);
        } else if (selectedTool === 'get_agent_info') {
            const agentInfo = window.MCPParsers.parseAgentInfoResponse(result);
            if (agentInfo) {
                addTerminalLine(`Agent: ${agentInfo.name} (${agentInfo.id})`, 'success');
                addTerminalLine(`Files: ${agentInfo.managed_files_count}, Interactions: ${agentInfo.total_interactions}`, 'info');
            }
            parsed = window.MCPParsers.parseGenericResponse(result);
        } else if (selectedTool === 'system_status') {
            const status = window.MCPParsers.parseSystemStatusResponse(result);
            if (status) {
                addTerminalLine('System Status:', 'success');
                addTerminalLine(`  Server: ${status.server.status || 'Unknown'}`, 'info');
                addTerminalLine(`  Agents: ${status.agents.total || 0}`, 'info');
            }
            parsed = window.MCPParsers.parseGenericResponse(result);
        } else {
            parsed = window.MCPParsers.parseGenericResponse(result);
        }
        
        if (parsed.success) {
            addTerminalLine('✅ Tool executed successfully', 'success');
            if (parsed.message) {
                // Split long messages into multiple lines
                const lines = parsed.message.split('\n');
                lines.forEach(line => {
                    if (line.trim()) {
                        addTerminalLine(line, 'info');
                    }
                });
            }
            
            // Refresh agents if agent-related tool was used
            if (['create_agent', 'delete_agent', 'update_agent'].includes(selectedTool)) {
                setTimeout(() => refreshAgents(), 500);
            }
        } else {
            addTerminalLine(`❌ Tool execution failed: ${parsed.message}`, 'error');
        }
        
    } catch (error) {
        console.error('Tool execution error:', error);
        addTerminalLine(`❌ Error: ${error.message}`, 'error');
    } finally {
        updateMCPStatus('active');
    }
}

/**
 * Attach validation to input fields
 */
function attachInputValidation() {
    // Add real-time validation for file paths
    document.querySelectorAll('input[name="file_path"], input[name="managed_file"]').forEach(input => {
        input.addEventListener('input', function() {
            const value = this.value;
            if (value && (value.includes('..') || value.startsWith('/'))) {
                this.classList.add('error');
                this.setCustomValidity('Path must be relative and cannot contain ..');
            } else {
                this.classList.remove('error');
                this.setCustomValidity('');
            }
        });
    });
    
    // Add validation for agent names
    document.querySelectorAll('input[name="name"]').forEach(input => {
        input.addEventListener('input', function() {
            const value = this.value;
            if (value && !/^[a-zA-Z0-9_-]+$/.test(value)) {
                this.classList.add('error');
                this.setCustomValidity('Name can only contain letters, numbers, hyphens, and underscores');
            } else {
                this.classList.remove('error');
                this.setCustomValidity('');
            }
        });
    });
}

/**
 * Update authentication UI
 * @param {boolean} isAuthenticated - Authentication status
 */
function updateAuthUI(isAuthenticated) {
    window.authenticated = isAuthenticated;
    
    const authIndicator = document.getElementById('authIndicator');
    const authIndicator2 = document.getElementById('authIndicator2');
    const authStatusText = document.getElementById('authStatusText');
    const authStatus2 = document.getElementById('authStatus2');
    const authSessionInfo = document.getElementById('authSessionInfo');
    const authBtn = document.getElementById('authBtn');
    
    if (isAuthenticated) {
        // Update indicators
        if (authIndicator) authIndicator.style.background = '#00ff88';
        if (authIndicator2) authIndicator2.style.background = '#00ff88';
        
        // Update text
        if (authStatusText) authStatusText.textContent = 'Authenticated';
        if (authStatus2) authStatus2.textContent = 'Authenticated';
        
        // Update session info
        const sessionId = localStorage.getItem('mcp_session_id');
        if (authSessionInfo && sessionId) {
            authSessionInfo.textContent = `Session: ${sessionId.substring(0, 8)}...`;
        }
        
        // Update button
        if (authBtn) {
            authBtn.textContent = 'Re-authenticate';
            authBtn.classList.add('authenticated');
        }
        
        // Enable protected panels
        document.querySelectorAll('.auth-protected').forEach(el => {
            el.classList.remove('disabled');
        });
        
        // Update MCP status
        updateMCPStatus('active');
        
    } else {
        // Update indicators
        if (authIndicator) authIndicator.style.background = '#ff5555';
        if (authIndicator2) authIndicator2.style.background = '#ff5555';
        
        // Update text
        if (authStatusText) authStatusText.textContent = 'Not Authenticated';
        if (authStatus2) authStatus2.textContent = 'Not Authenticated';
        
        // Update session info
        if (authSessionInfo) {
            authSessionInfo.textContent = 'MCP operations require authentication';
        }
        
        // Update button
        if (authBtn) {
            authBtn.textContent = 'Authenticate';
            authBtn.classList.remove('authenticated');
        }
        
        // Disable protected panels
        document.querySelectorAll('.auth-protected').forEach(el => {
            el.classList.add('disabled');
        });
        
        // Update MCP status
        updateMCPStatus('inactive');
    }
}

// Export functions
window.handleToolSelectionChange = handleToolSelectionChange;
window.generateToolInputs = generateToolInputs;
window.executeMCPTool = executeMCPTool;
window.attachInputValidation = attachInputValidation;
window.updateAuthUI = updateAuthUI;