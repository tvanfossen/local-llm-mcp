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
 * Generate git diff inputs
 */
function generateGitDiffInputs() {
    return `
        <div class="form-group">
            <label>File Path (optional):</label>
            <input type="text" class="commit-input" id="git_file_path" placeholder="path/to/file.py (leave empty for all files)">
        </div>
        <div class="form-group">
            <label>Show Staged Changes:</label>
            <input type="checkbox" id="git_staged" style="margin-left: 10px;">
            <small style="color: #8892b0; display: block; margin-top: 5px;">Check to show staged changes only</small>
        </div>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide git operation (not agent-specific)</p>
    `;
}

/**
 * Generate git commit inputs
 */
function generateGitCommitInputs() {
    return `
        <div class="form-group">
            <label>Commit Message:</label>
            <textarea class="text-area" id="git_message" placeholder="Add new feature for user management" required></textarea>
        </div>
        <div class="form-group">
            <label>Files to Add (optional):</label>
            <textarea class="text-area" id="git_files" placeholder="file1.py\\nfile2.py (one per line, leave empty to add all changes)"></textarea>
        </div>
        <p style="color: #ffb86c; font-size: 0.9em;">⚠️ This will create a git commit for the entire repository</p>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide git operation (not agent-specific)</p>
    `;
}

/**
 * Generate git log inputs
 */
function generateGitLogInputs() {
    return `
        <div class="form-group">
            <label>Number of Commits:</label>
            <input type="number" class="commit-input" id="git_limit" value="10" min="1" max="50">
        </div>
        <div class="form-group">
            <label>File Path (optional):</label>
            <input type="text" class="commit-input" id="git_log_file_path" placeholder="path/to/file.py (leave empty for all commits)">
        </div>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide git operation (not agent-specific)</p>
    `;
}

/**
 * Generate run tests inputs
 */
function generateRunTestsInputs() {
    return `
        <div class="form-group">
            <label>Test Path (optional):</label>
            <input type="text" class="commit-input" id="test_path" placeholder="tests/ or tests/test_specific.py (leave empty for all tests)">
        </div>
        <div class="form-group">
            <label>Options:</label>
            <div style="margin-top: 5px;">
                <input type="checkbox" id="test_coverage" checked style="margin-right: 5px;">
                <label for="test_coverage" style="margin-right: 15px;">Generate Coverage Report</label>

                <input type="checkbox" id="test_verbose" style="margin-right: 5px;">
                <label for="test_verbose">Verbose Output</label>
            </div>
        </div>
        <p style="color: #00d4ff; font-size: 0.9em;">🧪 Runs pytest with optional coverage reporting</p>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide testing operation (not agent-specific)</p>
    `;
}

/**
 * Generate pre-commit inputs
 */
function generatePreCommitInputs() {
    return `
        <div class="form-group">
            <label>Hook to Run (optional):</label>
            <input type="text" class="commit-input" id="precommit_hook" placeholder="flake8, black, mypy (leave empty for all hooks)">
        </div>
        <div class="form-group">
            <label>Run on All Files:</label>
            <input type="checkbox" id="precommit_all_files" style="margin-left: 10px;">
            <small style="color: #8892b0; display: block; margin-top: 5px;">Check to run on all files (not just staged changes)</small>
        </div>
        <p style="color: #50fa7b; font-size: 0.9em;">✅ Validates code quality using pre-commit hooks</p>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide validation operation (not agent-specific)</p>
    `;
}

/**
 * Generate file length validation inputs
 */
function generateFileLengthInputs() {
    return `
        <div class="form-group">
            <label>File Paths:</label>
            <textarea class="text-area" id="file_paths" placeholder="api/mcp_tools.py\\ncore/agent.py\\n(one file per line)" required></textarea>
        </div>
        <div class="form-group">
            <label>Maximum Lines:</label>
            <input type="number" class="commit-input" id="max_lines" value="300" min="1" max="1000">
        </div>
        <p style="color: #8892b0; font-size: 0.9em;">📏 Validates that files comply with line count requirements</p>
        <p style="color: #8892b0; font-size: 0.9em;">🌍 System-wide validation operation (not agent-specific)</p>
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
