/**
 * Agent Operation Helpers
 * Utility functions and display helpers for agent operations
 */

/**
 * Format agent ID for display
 * @param {string} id - Full agent ID
 * @returns {string} Formatted ID
 */
function formatAgentId(id) {
    if (!id) return 'unknown';
    if (id.length <= 12) return id;
    return `${id.substring(0, 8)}...`;
}

/**
 * Format success rate for display
 * @param {number} rate - Success rate (0-1)
 * @returns {string} Formatted percentage
 */
function formatSuccessRate(rate) {
    if (rate === null || rate === undefined || isNaN(rate)) {
        return 'N/A';
    }
    return `${Math.round(rate * 100)}%`;
}

/**
 * Format file count for display
 * @param {number} count - Number of files
 * @returns {string} Formatted string
 */
function formatFileCount(count) {
    if (!count || count === 0) return 'No files';
    if (count === 1) return '1 file';
    return `${count} files`;
}

/**
 * Format interaction count for display
 * @param {number} count - Number of interactions
 * @returns {string} Formatted string
 */
function formatInteractionCount(count) {
    if (!count || count === 0) return 'No interactions';
    if (count === 1) return '1 interaction';
    return `${count} interactions`;
}

/**
 * Create agent card HTML
 * @param {object} agent - Agent object
 * @returns {string} HTML string
 */
function createAgentCardHTML(agent) {
    const fileInfo = agent.managed_file && agent.managed_file !== 'unknown' 
        ? `📄 ${agent.managed_file}`
        : `📁 ${formatFileCount(agent.managed_files_count)}`;
    
    return `
        <div class="agent-name">${agent.name || formatAgentId(agent.id)}</div>
        <div class="agent-file">${fileInfo}</div>
        <div class="agent-stats">
            <span>📊 ${formatInteractionCount(agent.total_interactions)}</span>
            <span>✅ ${formatSuccessRate(agent.success_rate)}</span>
        </div>
        ${agent.description ? `<div class="agent-desc">${agent.description}</div>` : ''}
    `;
}

/**
 * Update selected agent display in UI
 * @param {object} agent - Selected agent object
 */
function updateSelectedAgentDisplay(agent) {
    const elements = {
        selectedName: document.getElementById('selectedAgentName'),
        selectedId: document.getElementById('selectedAgentId'),
        selectedFile: document.getElementById('selectedAgentFile'),
        selectedStats: document.getElementById('selectedAgentStats')
    };
    
    if (elements.selectedName) {
        const displayName = agent.name || formatAgentId(agent.id);
        const fileInfo = agent.managed_file && agent.managed_file !== 'unknown'
            ? agent.managed_file
            : formatFileCount(agent.managed_files_count);
        
        elements.selectedName.textContent = `${displayName} (${fileInfo})`;
        elements.selectedName.style.color = '#00d4ff';
    }
    
    if (elements.selectedId) {
        elements.selectedId.textContent = formatAgentId(agent.id);
    }
    
    if (elements.selectedFile) {
        elements.selectedFile.textContent = agent.managed_file || 'Multiple files';
    }
    
    if (elements.selectedStats) {
        elements.selectedStats.innerHTML = `
            <span>📊 ${formatInteractionCount(agent.total_interactions)}</span>
            <span>✅ ${formatSuccessRate(agent.success_rate)}</span>
        `;
    }
}

/**
 * Filter agents by search term
 * @param {array} agents - Array of agents
 * @param {string} searchTerm - Search term
 * @returns {array} Filtered agents
 */
function filterAgents(agents, searchTerm) {
    if (!searchTerm) return agents;
    
    const term = searchTerm.toLowerCase();
    return agents.filter(agent => {
        return (
            (agent.name && agent.name.toLowerCase().includes(term)) ||
            (agent.id && agent.id.toLowerCase().includes(term)) ||
            (agent.description && agent.description.toLowerCase().includes(term)) ||
            (agent.managed_file && agent.managed_file.toLowerCase().includes(term))
        );
    });
}

/**
 * Sort agents by criteria
 * @param {array} agents - Array of agents
 * @param {string} criteria - Sort criteria (name, interactions, success)
 * @returns {array} Sorted agents
 */
function sortAgents(agents, criteria = 'name') {
    const sorted = [...agents];
    
    switch(criteria) {
        case 'name':
            sorted.sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));
            break;
        case 'interactions':
            sorted.sort((a, b) => (b.total_interactions || 0) - (a.total_interactions || 0));
            break;
        case 'success':
            sorted.sort((a, b) => (b.success_rate || 0) - (a.success_rate || 0));
            break;
        case 'files':
            sorted.sort((a, b) => (b.managed_files_count || 0) - (a.managed_files_count || 0));
            break;
        default:
            break;
    }
    
    return sorted;
}

