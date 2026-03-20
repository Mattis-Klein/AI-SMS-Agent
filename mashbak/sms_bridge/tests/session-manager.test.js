const test = require("node:test");
const assert = require("node:assert/strict");

const sessionManager = require("../session-manager");

test("normalizePhoneNumber works correctly", () => {
    assert.equal(sessionManager.normalizePhoneNumber("+1 (848) 329-1230"), "8483291230");
    assert.equal(sessionManager.normalizePhoneNumber("18483291230"), "8483291230");
    assert.equal(sessionManager.normalizePhoneNumber("8483291230"), "8483291230");
    assert.equal(sessionManager.normalizePhoneNumber("(848) 329-1230"), "8483291230");
});

test("authorized sender defaults to MASHBAK mode", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    const mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.MASHBAK);
});

test("mode can be switched to BUCHERIM", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Start in Mashbak
    let mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.MASHBAK);
    
    // Switch to Bucherim
    const result = sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    assert.equal(result.previousMode, sessionManager.MODES.MASHBAK);
    assert.equal(result.newMode, sessionManager.MODES.BUCHERIM);
    
    // Verify mode is now Bucherim
    mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.BUCHERIM);
});

test("mode can be switched back to MASHBAK from BUCHERIM", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Switch to Bucherim
    sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    let mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.BUCHERIM);
    
    // Switch back to Mashbak
    sessionManager.setMode(normalizedSender, sessionManager.MODES.MASHBAK);
    mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.MASHBAK);
});

test("Bucherim mode times out after 30 minutes of inactivity", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Switch to Bucherim
    sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    let mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.BUCHERIM);
    
    // Simulate 30 minutes of inactivity by manipulating session state directly
    const session = sessionManager.getSession(normalizedSender);
    const thirtyMinutesAgo = Date.now() - sessionManager.BUCHERIM_TIMEOUT_MS - 1000;
    session.lastActivityTime = thirtyMinutesAgo;
    
    // Check if timed out
    const isTimedOut = sessionManager.isBucherimSessionTimedOut(normalizedSender);
    assert.equal(isTimedOut, true);
    
    // Check that getCurrentMode falls back to Mashbak due to timeout
    mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.MASHBAK);
});

test("Bucherim mode does NOT time out within 30 minutes", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Switch to Bucherim
    sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    let mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.BUCHERIM);
    
    // Simulate 29 minutes of inactivity
    const session = sessionManager.getSession(normalizedSender);
    const twentyNineMinutesAgo = Date.now() - (sessionManager.BUCHERIM_TIMEOUT_MS - 60000);
    session.lastActivityTime = twentyNineMinutesAgo;
    
    // Check if timed out (should be false)
    const isTimedOut = sessionManager.isBucherimSessionTimedOut(normalizedSender);
    assert.equal(isTimedOut, false);
    
    // Mode should still be Bucherim
    mode = sessionManager.getCurrentMode(normalizedSender);
    assert.equal(mode, sessionManager.MODES.BUCHERIM);
});

test("lastActivityTime is updated on getCurrentMode call", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Get initial session
    sessionManager.getCurrentMode(normalizedSender);
    const session1 = sessionManager.getSession(normalizedSender);
    const initialTime = session1.lastActivityTime;
    
    // Manually set it back slightly to ensure we can detect an update
    session1.lastActivityTime = initialTime - 100;
    
    // Call again
    sessionManager.getCurrentMode(normalizedSender);
    const session2 = sessionManager.getSession(normalizedSender);
    const updatedTime = session2.lastActivityTime;
    
    assert(updatedTime > initialTime - 100, "lastActivityTime should be updated");
});

test("getCurrentMode does not update activity time via isBucherimSessionTimedOut", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Switch to Bucherim
    sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    const session = sessionManager.getSession(normalizedSender);
    const initialTime = session.lastActivityTime;
    
    // Simulate 25 minutes of inactivity
    session.lastActivityTime = Date.now() - (sessionManager.BUCHERIM_TIMEOUT_MS - 300000);
    
    // Check timeout without updating activity time
    const isTimedOut = sessionManager.isBucherimSessionTimedOut(normalizedSender);
    assert.equal(isTimedOut, false);
    
    // Activity time should NOT have changed
    assert.equal(session.lastActivityTime, Date.now() - (sessionManager.BUCHERIM_TIMEOUT_MS - 300000));
});

test("getSessionInfo does not update activity time", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Get initial info
    sessionManager.getCurrentMode(normalizedSender);
    const session = sessionManager.getSession(normalizedSender);
    const initialTime = session.lastActivityTime;
    
    // Manually set last activity to 15 minutes ago
    session.lastActivityTime = Date.now() - 900000;
    
    // Get session info (should not update)
    const info = sessionManager.getSessionInfo(normalizedSender);
    
    // Activity time should NOT have changed
    assert.equal(session.lastActivityTime, Date.now() - 900000);
    assert.equal(info.lastActivityTime, Date.now() - 900000);
});

test("separate senders have separate sessions", () => {
    sessionManager.clearAllSessions();
    const sender1 = "8483291230";
    const sender2 = "9297546860";
    
    // Sender 1: switch to Bucherim
    sessionManager.setMode(sender1, sessionManager.MODES.BUCHERIM);
    assert.equal(sessionManager.getCurrentMode(sender1), sessionManager.MODES.BUCHERIM);
    
    // Sender 2: should default to Mashbak
    assert.equal(sessionManager.getCurrentMode(sender2), sessionManager.MODES.MASHBAK);
    
    // Verify sender 1 is still Bucherim
    assert.equal(sessionManager.getCurrentMode(sender1), sessionManager.MODES.BUCHERIM);
});

test("resetSession clears a specific sender's session", () => {
    sessionManager.clearAllSessions();
    const normalizedSender = "8483291230";
    
    // Switch to Bucherim
    sessionManager.setMode(normalizedSender, sessionManager.MODES.BUCHERIM);
    assert.equal(sessionManager.getCurrentMode(normalizedSender), sessionManager.MODES.BUCHERIM);
    
    // Reset session
    sessionManager.resetSession(normalizedSender);
    
    // Should default to Mashbak again
    assert.equal(sessionManager.getCurrentMode(normalizedSender), sessionManager.MODES.MASHBAK);
});

test("clearAllSessions clears all sessions", () => {
    const sender1 = "8483291230";
    const sender2 = "9297546860";
    
    // Set both to Bucherim
    sessionManager.setMode(sender1, sessionManager.MODES.BUCHERIM);
    sessionManager.setMode(sender2, sessionManager.MODES.BUCHERIM);
    
    // Clear all
    sessionManager.clearAllSessions();
    
    // Both should default to Mashbak
    assert.equal(sessionManager.getCurrentMode(sender1), sessionManager.MODES.MASHBAK);
    assert.equal(sessionManager.getCurrentMode(sender2), sessionManager.MODES.MASHBAK);
});
