/**
 * MCP Client - Simplified
 */

class MCPClient {
    constructor(sessionToken) {
        this.sessionToken = sessionToken;
        this.baseUrl = '/mcp';
    }

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
    }

    async listTools() {
        const request = {
            jsonrpc: "2.0",
            id: Date.now(),
            method: "tools/list",
            params: {}
        };

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
    }
}

// Global variables
window.authenticated = false;
window.mcpClient = null;

// Global authenticate function - MUST be accessible from HTML onclick
function authenticate() {
    const keyInput = document.getElementById('privateKey');
    const authBtn = document.getElementById('authBtn');

    const privateKey = keyInput.value.trim();

    if (!privateKey) {
        if (typeof addTerminalLine !== 'undefined') {
            addTerminalLine('❌ Please paste your RSA private key', 'error');
        }
        return;
    }

    authBtn.disabled = true;
    authBtn.textContent = 'Authenticating...';

    // Make async call
    authenticateAsync(privateKey, keyInput, authBtn);
}

async function authenticateAsync(privateKey, keyInput, authBtn) {
    try {
        if (typeof addTerminalLine !== 'undefined') {
            addTerminalLine('🔐 Authenticating...', 'info');
        }

        const response = await fetch('/api/orchestrator/authenticate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ private_key: privateKey })
        });

        const data = await response.json();

        if (response.ok && data.session_token) {
            window.authenticated = true;
            window.sessionToken = data.session_token;
            window.mcpClient = new MCPClient(data.session_token);

            keyInput.value = '';

            if (typeof updateAuthUI !== 'undefined') {
                updateAuthUI(true);
            }
            if (typeof addTerminalLine !== 'undefined') {
                addTerminalLine('✅ Authentication successful!', 'success');
            }

            // Load available tools
            if (typeof loadMCPTools !== 'undefined') {
                await loadMCPTools();
            }

            // Refresh agents
            if (typeof refreshAgents !== 'undefined') {
                await refreshAgents();
            }

        } else {
            throw new Error(data.error || 'Authentication failed');
        }

    } catch (error) {
        console.error('Authentication error:', error);
        if (typeof addTerminalLine !== 'undefined') {
            addTerminalLine(`❌ Authentication failed: ${error.message}`, 'error');
        }
        window.authenticated = false;
        window.mcpClient = null;
        if (typeof updateAuthUI !== 'undefined') {
            updateAuthUI(false);
        }
    } finally {
        authBtn.disabled = false;
        authBtn.textContent = window.authenticated ? 'Re-authenticate' : 'Authenticate';
    }
}

// Make authenticate globally available
window.authenticate = authenticate;
