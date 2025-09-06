/**
 * Orchestrator Main Application Logic
 * Handles authentication, WebSocket, and application initialization
 */

// Global state
let authenticated = false;
let sessionToken = null;
let currentSelectedAgent = null;
let ws = null;
let sessionExpiry = null;

// Initialize on load
window.onload = () => {
    initializeApplication();
};

function initializeApplication() {
    initWebSocket();
    updateMCPStatus(true);
    updateToolInputs();
    updateAuthenticationUI();
    addTerminalLine('🔗 MCP JSON-RPC client initialized', 'info');
    addTerminalLine('📡 All agent operations now use MCP protocol', 'info');
    addTerminalLine('🔐 Authentication integration enabled', 'info');
}

function updateMCPStatus(ready) {
    document.getElementById('mcpIndicator').style.background = ready ? '#50fa7b' : '#ff5555';
    document.getElementById('mcpStatus').textContent = ready ? 'MCP Ready' : 'MCP Error';
}

function updateAuthenticationUI() {
    const panels = ['agentsPanel', 'toolsPanel', 'actionsPanel'];
    const authIndicators = ['authIndicator', 'authIndicator2'];
    const authTexts = ['authStatusText', 'authStatus2'];

    panels.forEach(panelId => {
        const panel = document.getElementById(panelId);
        if (authenticated) {
            panel.classList.remove('require-auth');
        } else {
            panel.classList.add('require-auth');
        }
    });

    authIndicators.forEach(indicatorId => {
        const indicator = document.getElementById(indicatorId);
        indicator.className = 'status-indicator';
        if (authenticated) {
            indicator.classList.add('authenticated');
        } else {
            indicator.classList.remove('authenticated');
        }
    });

    const sessionInfo = document.getElementById('authSessionInfo');
    if (authenticated && sessionExpiry) {
        const timeLeft = Math.max(0, Math.floor((sessionExpiry - Date.now()) / 1000));
        sessionInfo.textContent = `Session expires in ${timeLeft}s`;
    } else {
        sessionInfo.textContent = 'MCP operations require authentication';
    }
}

async function authenticate() {
    const keyInput = document.getElementById('privateKey');
    const authBtn = document.getElementById('authBtn');

    if (!keyInput.value) {
        addTerminalLine('No private key provided', 'error');
        keyInput.classList.add('error');
        return;
    }

    keyInput.classList.remove('error');
    authBtn.disabled = true;
    authBtn.textContent = 'Authenticating...';

    try {
        const response = await fetch('/api/orchestrator/authenticate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({private_key: keyInput.value})
        });

        if (response.ok) {
            const data = await response.json();
            authenticated = true;
            sessionToken = data.session_token;
            sessionExpiry = Date.now() + (data.expires_in * 1000);

            document.getElementById('authStatusText').textContent = 'Authenticated';
            document.getElementById('authStatus2').textContent = 'Authenticated';

            addTerminalLine('🔐 Authentication successful - MCP tools enabled', 'success');
            addTerminalLine(`⏰ Session expires in ${data.expires_in} seconds`, 'info');

            keyInput.value = '';
            updateAuthenticationUI();

            // Auto-refresh agents after authentication
            refreshAgents();

            // Start session monitoring
            startSessionMonitoring();
        } else {
            const error = await response.json();
            addTerminalLine(`❌ Authentication failed: ${error.error || error.message}`, 'error');
            keyInput.classList.add('error');
        }
    } catch (error) {
        addTerminalLine(`🚫 Authentication error: ${error}`, 'error');
        keyInput.classList.add('error');
    }

    authBtn.disabled = false;
    authBtn.textContent = 'Authenticate';
}

function startSessionMonitoring() {
    // Update session info every 10 seconds
    setInterval(() => {
        if (authenticated && sessionExpiry) {
            const timeLeft = Math.max(0, Math.floor((sessionExpiry - Date.now()) / 1000));
            const sessionInfo = document.getElementById('authSessionInfo');
            sessionInfo.textContent = `Session expires in ${timeLeft}s`;

            // Warn when session is about to expire
            if (timeLeft < 300 && timeLeft > 0) { // 5 minutes
                const indicator = document.getElementById('authIndicator');
                indicator.classList.add('expired');
                if (timeLeft === 299) {
                    addTerminalLine('⚠️ Session expires in 5 minutes - consider re-authenticating', 'warning');
                }
            }

            // Handle session expiry
            if (timeLeft <= 0) {
                handleSessionExpiry();
            }
        }
    }, 10000);
}

function handleSessionExpiry() {
    authenticated = false;
    sessionToken = null;
    sessionExpiry = null;

    document.getElementById('authStatusText').textContent = 'Session Expired';
    document.getElementById('authStatus2').textContent = 'Session Expired';

    updateAuthenticationUI();
    addTerminalLine('🔐 Session expired - please re-authenticate', 'warning');

    const keyInput = document.getElementById('privateKey');
    keyInput.placeholder = 'Session expired - paste private key to re-authenticate...';
    keyInput.focus();
}

function initWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        updateWSStatus('Connected', true);
        addTerminalLine('WebSocket connected', 'success');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    ws.onclose = () => {
        updateWSStatus('Disconnected', false);
        addTerminalLine('WebSocket disconnected', 'error');
        setTimeout(initWebSocket, 3000);
    };

    ws.onerror = (error) => {
        addTerminalLine(`WebSocket error: ${error}`, 'error');
    };
}

function updateWSStatus(text, connected) {
    document.getElementById('wsStatus').textContent = text;
    document.getElementById('wsIndicator').style.background = connected ? '#50fa7b' : '#ff5555';
}

function handleWSMessage(data) {
    if (data.message) {
        addTerminalLine(data.message, data.level || 'info');
    }
}

function addTerminalLine(text, type = '') {
    const terminal = document.getElementById('terminal');
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;

    // Limit terminal lines to prevent memory issues
    while (terminal.children.length > 100) {
        terminal.removeChild(terminal.firstChild);
    }
}
