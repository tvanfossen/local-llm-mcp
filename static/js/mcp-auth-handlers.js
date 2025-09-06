/**
 * MCP Authentication Error Handlers
 * Handles authentication errors and retry logic for MCP operations
 */

/**
 * Handle HTTP errors from MCP calls
 * @param {Response} response - Fetch response object
 * @param {string} toolName - Name of the tool that failed
 */
async function handleHTTPError(response, toolName) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

    try {
        if (response.status === 401 || response.status === 403) {
            // Authentication/authorization error
            const errorBody = await response.json();
            errorMessage = errorBody.error || errorBody.message || 'Authentication failed';

            if (response.status === 401) {
                addTerminalLine('🔐 Authentication expired - please re-authenticate', 'warning');
                handleSessionExpiry();
            }

            addTerminalLine(`❌ Auth Error (${toolName}): ${errorMessage}`, 'error');
        } else if (response.status >= 500) {
            // Server error
            addTerminalLine(`🔥 Server Error (${toolName}): ${errorMessage}`, 'error');
        } else {
            // Client error
            addTerminalLine(`❌ Request Error (${toolName}): ${errorMessage}`, 'error');
        }
    } catch (parseError) {
        addTerminalLine(`❌ HTTP Error (${toolName}): ${errorMessage}`, 'error');
    }

    throw new Error(errorMessage);
}

/**
 * Handle MCP-specific errors from JSON-RPC responses
 * @param {object} error - MCP error object
 * @param {string} toolName - Name of the tool that failed
 */
async function handleMCPError(error, toolName) {
    const errorMessage = `MCP Error [${error.code}]: ${error.message}`;

    // Handle authentication-specific MCP errors
    if (error.code === -32001 || error.message.includes('authentication') || error.message.includes('unauthorized')) {
        addTerminalLine('🔐 MCP authentication failed - session may be expired', 'warning');

        // Check if session has expired
        if (sessionExpiry && Date.now() >= (sessionExpiry - 30000)) { // 30s grace period
            handleSessionExpiry();
        }
    } else if (error.code === -32002 || error.message.includes('permission')) {
        addTerminalLine(`🚫 Permission Error (${toolName}): ${error.message}`, 'error');
    } else if (error.code === -32603) {
        addTerminalLine(`⚙️ Internal Error (${toolName}): ${error.message}`, 'error');
    } else {
        addTerminalLine(`❌ MCP Error (${toolName}): ${error.message}`, 'error');
    }

    throw new Error(errorMessage);
}

/**
 * Handle general errors from MCP calls
 * @param {Error} error - Error object
 * @param {string} toolName - Name of the tool that failed
 */
async function handleMCPCallError(error, toolName) {
    if (error.code === 'AUTH_REQUIRED') {
        addTerminalLine('🔒 Authentication required - please authenticate first', 'warning');

        // Focus authentication input
        const keyInput = document.getElementById('privateKey');
        if (keyInput) {
            keyInput.focus();
            keyInput.placeholder = 'Authentication required - paste private key here...';
        }
    } else if (error.code === 'SESSION_EXPIRED') {
        addTerminalLine('⏰ Session expired - please re-authenticate', 'warning');
    } else if (error.name === 'NetworkError' || error.message.includes('fetch')) {
        addTerminalLine(`🌐 Network Error (${toolName}): Connection failed`, 'error');
    } else if (!error.message.includes('MCP Error') && !error.message.includes('HTTP')) {
        // Only log if not already handled by specific error handlers
        addTerminalLine(`❌ Unexpected Error (${toolName}): ${error.message}`, 'error');
    }
}

/**
 * Check if an error warrants authentication retry
 * @param {Error} error - Error object
 * @returns {boolean} - Whether to retry with authentication
 */
function shouldRetryAuthentication(error) {
    return error.code === 'AUTH_REQUIRED' ||
           error.code === 'SESSION_EXPIRED' ||
           error.message.includes('authentication') ||
           error.message.includes('unauthorized') ||
           error.message.includes('401');
}
