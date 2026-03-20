/**
 * SMS Session Manager
 * 
 * Manages per-sender session state including:
 * - Current routing mode (EX_MASHBAK or EX_BUCHERIM)
 * - Last activity timestamp for timeout tracking
 * - Session expiry logic (Bucherim mode expires after 30 minutes of inactivity)
 */

const MODES = {
    MASHBAK: "MASHBAK",
    BUCHERIM: "BUCHERIM",
};

const DEFAULT_MODE = MODES.MASHBAK;
const BUCHERIM_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Per-sender session state:
 * {
 *   normalizedSender: {
 *     mode: string (MASHBAK or BUCHERIM),
 *     lastActivityTime: number (ms since epoch),
 *     modeSetTime: number (ms since epoch, when mode was last changed)
 *   }
 * }
 */
const sessions = {};

/**
 * Normalize a phone number to 10 digits (last 10 digits).
 * Must match the normalization in access-control-config.js and sms-server.js.
 */
function normalizePhoneNumber(value, maxDigits = 10) {
    const cleaned = String(value || "").replace(/\D/g, "");
    if (cleaned.length > maxDigits) {
        return cleaned.slice(-maxDigits);
    }
    return cleaned;
}

/**
 * Get or initialize session for a sender.
 * Always defaults to MASHBAK mode on first access.
 */
function getSession(normalizedSender) {
    if (!sessions[normalizedSender]) {
        const now = Date.now();
        sessions[normalizedSender] = {
            mode: DEFAULT_MODE,
            lastActivityTime: now,
            modeSetTime: now,
        };
    }
    return sessions[normalizedSender];
}

/**
 * Get current routing mode for a sender.
 * Checks for timeout: if in BUCHERIM mode and timed out, falls back to MASHBAK.
 * Updates lastActivityTime on every call.
 * 
 * @returns {string} One of: MASHBAK or BUCHERIM
 */
function getCurrentMode(normalizedSender) {
    const session = getSession(normalizedSender);
    const now = Date.now();
    
    // Check timeout for Bucherim mode BEFORE updating activity time
    if (session.mode === MODES.BUCHERIM) {
        const timeSinceLastActivity = now - session.lastActivityTime;
        if (timeSinceLastActivity > BUCHERIM_TIMEOUT_MS) {
            // Timeout expired, fall back to Mashbak
            session.mode = MODES.MASHBAK;
            session.lastActivityTime = now;
            return MODES.MASHBAK;
        }
    }
    
    // Update last activity (if not timed out)
    session.lastActivityTime = now;
    
    return session.mode;
}

/**
 * Check if a sender's Bucherim session has timed out.
 * Does NOT update lastActivityTime.
 * Useful for logging decisions without side effects.
 * 
 * @returns {boolean} true if in Bucherim mode and timed out
 */
function isBucherimSessionTimedOut(normalizedSender) {
    const session = getSession(normalizedSender);
    if (session.mode !== MODES.BUCHERIM) {
        return false;
    }
    
    const now = Date.now();
    const timeSinceLastActivity = now - session.lastActivityTime;
    return timeSinceLastActivity > BUCHERIM_TIMEOUT_MS;
}

/**
 * Set mode for a sender.
 * Updates both mode and timestamps.
 * 
 * @param {string} normalizedSender
 * @param {string} newMode - MASHBAK or BUCHERIM
 * @returns {{previousMode: string, newMode: string, timestamp: number}}
 */
function setMode(normalizedSender, newMode) {
    if (newMode !== MODES.MASHBAK && newMode !== MODES.BUCHERIM) {
        throw new Error(`Invalid mode: ${newMode}`);
    }
    
    const session = getSession(normalizedSender);
    const previousMode = session.mode;
    const now = Date.now();
    
    session.mode = newMode;
    session.modeSetTime = now;
    session.lastActivityTime = now;
    
    return {
        previousMode,
        newMode,
        timestamp: now,
        durationMs: now - session.modeSetTime, // Always 0 on first set, shows how long previous mode was active
    };
}

/**
 * Get session info for debugging/logging.
 * Does NOT update activity time.
 * 
 * @returns {{mode: string, lastActivityTime: number, modeSetTime: number, isTimedOut: boolean}}
 */
function getSessionInfo(normalizedSender) {
    const session = getSession(normalizedSender);
    return {
        mode: session.mode,
        lastActivityTime: session.lastActivityTime,
        modeSetTime: session.modeSetTime,
        isTimedOut: isBucherimSessionTimedOut(normalizedSender),
    };
}

/**
 * Reset (clear) session for a sender.
 * Used for testing or manual session invalidation.
 */
function resetSession(normalizedSender) {
    delete sessions[normalizedSender];
}

/**
 * Clear all sessions.
 * Used for testing.
 */
function clearAllSessions() {
    for (const key in sessions) {
        delete sessions[key];
    }
}

module.exports = {
    MODES,
    DEFAULT_MODE,
    BUCHERIM_TIMEOUT_MS,
    normalizePhoneNumber,
    getSession,
    getCurrentMode,
    isBucherimSessionTimedOut,
    setMode,
    getSessionInfo,
    resetSession,
    clearAllSessions,
};
