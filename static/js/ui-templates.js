/**
 * UI Templates - HTML Generation for MCP Tool Forms
 * Handles generation of dynamic form templates
 */

/**
 * Generate create agent input form
 */
function generateCreateAgentInputs() {
    return `
        <div class="form-group">
            <label>Agent Name:</label>
            <input type="text" class="commit-input" id="agent_name" placeholder="my-agent" required>
        </div>
        <div class="form-group">
            <label>Description:</label>
            <input type="text" class="commit-input" id="agent_description" placeholder="Manages project documentation" required>
        </div>
        <div class="form-group">
            <label>System Prompt:</label>
            <textarea class="text-area" id="agent_system_prompt" placeholder="You are a documentation expert..." required></textarea>
        </div>
        <div class="form-group">
            <label>Managed File:</label>
            <input type="text" class="commit-input" id="agent_managed_file" placeholder="README.md" required>
        </div>
        <div class="form-group">
            <label>Initial Context (optional):</label>
            <textarea class="text-area" id="agent_initial_context" placeholder="Optional starting context..."></textarea>
        </div>
    `;
}

/**
 * Generate agent ID input
 */
function generateAgentIdInput(description) {
    const warningStyle = description.includes('Warning') ? 'color: #ff5555;' : '';

    return `
        <div class="form-group">
            <label>Agent ID:</label>
            <input type="text" class="commit-input" id="target_agent_id" placeholder="Select agent or enter ID" required>
        </div>
        <p style="font-size: 0.9em; ${warningStyle}">${description}</p>
        ${currentSelectedAgent ?
            `<p style="color: #00d4ff; font-size: 0.9em;">💡 Currently selected: ${currentSelectedAgent.name} (${currentSelectedAgent.id})</p>` :
            '<p style="color: #8892b0; font-size: 0.9em;">💡 Select an agent from the list or enter ID manually</p>'
        }
    `;
}

/**
 * Generate chat inputs
 */
function generateChatInputs() {
    return `
        <div class="form-group">
            <label>Message:</label>
            <textarea class="text-area" id="chat_message" placeholder="Your instruction to the agent..." required></textarea>
        </div>
        <div class="form-group">
            <label>Task Type:</label>
            <select class="tool-selector" id="chat_task_type">
                <option value="update">Update</option>
                <option value="create">Create</option>
                <option value="analyze">Analyze</option>
                <option value="refactor">Refactor</option>
                <option value="debug">Debug</option>
                <option value="document">Document</option>
                <option value="test">Test</option>
            </select>
        </div>
        <div class="form-group">
            <label>Context (optional):</label>
            <textarea class="text-area" id="chat_context" placeholder="Additional context..."></textarea>
        </div>
        ${currentSelectedAgent ?
            `<p style="color: #00d4ff; font-size: 0.9em;">💬 Chatting with: ${currentSelectedAgent.name}</p>` :
            '<p style="color: #ff5555; font-size: 0.9em;">⚠️ Please select an agent first</p>'
        }
    `;
}

/**
 * Generate no parameters message
 */
function generateNoParamsMessage(description) {
    return `
        <p style="color: #8892b0; font-style: italic; text-align: center; padding: 20px;">
            ${description}<br><br>
            No parameters required - click Execute to run this tool.
        </p>
    `;
}

/**
 * Create status badge
 */
function createStatusBadge(status, text) {
    const colors = {
        success: '#50fa7b',
        error: '#ff5555',
        warning: '#ffb86c',
        info: '#00d4ff'
    };

    return `<span style="
        display: inline-block;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 0.8em;
        background: ${colors[status] || colors.info}20;
        color: ${colors[status] || colors.info};
        border: 1px solid ${colors[status] || colors.info}40;
    ">${text}</span>`;
}
