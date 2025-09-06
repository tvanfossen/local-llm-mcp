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

// Display agents function moved to agent-helpers.js

// Select agent function moved to agent-helpers.js

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

            // Git Tools
            case 'git_status':
                result = await gitStatus();
                break;

            case 'git_diff':
                result = await gitDiff(parameters);
                break;

            case 'git_commit':
                result = await gitCommit(parameters);
                if (result.success) {
                    addTerminalLine('🎉 Git commit successful!', 'success');
                }
                break;

            case 'git_log':
                result = await gitLog(parameters);
                break;

            // Testing & Validation Tools
            case 'run_tests':
                result = await runTests(parameters);
                break;

            case 'run_pre_commit':
                result = await runPreCommit(parameters);
                break;

            case 'validate_file_length':
                result = await validateFileLength(parameters);
                break;

            case 'validate_agent_file':
                if (!currentSelectedAgent) {
                    addTerminalLine('Please select an agent first', 'warning');
                    return;
                }
                result = await validateAgentFile(currentSelectedAgent.id);
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

        // Git Tools
        case 'git_diff':
            parameters.file_path = getInputValue('git_file_path');
            parameters.staged = document.getElementById('git_staged')?.checked || false;
            break;

        case 'git_commit':
            parameters.message = getInputValue('git_message');
            const filesText = getInputValue('git_files');
            if (filesText) {
                parameters.files = filesText.split('\n').filter(f => f.trim()).map(f => f.trim());
            }
            break;

        case 'git_log':
            parameters.limit = parseInt(getInputValue('git_limit')) || 10;
            parameters.file_path = getInputValue('git_log_file_path');
            break;

        // Testing & Validation Tools
        case 'run_tests':
            parameters.test_path = getInputValue('test_path');
            parameters.coverage = document.getElementById('test_coverage')?.checked !== false;
            parameters.verbose = document.getElementById('test_verbose')?.checked || false;
            break;

        case 'run_pre_commit':
            parameters.hook = getInputValue('precommit_hook');
            parameters.all_files = document.getElementById('precommit_all_files')?.checked || false;
            break;

        case 'validate_file_length':
            const filePathsText = getInputValue('file_paths');
            parameters.file_paths = filePathsText.split('\n').filter(f => f.trim()).map(f => f.trim());
            parameters.max_lines = parseInt(getInputValue('max_lines')) || 300;
            break;

        // No parameters needed for these tools
        case 'list_agents':
        case 'system_status':
        case 'get_agent_file':
        case 'git_status':
        case 'validate_agent_file':
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
        'chat_with_agent': ['message'],
        'git_commit': ['message'],
        'validate_file_length': ['file_paths']
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

// Quick action functions moved to agent-helpers.js

// Tool availability function moved to agent-helpers.js

// Selected agent display function moved to agent-helpers.js

// Utility functions moved to agent-helpers.js