/**
 * Get agent status badge
 * @param {object} agent - Agent object
 * @returns {string} HTML badge
 */
function getAgentStatusBadge(agent) {
    const successRate = agent.success_rate || 0;
    const interactions = agent.total_interactions || 0;
    
    if (interactions === 0) {
        return '<span class="badge badge-new">New</span>';
    } else if (successRate >= 0.9) {
        return '<span class="badge badge-excellent">Excellent</span>';
    } else if (successRate >= 0.7) {
        return '<span class="badge badge-good">Good</span>';
    } else if (successRate >= 0.5) {
        return '<span class="badge badge-fair">Fair</span>';
    } else {
        return '<span class="badge badge-poor">Needs Attention</span>';
    }
}

/**
 * Calculate agent health score
 * @param {object} agent - Agent object
 * @returns {number} Health score (0-100)
 */
function calculateAgentHealth(agent) {
    let score = 100;
    
    // Factor in success rate (40% weight)
    const successWeight = 40;
    const successRate = agent.success_rate || 0;
    score = successWeight * successRate;
    
    // Factor in activity (30% weight)
    const activityWeight = 30;
    const interactions = agent.total_interactions || 0;
    if (interactions === 0) {
        score += 0; // New agent, neutral
    } else if (interactions < 10) {
        score += activityWeight * 0.5;
    } else if (interactions < 50) {
        score += activityWeight * 0.75;
    } else {
        score += activityWeight;
    }
    
    // Factor in file management (30% weight)
    const fileWeight = 30;
    const files = agent.managed_files_count || 0;
    if (files === 0) {
        score += 0;
    } else if (files === 1) {
        score += fileWeight; // Optimal for single responsibility
    } else if (files <= 3) {
        score += fileWeight * 0.8;
    } else {
        score += fileWeight * 0.5; // Too many files
    }
    
    return Math.round(score);
}

/**
 * Get agent recommendations
 * @param {object} agent - Agent object
 * @returns {array} Array of recommendation strings
 */
function getAgentRecommendations(agent) {
    const recommendations = [];
    
    if (agent.total_interactions === 0) {
        recommendations.push('Start using this agent to build interaction history');
    }
    
    if (agent.success_rate < 0.5 && agent.total_interactions > 5) {
        recommendations.push('Review and update agent prompts to improve success rate');
    }
    
    if (agent.managed_files_count > 5) {
        recommendations.push('Consider splitting responsibilities across multiple agents');
    }
    
    if (agent.managed_files_count === 0) {
        recommendations.push('Assign files to this agent for management');
    }
    
    return recommendations;
}

/**
 * Export agent data as JSON
 * @param {object} agent - Agent object
 * @returns {string} JSON string
 */
function exportAgentData(agent) {
    const exportData = {
        id: agent.id,
        name: agent.name,
        description: agent.description,
        managed_files: agent.managed_files || [],
        managed_file: agent.managed_file,
        statistics: {
            total_interactions: agent.total_interactions,
            success_rate: agent.success_rate,
            health_score: calculateAgentHealth(agent)
        },
        exported_at: new Date().toISOString()
    };
    
    return JSON.stringify(exportData, null, 2);
}

/**
 * Validate agent data
 * @param {object} agent - Agent object to validate
 * @returns {object} Validation result
 */
function validateAgentData(agent) {
    const errors = [];
    const warnings = [];
    
    // Required fields
    if (!agent.id) errors.push('Agent ID is required');
    if (!agent.name) warnings.push('Agent name is missing');
    
    // Data integrity
    if (agent.success_rate > 1 || agent.success_rate < 0) {
        errors.push('Success rate must be between 0 and 1');
    }
    
    if (agent.total_interactions < 0) {
        errors.push('Total interactions cannot be negative');
    }
    
    if (agent.managed_files_count < 0) {
        errors.push('File count cannot be negative');
    }
    
    return {
        valid: errors.length === 0,
        errors,
        warnings
    };
}

// Export all helper functions
window.AgentHelpers = {
    formatAgentId,
    formatSuccessRate,
    formatFileCount,
    formatInteractionCount,
    createAgentCardHTML,
    updateSelectedAgentDisplay,
    filterAgents,
    sortAgents,
    getAgentStatusBadge,
    calculateAgentHealth,
    getAgentRecommendations,
    exportAgentData,
    validateAgentData
};