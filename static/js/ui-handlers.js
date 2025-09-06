/**
 * UI Handlers - Dynamic UI Management for MCP Tools
 * Handles tool input generation and UI updates
 */

/**
 * Update tool inputs based on selected tool
 */
function updateToolInputs() {
    const toolSelect = document.getElementById('toolSelector');
    const toolName = toolSelect.value;
    const container = document.getElementById('toolInputs');

    if (!toolName) {
        container.innerHTML = '<p style="opacity: 0.7; font-style: italic;">Select a tool to see its parameters</p>';
        updateToolAvailability();
        return;
    }

    const toolInputTemplates = {
        'create_agent': generateCreateAgentInputs(),
        'list_agents': generateNoParamsMessage('Lists all agents in the registry'),
        'get_agent_info': generateAgentIdInput('Get detailed information about an agent'),
        'delete_agent': generateAgentIdInput('⚠️ Warning: This will permanently delete the agent'),
        'chat_with_agent': generateChatInputs(),
        'get_agent_file': generateNoParamsMessage('Gets the file content managed by the selected agent'),
        'system_status': generateNoParamsMessage('Displays system and model status information'),
        // Git Tools
        'git_status': generateNoParamsMessage('Check git repository status and changes (system-wide operation)'),
        'git_diff': generateGitDiffInputs(),
        'git_commit': generateGitCommitInputs(),
        'git_log': generateGitLogInputs(),
        // Testing & Validation Tools
        'run_tests': generateRunTestsInputs(),
        'run_pre_commit': generatePreCommitInputs(),
        'validate_file_length': generateFileLengthInputs(),
        'validate_agent_file': generateAgentIdInput('Validate agent file meets all requirements')
    };

    container.innerHTML = toolInputTemplates[toolName] || '<p style="color: #ff5555;">Unknown tool selected</p>';
    updateToolAvailability();
}

// Template generation functions moved to ui-templates.js




/**
 * Handle tool selection changes
 */
function onToolSelectionChange() {
    updateToolInputs();

    // Auto-fill agent ID if an agent is selected
    const toolSelect = document.getElementById('toolSelector');
    const agentIdInput = document.getElementById('target_agent_id');

    if (agentIdInput && currentSelectedAgent) {
        agentIdInput.value = currentSelectedAgent.id;
    }
}

/**
 * Format MCP response for display
 */
function formatMCPResponse(response) {
    if (typeof response === 'string') {
        return response;
    }

    if (response.message) {
        return response.message;
    }

    if (response.text) {
        return response.text;
    }

    return JSON.stringify(response, null, 2);
}


/**
 * Show loading state for buttons
 */
function setButtonLoading(buttonId, loading) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    if (loading) {
        button.disabled = true;
        button.textContent = button.textContent.replace(/^/, '⏳ ');
    } else {
        button.disabled = false;
        button.textContent = button.textContent.replace('⏳ ', '');
    }
}

/**
 * Handle keyboard shortcuts
 */
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + Enter to execute tool
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        const executeBtn = document.getElementById('executeBtn');
        if (!executeBtn.disabled) {
            executeMCPTool();
        }
        event.preventDefault();
    }

    // Escape to clear selection
    if (event.key === 'Escape') {
        currentSelectedAgent = null;
        document.querySelectorAll('.agent-card').forEach(card => {
            card.classList.remove('selected');
        });
        updateSelectedAgentDisplay();
    }
});

/**
 * Auto-resize textareas
 */
function setupAutoResize() {
    document.addEventListener('input', function(event) {
        if (event.target.classList.contains('text-area')) {
            event.target.style.height = 'auto';
            event.target.style.height = event.target.scrollHeight + 'px';
        }
    });
}

/**
 * Initialize UI handlers
 */
function initializeUIHandlers() {
    setupAutoResize();

    // Add event listener for tool selection
    const toolSelect = document.getElementById('toolSelector');
    if (toolSelect) {
        toolSelect.addEventListener('change', onToolSelectionChange);
    }

    // Set up periodic UI updates
    setInterval(updateToolAvailability, 1000);
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        addTerminalLine('📋 Copied to clipboard', 'success');
    } catch (error) {
        addTerminalLine('Failed to copy to clipboard', 'error');
    }
}

/**
 * Download content as file
 */
function downloadAsFile(content, filename, type = 'text/plain') {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    addTerminalLine(`💾 Downloaded: ${filename}`, 'success');
}

/**
 * Show tooltip
 */
function showTooltip(element, text) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    tooltip.style.cssText = `
        position: absolute;
        background: rgba(26, 31, 58, 0.9);
        color: #e0e6ed;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.8em;
        border: 1px solid #2d3561;
        z-index: 1000;
        pointer-events: none;
    `;

    document.body.appendChild(tooltip);

    const rect = element.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.bottom + 5) + 'px';

    setTimeout(() => {
        if (tooltip.parentNode) {
            tooltip.parentNode.removeChild(tooltip);
        }
    }, 3000);
}

// Initialize UI handlers when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeUIHandlers);
} else {
    initializeUIHandlers();
}
