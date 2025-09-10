/**
 * Main Orchestrator Entry Point
 * Initializes the application and manages global state
 */

// Global state
window.authenticated = false;
window.mcpClient = null;
window.currentAgents = [];
window.currentSelectedAgent = null;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Orchestrator initializing...');
    
    // Initialize components
    initializeUI();
    initializeEventListeners();
    checkAuthStatus();
    
    // Set initial states
    updateAuthUI(false);
    updateToolAvailability();
    
    console.log('✅ Orchestrator ready');
});

/**
 * Initialize UI components
 */
function initializeUI() {
    // Set initial terminal message
    addTerminalLine('🤖 MCP-based orchestrator ready. Authenticate to begin.', 'info');
    
    // Disable protected elements initially
    document.querySelectorAll('.auth-protected').forEach(el => {
        el.classList.add('disabled');
    });
    
    // Set initial status indicators
    updateWSStatus('disconnected');
    updateMCPStatus('inactive');
}

/**
 * Initialize event listeners
 */
function initializeEventListeners() {
    // Tool selector change
    const toolSelector = document.getElementById('toolSelector');
    if (toolSelector) {
        toolSelector.addEventListener('change', handleToolSelectionChange);
    }
    
    // Quick message enter key
    const quickMessage = document.getElementById('quickMessage');
    if (quickMessage) {
        quickMessage.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                quickChatWithAgent();
            }
        });
    }
    
    // Private key enter
    const privateKeyInput = document.getElementById('privateKey');
    if (privateKeyInput) {
        privateKeyInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                authenticate();
            }
        });
    }
}

/**
 * Check authentication status on load
 */
function checkAuthStatus() {
    const token = localStorage.getItem('mcp_auth_token');
    const sessionId = localStorage.getItem('mcp_session_id');
    
    if (token && sessionId) {
        console.log('Found existing session, attempting to restore...');
        restoreSession(token, sessionId);
    }
}

/**
 * Restore existing session
 */
async function restoreSession(token, sessionId) {
    try {
        // Initialize MCP client with existing token
        window.mcpClient = new MCPClient(token);
        
        // Test the connection
        const testResult = await window.mcpClient.callTool('system_status', {});
        
        if (testResult && !testResult.isError) {
            window.authenticated = true;
            updateAuthUI(true);
            addTerminalLine('✅ Session restored successfully', 'success');
            
            // Auto-refresh agents
            setTimeout(() => refreshAgents(), 500);
        } else {
            throw new Error('Session invalid');
        }
    } catch (error) {
        console.error('Failed to restore session:', error);
        localStorage.removeItem('mcp_auth_token');
        localStorage.removeItem('mcp_session_id');
        addTerminalLine('⚠️ Previous session expired, please authenticate again', 'warning');
    }
}

/**
 * Update WebSocket status indicator
 */
function updateWSStatus(status) {
    const indicator = document.getElementById('wsIndicator');
    const text = document.getElementById('wsStatus');
    
    if (!indicator || !text) return;
    
    switch(status) {
        case 'connected':
            indicator.style.background = '#00ff88';
            text.textContent = 'Connected';
            break;
        case 'connecting':
            indicator.style.background = '#ffaa00';
            text.textContent = 'Connecting...';
            break;
        default:
            indicator.style.background = '#ff5555';
            text.textContent = 'Disconnected';
    }
}

/**
 * Update MCP status indicator
 */
function updateMCPStatus(status) {
    const indicator = document.getElementById('mcpIndicator');
    const statusText = document.getElementById('mcpStatus');
    
    if (indicator) {
        switch(status) {
            case 'active':
                indicator.style.background = '#00ff88';
                break;
            case 'processing':
                indicator.style.background = '#ffaa00';
                break;
            default:
                indicator.style.background = '#ff5555';
        }
    }
    
    if (statusText) {
        switch(status) {
            case 'active':
                statusText.textContent = 'MCP Ready';
                statusText.style.color = '#00ff88';
                break;
            case 'processing':
                statusText.textContent = 'Processing...';
                statusText.style.color = '#ffaa00';
                break;
            default:
                statusText.textContent = 'MCP Inactive';
                statusText.style.color = '#ff5555';
        }
    }
}

/**
 * Add line to terminal
 */
function addTerminalLine(message, type = 'info') {
    const terminal = document.getElementById('terminal');
    if (!terminal) return;
    
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    
    // Add timestamp
    const timestamp = new Date().toLocaleTimeString();
    line.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
    
    terminal.appendChild(line);
    
    // Auto-scroll to bottom
    terminal.scrollTop = terminal.scrollHeight;
    
    // Limit terminal history
    const maxLines = 100;
    while (terminal.children.length > maxLines) {
        terminal.removeChild(terminal.firstChild);
    }
}

/**
 * Clear terminal
 */
function clearTerminal() {
    const terminal = document.getElementById('terminal');
    if (terminal) {
        terminal.innerHTML = '';
        addTerminalLine('Terminal cleared', 'info');
    }
}

// Export functions for global use
window.addTerminalLine = addTerminalLine;
window.clearTerminal = clearTerminal;
window.updateWSStatus = updateWSStatus;
window.updateMCPStatus = updateMCPStatus;