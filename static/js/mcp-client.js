/**
 * MCP Client - Complete Implementation with Authentication
 * Handles all MCP protocol communication and authentication
 */

class MCPClient {
    constructor(sessionToken) {
        this.sessionToken = sessionToken;
        this.baseUrl = '/mcp';
    }

    /**
     * Call an MCP tool
     * @param {string} toolName - Name of the tool
     * @param {object} args - Tool arguments
     * @returns {Promise<object>} Tool response
     */
    async callTool(toolName, args = {}) {
        const request = {
            jsonrpc: "2.0",
            id: Date.now(),
            method: "tools/call",
            params: {
                name: toolName,
                arguments: args
            }
        };

        try {
            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.sessionToken}`
                },
                body: JSON.stringify(request)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const jsonrpcResponse = await response.json();

            if (jsonrpcResponse.error) {
                throw new Error(jsonrpcResponse.error.message || 'MCP error');
            }

            return jsonrpcResponse.result;

        } catch (error) {
            console.error('MCP call failed:', error);
            throw error;
        }
    }
}

/**
 * Main authentication function
 * Called when user clicks the Authenticate button
 */
async function authenticate() {
    const keyInput = document.getElementById('privateKey');
    const authBtn = document.getElementById('authBtn');
    
    if (!keyInput || !authBtn) {
        console.error('Authentication elements not found');
        return;
    }

    const privateKey = keyInput.value.trim();
    
    if (!privateKey) {
        addTerminalLine('❌ Please paste your RSA private key', 'error');
        keyInput.classList.add('error');
        return;
    }

    // Validate key format
    if (!privateKey.includes('BEGIN RSA PRIVATE KEY') && !privateKey.includes('BEGIN PRIVATE KEY')) {
        addTerminalLine('❌ Invalid key format. Please paste a valid RSA private key', 'error');
        keyInput.classList.add('error');
        return;
    }

    keyInput.classList.remove('error');
    authBtn.disabled = true;
    authBtn.textContent = 'Authenticating...';

    try {
        addTerminalLine('🔐 Authenticating with MCP server...', 'info');
        
        const response = await fetch('/api/orchestrator/authenticate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ private_key: privateKey })
        });

        const data = await response.json();

        if (response.ok && data.session_token) {
            // Authentication successful
            window.authenticated = true;
            window.sessionToken = data.session_token;
            window.sessionId = data.session_id;
            
            // Store in localStorage for session persistence
            localStorage.setItem('mcp_auth_token', data.session_token);
            localStorage.setItem('mcp_session_id', data.session_id);
            
            // Calculate session expiry
            if (data.expires_in) {
                window.sessionExpiry = Date.now() + (data.expires_in * 1000);
                localStorage.setItem('mcp_session_expiry', window.sessionExpiry);
            }
            
            // Initialize MCP client with token
            window.mcpClient = new MCPClient(data.session_token);
            
            // Update UI
            updateAuthUI(true);
            updateMCPStatus('active');
            
            // Clear the key input for security
            keyInput.value = '';
            
            addTerminalLine('✅ Authentication successful!', 'success');
            addTerminalLine(`📍 Session ID: ${data.session_id.substring(0, 8)}...`, 'info');
            
            if (data.expires_in) {
                const minutes = Math.floor(data.expires_in / 60);
                addTerminalLine(`⏱️ Session expires in ${minutes} minutes`, 'info');
            }
            
            // Auto-refresh agents after authentication
            setTimeout(() => {
                addTerminalLine('🔄 Loading agents...', 'info');
                refreshAgents();
            }, 500);
            
        } else {
            // Authentication failed
            const errorMsg = data.error || 'Authentication failed';
            throw new Error(errorMsg);
        }
        
    } catch (error) {
        console.error('Authentication error:', error);
        addTerminalLine(`❌ Authentication failed: ${error.message}`, 'error');
        keyInput.classList.add('error');
        
        // Clear any stored session
        localStorage.removeItem('mcp_auth_token');
        localStorage.removeItem('mcp_session_id');
        localStorage.removeItem('mcp_session_expiry');
        
        window.authenticated = false;
        window.sessionToken = null;
        window.mcpClient = null;
        
        updateAuthUI(false);
        updateMCPStatus('inactive');
        
    } finally {
        authBtn.disabled = false;
        authBtn.textContent = window.authenticated ? 'Re-authenticate' : 'Authenticate';
    }
}

/**
 * Handle session expiry
 */
function handleSessionExpiry() {
    window.authenticated = false;
    window.sessionToken = null;
    window.sessionId = null;
    window.sessionExpiry = null;
    window.mcpClient = null;
    
    // Clear localStorage
    localStorage.removeItem('mcp_auth_token');
    localStorage.removeItem('mcp_session_id');
    localStorage.removeItem('mcp_session_expiry');
    
    // Update UI
    updateAuthUI(false);
    updateMCPStatus('inactive');
    
    addTerminalLine('⏰ Session expired - please authenticate again', 'warning');
    
    // Focus on key input
    const keyInput = document.getElementById('privateKey');
    if (keyInput) {
        keyInput.focus();
        keyInput.placeholder = 'Session expired - paste private key to re-authenticate...';
    }
}

/**
 * Check and restore session on page load
 */
function checkSessionOnLoad() {
    const storedToken = localStorage.getItem('mcp_auth_token');
    const storedSessionId = localStorage.getItem('mcp_session_id');
    const storedExpiry = localStorage.getItem('mcp_session_expiry');
    
    if (storedToken && storedSessionId) {
        // Check if session is still valid
        if (storedExpiry && Date.now() < parseInt(storedExpiry)) {
            // Restore session
            window.authenticated = true;
            window.sessionToken = storedToken;
            window.sessionId = storedSessionId;
            window.sessionExpiry = parseInt(storedExpiry);
            window.mcpClient = new MCPClient(storedToken);
            
            // Update UI
            updateAuthUI(true);
            updateMCPStatus('active');
            
            const remainingMinutes = Math.floor((window.sessionExpiry - Date.now()) / 60000);
            addTerminalLine(`✅ Session restored (${remainingMinutes} minutes remaining)`, 'success');
            
            // Auto-refresh agents
            setTimeout(() => refreshAgents(), 500);
            
            // Set up session expiry check
            const timeUntilExpiry = window.sessionExpiry - Date.now();
            setTimeout(() => handleSessionExpiry(), timeUntilExpiry);
            
        } else {
            // Session expired
            handleSessionExpiry();
        }
    }
}

/**
 * Logout function
 */
function logout() {
    if (!window.authenticated) {
        addTerminalLine('Not currently authenticated', 'info');
        return;
    }
    
    // Clear session
    handleSessionExpiry();
    addTerminalLine('✅ Logged out successfully', 'success');
}

// Export functions for global use
window.MCPClient = MCPClient;
window.authenticate = authenticate;
window.handleSessionExpiry = handleSessionExpiry;
window.checkSessionOnLoad = checkSessionOnLoad;
window.logout = logout;