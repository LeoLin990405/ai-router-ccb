/**
 * CCB Gateway Dashboard - Utility Functions
 * Extracted from index.html for modular maintenance
 */

// ==================== Formatting Functions ====================

/**
 * Format percentage value
 * @param {number} value - Value between 0 and 1
 * @returns {string} Formatted percentage string
 */
function formatPercent(value) {
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format latency in milliseconds
 * @param {number} ms - Latency in milliseconds
 * @returns {string} Human-readable latency
 */
function formatLatency(ms) {
    if (!ms) return '0ms';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * Format duration from seconds
 * @param {number} seconds - Duration in seconds
 * @returns {string} Human-readable duration
 */
function formatDuration(seconds) {
    if (!seconds) return '0s';
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
}

/**
 * Format timestamp to time string
 * @param {string|number} ts - ISO timestamp or Unix timestamp
 * @returns {string} Formatted time
 */
function formatTime(ts) {
    if (!ts) return '-';
    try {
        const date = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
        return '-';
    }
}

/**
 * Format feature name for display
 * @param {string} name - Feature name with underscores
 * @returns {string} Human-readable feature name
 */
function formatFeatureName(name) {
    return name.replace(/_/g, ' ').replace(/enabled/i, '').trim();
}

/**
 * Format cost value
 * @param {number} cost - Cost in USD
 * @returns {string} Formatted cost
 */
function formatCost(cost) {
    if (!cost || cost < 0.01) return '0.00';
    return cost.toFixed(2);
}

/**
 * Format large numbers with K/M suffixes
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

/**
 * Format bytes to human-readable string
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size
 */
function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
}

/**
 * Format relative time from timestamp
 * @param {number} timestamp - Unix timestamp in seconds
 * @param {string} lang - Language code ('en' or 'zh')
 * @returns {string} Human-readable relative time
 */
function formatRelativeTime(timestamp, lang = 'en') {
    if (!timestamp) return '';
    const now = Date.now() / 1000;
    const diff = now - timestamp;
    if (diff < 60) return lang === 'zh' ? '刚刚' : 'just now';
    if (diff < 3600) return lang === 'zh' ? `${Math.floor(diff / 60)} 分钟前` : `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return lang === 'zh' ? `${Math.floor(diff / 3600)} 小时前` : `${Math.floor(diff / 3600)}h ago`;
    return lang === 'zh' ? `${Math.floor(diff / 86400)} 天前` : `${Math.floor(diff / 86400)}d ago`;
}

// ==================== Style Helpers ====================

/**
 * Get status text color class
 * @param {string} status - Provider status
 * @returns {string} Tailwind color class
 */
function getStatusClass(status) {
    return {
        healthy: 'text-emerald-400', available: 'text-emerald-400',
        degraded: 'text-amber-400', unavailable: 'text-rose-400', unknown: 'text-gray-400'
    }[status] || 'text-gray-400';
}

/**
 * Get status badge class
 * @param {string} status - Provider status
 * @returns {string} Badge style classes
 */
function getStatusBadgeClass(status) {
    return {
        healthy: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        available: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        degraded: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        unavailable: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
        unknown: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
}

/**
 * Get request status badge class
 * @param {string} status - Request status
 * @returns {string} Badge class
 */
function getRequestStatusClass(status) {
    return {
        queued: 'badge-info', processing: 'badge-warning',
        completed: 'badge-success', failed: 'badge-error', cancelled: 'badge-error'
    }[status] || 'badge-info';
}

/**
 * Get status dot class for inline indicators
 * @param {string} status - Status string
 * @returns {string} Color class
 */
function getStatusDotClass(status) {
    return {
        queued: 'bg-indigo-400', processing: 'bg-amber-400',
        completed: 'bg-emerald-400', failed: 'bg-rose-400', cancelled: 'bg-gray-400'
    }[status] || 'bg-gray-400';
}

/**
 * Get log entry class based on type
 * @param {string} type - Log type
 * @returns {string} Color class
 */
function getLogClass(type) {
    return {
        success: 'text-emerald-400', error: 'text-rose-400',
        warning: 'text-amber-400', info: 'text-cyan-400'
    }[type] || 'text-gray-400';
}

/**
 * Get agent icon class
 * @param {string} agent - Agent name
 * @returns {string} FontAwesome icon class
 */
function getAgentIcon(agent) {
    if (!agent) return 'fa-robot';
    const lower = agent.toLowerCase();
    if (lower.includes('sisyphus')) return 'fa-mountain';
    if (lower.includes('oracle')) return 'fa-eye';
    if (lower.includes('librarian')) return 'fa-book';
    if (lower.includes('explorer')) return 'fa-compass';
    if (lower.includes('frontend')) return 'fa-paint-brush';
    if (lower.includes('reviewer')) return 'fa-search';
    return 'fa-robot';
}

/**
 * Get score color class
 * @param {number} score - Score 0-100
 * @returns {string} Color class
 */
function getScoreColor(score) {
    if (score >= 80) return 'bg-emerald-500';
    if (score >= 60) return 'bg-amber-500';
    return 'bg-rose-500';
}

// ==================== Provider Tier Helpers ====================

const PROVIDER_TIERS = {
    fast: ['kimi', 'qwen'],
    medium: ['iflow', 'opencode'],
    slow: ['codex', 'gemini', 'claude']
};

/**
 * Get provider speed tier
 * @param {string} name - Provider name
 * @returns {string} Tier name
 */
function getProviderTier(name) {
    const lower = name.toLowerCase();
    if (PROVIDER_TIERS.fast.includes(lower)) return 'fast';
    if (PROVIDER_TIERS.medium.includes(lower)) return 'medium';
    if (PROVIDER_TIERS.slow.includes(lower)) return 'slow';
    return 'unknown';
}

/**
 * Get provider tier icon
 * @param {string} name - Provider name
 * @returns {string} Emoji icon
 */
function getProviderTierIcon(name) {
    const tier = getProviderTier(name);
    return { fast: '🚀', medium: '⚡', slow: '🐢', unknown: '❓' }[tier];
}

/**
 * Get provider tier label
 * @param {string} name - Provider name
 * @returns {string} Tier label
 */
function getProviderTierLabel(name) {
    const tier = getProviderTier(name);
    return { fast: 'Fast', medium: 'Medium', slow: 'Slow', unknown: '?' }[tier];
}

/**
 * Get provider tier style class
 * @param {string} name - Provider name
 * @returns {string} Style classes
 */
function getProviderTierClass(name) {
    const tier = getProviderTier(name);
    return {
        fast: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        slow: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
        unknown: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }[tier];
}

// ==================== Token Pricing ====================

const TOKEN_PRICING = {
    claude: { input: 0.003, output: 0.015 },
    gemini: { input: 0.00025, output: 0.0005 },
    openai: { input: 0.005, output: 0.015 },
    default: { input: 0.001, output: 0.002 }
};

/**
 * Calculate estimated cost for tokens
 * @param {string} provider - Provider name
 * @param {number} inputTokens - Input token count
 * @param {number} outputTokens - Output token count
 * @returns {number} Estimated cost in USD
 */
function calculateTokenCost(provider, inputTokens, outputTokens) {
    const pricing = TOKEN_PRICING[provider.toLowerCase()] || TOKEN_PRICING.default;
    const inputCost = (inputTokens / 1000) * pricing.input;
    const outputCost = (outputTokens / 1000) * pricing.output;
    return inputCost + outputCost;
}

// Export for ES modules (if used)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatPercent, formatLatency, formatDuration, formatTime, formatFeatureName,
        formatCost, formatNumber, formatBytes, formatRelativeTime,
        getStatusClass, getStatusBadgeClass, getRequestStatusClass, getStatusDotClass,
        getLogClass, getAgentIcon, getScoreColor,
        getProviderTier, getProviderTierIcon, getProviderTierLabel, getProviderTierClass,
        calculateTokenCost, TOKEN_PRICING, PROVIDER_TIERS
    };
}
