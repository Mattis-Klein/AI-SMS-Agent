const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const express = require("express");
const bodyParser = require("body-parser");
const twilio = require("twilio");
const {
    isAccessRequestCommand,
    loadSenderAccessConfig,
    normalizePhoneNumber,
    resolveSenderAction,
} = require("./access-control-config");
const { redactConfigAssignments, sanitize } = require("./redaction");
const { loadEnvFile } = require("./env-loader");
const sessionManager = require("./session-manager");

// Load master config first (reads from mashbak/.env.master)
const masterEnvPath = path.join(__dirname, "..", ".env.master");
loadEnvFile(masterEnvPath);

const app = express();
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

const BASE_DIR = __dirname;
const AGENT_URL = process.env.AGENT_URL || "http://127.0.0.1:8787";
const AGENT_API_KEY = process.env.AGENT_API_KEY || "";
const PORT = Number(process.env.BRIDGE_PORT || 34567);
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL || "").replace(/\/$/, "");
const BUCHERIM_TWILIO_NUMBER = process.env.BUCHERIM_TWILIO_NUMBER || "+18772683048";
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID || "";
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN || "";
const TWILIO_FROM_NUMBER = process.env.TWILIO_FROM_NUMBER || "";
const LOG_DIR = path.join(BASE_DIR, "..", "data", "logs");
const LOG_FILE = path.join(LOG_DIR, "bridge.log");
const LOG_ARCHIVE_FILE = path.join(LOG_DIR, "bridge.log.1");
const LOG_MAX_BYTES = Number(process.env.BRIDGE_LOG_MAX_BYTES || 1_000_000);
const SENDER_ACCESS = loadSenderAccessConfig(process.env);
const ACCESS_CONFIG_LOADED_AT = new Date().toISOString();

// SMS session mode control commands (only authorized owner can trigger these)
const MODE_COMMAND_BUCHERIM = "MAT@BUCHERIM";
const MODE_COMMAND_MASHBAK = "MAT@MASHBAK";

fs.mkdirSync(LOG_DIR, { recursive: true });

const twilioRestClient = (TWILIO_ACCOUNT_SID && TWILIO_AUTH_TOKEN)
    ? twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    : null;

if (!AGENT_API_KEY) {
    throw new Error("AGENT_API_KEY is required. Set it in mashbak/.env.master or the environment.");
}

if (!PUBLIC_BASE_URL) {
    console.warn("[bridge] PUBLIC_BASE_URL is not set. Twilio signature validation will use request headers.");
}

if (!TWILIO_AUTH_TOKEN) {
    console.warn("[bridge] TWILIO_AUTH_TOKEN is not set. Twilio signature validation is disabled.");
}

if (!TWILIO_ACCOUNT_SID) {
    console.warn("[bridge] TWILIO_ACCOUNT_SID is not set. Owner access-request notifications are disabled.");
}

if (!TWILIO_FROM_NUMBER) {
    console.warn("[bridge] TWILIO_FROM_NUMBER is not set. Inbound To number will be used for owner notifications when available.");
}

function rotateLogIfNeeded() {
    try {
        if (!fs.existsSync(LOG_FILE)) {
            return;
        }

        const stats = fs.statSync(LOG_FILE);
        if (stats.size < LOG_MAX_BYTES) {
            return;
        }

        if (fs.existsSync(LOG_ARCHIVE_FILE)) {
            fs.unlinkSync(LOG_ARCHIVE_FILE);
        }

        fs.renameSync(LOG_FILE, LOG_ARCHIVE_FILE);
    } catch (error) {
        console.warn(`[bridge] failed to rotate logs: ${error.message}`);
    }
}

function logBridgeEvent(event) {
    const record = {
        time: new Date().toISOString(),
        ...sanitize(event)
    };

    rotateLogIfNeeded();
    fs.appendFileSync(LOG_FILE, `${JSON.stringify(record)}\n`, "utf8");
}

function createRequestId() {
    return crypto.randomUUID();
}

function truncateText(value, maxLength = 500) {
    const text = String(value ?? "");
    if (text.length <= maxLength) {
        return text;
    }

    return `${text.slice(0, maxLength)}...`;
}

function toE164Us(value) {
    const digits = normalizePhoneNumber(value, SENDER_ACCESS.normalizationDigits);
    if (digits.length === 10) {
        return `+1${digits}`;
    }
    if (digits.length === 11 && digits.startsWith("1")) {
        return `+${digits}`;
    }
    return String(value || "").trim();
}

async function notifyOwnerAccessRequest({ requestId, normalizedFrom, inboundTo }) {
    const ownerTo = toE164Us(SENDER_ACCESS.ownerNumber);
    const fromNumber = toE164Us(TWILIO_FROM_NUMBER || inboundTo || "");

    if (!twilioRestClient) {
        logBridgeEvent({
            requestId,
            stage: "access_request_notify_skipped",
            reason: "missing_twilio_rest_credentials",
            normalizedFrom,
        });
        return;
    }

    if (!fromNumber) {
        logBridgeEvent({
            requestId,
            stage: "access_request_notify_skipped",
            reason: "missing_from_number",
            normalizedFrom,
        });
        return;
    }

    const body = `Mashbak access request: ${normalizedFrom} sent @mashbak and requested access.`;

    try {
        const message = await twilioRestClient.messages.create({
            to: ownerTo,
            from: fromNumber,
            body,
        });

        logBridgeEvent({
            requestId,
            stage: "access_request_notify_sent",
            normalizedFrom,
            ownerTo,
            messageSid: message.sid || null,
        });
    } catch (error) {
        logBridgeEvent({
            requestId,
            stage: "access_request_notify_failed",
            normalizedFrom,
            ownerTo,
            error: error.message,
        });
    }
}

function getRequestUrlCandidates(req) {
    const candidates = [];

    if (PUBLIC_BASE_URL) {
        candidates.push(`${PUBLIC_BASE_URL}${req.originalUrl}`);
    }

    const forwardedProto = (req.headers["x-forwarded-proto"] || "").split(",")[0].trim();
    const forwardedHost = (req.headers["x-forwarded-host"] || "").split(",")[0].trim();
    const originalHost = (req.headers["x-original-host"] || "").split(",")[0].trim();
    const host = req.get("host");

    const protocolOptions = [
        forwardedProto,
        req.protocol,
        "https",
        "http",
    ].filter(Boolean);

    const hostOptions = [
        forwardedHost,
        originalHost,
        host,
    ].filter(Boolean);

    for (const protocol of protocolOptions) {
        for (const candidateHost of hostOptions) {
            candidates.push(`${protocol}://${candidateHost}${req.originalUrl}`);
        }
    }

    return Array.from(new Set(candidates));
}

function isValidTwilioRequest(req) {
    if (!TWILIO_AUTH_TOKEN) {
        return true;
    }

    const signature = req.get("x-twilio-signature") || "";
    if (!signature) {
        return false;
    }

    const urls = getRequestUrlCandidates(req);
    for (const url of urls) {
        if (twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, req.body || {})) {
            return true;
        }
    }

    return false;
}

function buildTwimlMessage(message) {
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message(message);
    return twiml.toString();
}

function buildTwimlMessageWithMedia(message, media = []) {
    const twiml = new twilio.twiml.MessagingResponse();
    const msg = twiml.message(message);
    for (const mediaItem of media) {
        const url = String(mediaItem && mediaItem.url ? mediaItem.url : "").trim();
        if (url) {
            msg.media(url);
        }
    }
    return twiml.toString();
}

function normalizeToE164(value) {
    const digits = String(value || "").replace(/\D/g, "");
    if (!digits) {
        return "";
    }
    if (digits.length === 10) {
        return `+1${digits}`;
    }
    if (digits.length === 11 && digits.startsWith("1")) {
        return `+${digits}`;
    }
    return `+${digits}`;
}

function extractInboundMedia(body) {
    const count = Number(body.NumMedia || 0);
    if (!Number.isFinite(count) || count <= 0) {
        return [];
    }

    const media = [];
    for (let i = 0; i < count; i += 1) {
        const url = String(body[`MediaUrl${i}`] || "").trim();
        const contentType = String(body[`MediaContentType${i}`] || "").trim();
        if (!url) {
            continue;
        }
        media.push({
            url,
            content_type: contentType || null,
            filename: null,
        });
    }

    return media;
}

async function postJson(endpoint, payload, requestId, sender = null) {
    const safePayload = sanitize(payload);
    logBridgeEvent({
        requestId,
        stage: "agent_request",
        endpoint,
        payload: truncateText(JSON.stringify(safePayload), 1000),
        sender
    });

    const headers = {
        "Content-Type": "application/json",
        "x-api-key": AGENT_API_KEY,
        "x-request-id": requestId
    };

    if (sender) {
        headers["x-sender"] = sender;
        headers["x-source"] = "sms";
    }

    const response = await fetch(`${AGENT_URL}${endpoint}`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
    });

    const text = await response.text();
    try {
        const parsed = JSON.parse(text);
        logBridgeEvent({
            requestId,
            stage: "agent_response",
            endpoint,
            ok: response.ok,
            status: response.status,
            data: truncateText(JSON.stringify(parsed), 1500)
        });
        return { ok: response.ok, status: response.status, data: parsed };
    } catch {
        const raw = { raw: truncateText(text, 2000) };
        logBridgeEvent({
            requestId,
            stage: "agent_response",
            endpoint,
            ok: response.ok,
            status: response.status,
            data: raw
        });
        return { ok: response.ok, status: response.status, data: raw };
    }
}

async function callAgentExecuteNaturalLanguage(message, requestId, sender = null) {
    return postJson("/execute-nl", { message }, requestId, sender);
}

async function callAgentBucherimSms(payload, requestId, sender = null) {
    return postJson("/bucherim/sms", payload, requestId, sender);
}

function formatAgentError(result) {
    if (result.data && result.data.detail) {
        return `Agent error (${result.status}): ${result.data.detail}`;
    }
    if (result.data && result.data.error) {
        return `Error: ${result.data.error}`;
    }
    return `Agent error (${result.status}): ${JSON.stringify(result.data)}`;
}

async function buildReply(message, requestId, from) {
    const normalized = message.trim();

    if (!normalized) {
        return "Empty message.";
    }

    // SMS bridge is transport-only: always use the shared natural-language core.
    const result = await callAgentExecuteNaturalLanguage(normalized, requestId, from);

    if (!result.ok) {
        return formatAgentError(result);
    }

    const output = result.data.output || "";
    const error = result.data.error || "";

    if (result.data.success) {
        return output || "Done.";
    } else {
        return error || "Could not process your request.";
    }
}

async function buildBucherimReply({ message, from, to, requestId, messageSid, accountSid, media }) {
    const result = await callAgentBucherimSms({
        from_number: from,
        to_number: to,
        body: message,
        message_sid: messageSid || null,
        account_sid: accountSid || null,
        media: media || [],
    }, requestId, from);

    if (!result.ok) {
        return {
            reply: formatAgentError(result),
            fullReply: formatAgentError(result),
            status: "error",
            responseMode: "error",
            outboundMedia: [],
        };
    }

    const reply = String(result.data.reply || result.data.output || "Done.");
    const outboundMedia = Array.isArray(result.data.outbound_media) ? result.data.outbound_media : [];

    return {
        reply,
        fullReply: String(result.data.full_reply || reply),
        status: String(result.data.status || "unknown"),
        responseMode: String(result.data.response_mode || "text"),
        outboundMedia,
    };
}

/**
 * Check if a message is a mode control command.
 * Returns the target mode if it is, null otherwise.
 * Control commands are case-insensitive and must match exactly.
 */
function getControlCommandMode(message) {
    const normalized = (message || "").trim().toUpperCase();
    if (normalized === MODE_COMMAND_BUCHERIM.toUpperCase()) {
        return sessionManager.MODES.BUCHERIM;
    }
    if (normalized === MODE_COMMAND_MASHBAK.toUpperCase()) {
        return sessionManager.MODES.MASHBAK;
    }
    return null;
}

app.get("/", (req, res) => {
    res.status(200).send("SMS bridge is running.");
});

app.get("/health", (req, res) => {
    res.status(200).json({
        status: "ok",
        port: PORT,
        logFile: LOG_FILE,
        twilioValidationEnabled: Boolean(TWILIO_AUTH_TOKEN),
        senderAccessControlEnabled: true,
        sessionRoutingEnabled: true,
        bucherimTimeoutMs: sessionManager.BUCHERIM_TIMEOUT_MS,
        accessControlConfigLoadedAt: ACCESS_CONFIG_LOADED_AT,
        accessControlReloadRequiresRestart: true
    });
});

app.get("/sms", (req, res) => {
    res.status(200).send("SMS endpoint is reachable.");
});

app.post("/sms", async (req, res) => {
    const requestId = createRequestId();
    const message = (req.body.Body || "").trim();
    const safeMessage = redactConfigAssignments(message);
    const from = req.body.From || "";
    const to = req.body.To || "";
    const messageSid = req.body.MessageSid || "";
    const accountSid = req.body.AccountSid || "";
    const inboundMedia = extractInboundMedia(req.body);
    const normalizedTo = normalizeToE164(to);
    const normalizedBucherimNumber = normalizeToE164(BUCHERIM_TWILIO_NUMBER);

    // Normalize sender using access control config normalization digits
    const normalizedFrom = normalizePhoneNumber(from, SENDER_ACCESS.normalizationDigits);
    const isOwner = normalizedFrom === SENDER_ACCESS.ownerNumber;

    console.log(`[sms] requestId=${requestId} from=${from} normalizedFrom=${normalizedFrom} body=${safeMessage}`);
    logBridgeEvent({
        requestId,
        stage: "incoming_sms",
        from,
        normalizedFrom,
        to,
        normalizedTo,
        messageSid,
        message: safeMessage,
        mediaCount: inboundMedia.length,
        media: inboundMedia,
        url: getRequestUrlCandidates(req)[0] || req.originalUrl
    });

    if (!isValidTwilioRequest(req)) {
        console.warn(`[sms] requestId=${requestId} rejected invalid Twilio signature from=${from}`);
        logBridgeEvent({
            requestId,
            stage: "rejected",
            reason: "invalid_twilio_signature",
            from,
            message: safeMessage
        });
        res.status(403).send("Forbidden");
        return;
    }

    let reply;
    let fullReply = "";
    let outboundMedia = [];

    try {
        // Step 1: Check if sender is authorized (owner)
        // Unauthorized senders are immediately denied
        if (!isOwner) {
            console.log(`[sms] requestId=${requestId} unauthorized_sender normalizedFrom=${normalizedFrom}`);
            logBridgeEvent({
                requestId,
                stage: "sender_authorization_check",
                normalizedFrom,
                isOwner: false,
                authorized: false,
                action: "denied"
            });
            reply = SENDER_ACCESS.denialResponse;
        } else {
            // Step 2: Check if this is a mode control command from the authorized owner
            const controlMode = getControlCommandMode(message);
            if (controlMode) {
                // Handle mode switch - this is a control command, don't forward to assistant
                const previousMode = sessionManager.getCurrentMode(normalizedFrom);
                const modeChangeResult = sessionManager.setMode(normalizedFrom, controlMode);
                
                console.log(`[sms] requestId=${requestId} mode_switch from=${previousMode} to=${controlMode}`);
                logBridgeEvent({
                    requestId,
                    stage: "mode_control_command",
                    normalizedFrom,
                    controlCommand: message,
                    previousMode,
                    newMode: controlMode,
                    switched: previousMode !== controlMode,
                    switchTime: modeChangeResult.timestamp
                });

                // Acknowledge the mode switch without forwarding to assistant
                reply = `Switched to ${controlMode} mode.`;
            } else {
                // Step 3: Not a control command. Check sender authorization and get routing mode.
                const senderDecision = resolveSenderAction(from, SENDER_ACCESS);

                if (!senderDecision.shouldForward) {
                    // This shouldn't happen if isOwner is true and authorization was done correctly
                    // But handle it defensively
                    console.log(
                        `[sms] requestId=${requestId} sender=${senderDecision.normalizedFrom} action=${senderDecision.action}`
                    );
                    logBridgeEvent({
                        requestId,
                        stage: "sender_access_control",
                        from,
                        normalizedFrom: senderDecision.normalizedFrom,
                        action: senderDecision.action,
                        message: safeMessage,
                        forwarded: false
                    });
                    reply = senderDecision.reply;
                } else {
                    // Authorized sender, not a control command. Now determine routing mode.
                    // Get current mode (this updates lastActivityTime)
                    const currentMode = sessionManager.getCurrentMode(normalizedFrom);
                    const sessionInfo = sessionManager.getSessionInfo(normalizedFrom);
                    const wasTimedOut = sessionInfo.isTimedOut;

                    console.log(
                        `[sms] requestId=${requestId} authorized_owner routing currentMode=${currentMode} wasTimedOut=${wasTimedOut}`
                    );
                    logBridgeEvent({
                        requestId,
                        stage: "sender_authorization_check",
                        normalizedFrom,
                        isOwner: true,
                        authorized: true,
                        action: "route_to_session_mode"
                    });

                    logBridgeEvent({
                        requestId,
                        stage: "session_routing_decision",
                        normalizedFrom,
                        currentMode,
                        wasTimedOut,
                        modeSetTime: sessionInfo.modeSetTime,
                        lastActivityTime: sessionInfo.lastActivityTime
                    });

                    // Route based on current mode
                    if (currentMode === sessionManager.MODES.BUCHERIM) {
                        const bucherimResult = await buildBucherimReply({
                            message,
                            from,
                            to,
                            requestId,
                            messageSid,
                            accountSid,
                            media: inboundMedia,
                        });
                        reply = bucherimResult.reply;
                        fullReply = bucherimResult.fullReply;
                        outboundMedia = bucherimResult.outboundMedia || [];
                        logBridgeEvent({
                            requestId,
                            stage: "route_bucherim",
                            normalizedFrom,
                            status: bucherimResult.status,
                            responseMode: bucherimResult.responseMode,
                            mediaCount: inboundMedia.length,
                            outboundMediaCount: outboundMedia.length,
                        });
                    } else {
                        // Default route: Mashbak (MASHBAK mode)
                        reply = await buildReply(message, requestId, from);
                        logBridgeEvent({
                            requestId,
                            stage: "route_mashbak",
                            normalizedFrom,
                            mediaCount: inboundMedia.length,
                        });
                    }
                }
            }
        }
    } catch (error) {
        logBridgeEvent({
            requestId,
            stage: "bridge_error",
            error: error.message,
            stack: truncateText(error.stack || "", 2000)
        });
        reply = `Bridge error: ${error.message}`;
        fullReply = reply;
    }

    if (reply.length > 1500) {
        reply = `${reply.slice(0, 1497)}...`;
    }

    logBridgeEvent({
        requestId,
        stage: "reply_ready",
        from,
        normalizedFrom,
        reply: truncateText(reply, 2000),
        fullReply: truncateText(fullReply || reply, 2000),
        outboundMediaCount: outboundMedia.length,
    });

    res.status(200);
    res.type("text/xml");
    if (outboundMedia.length > 0) {
        res.send(buildTwimlMessageWithMedia(reply, outboundMedia));
    } else {
        res.send(buildTwimlMessage(reply));
    }
    logBridgeEvent({
        requestId,
        stage: "reply_sent",
        status: 200
    });
});

app.listen(PORT, () => {
    logBridgeEvent({
        stage: "startup",
        port: PORT,
        publicBaseUrl: PUBLIC_BASE_URL,
        twilioValidationEnabled: Boolean(TWILIO_AUTH_TOKEN),
        senderAccessControlEnabled: true,
        sessionRoutingEnabled: true,
        bucherimTimeoutMs: sessionManager.BUCHERIM_TIMEOUT_MS,
        modeCommands: {
            bucherim: MODE_COMMAND_BUCHERIM,
            mashbak: MODE_COMMAND_MASHBAK,
        },
        ownerNumber: SENDER_ACCESS.ownerNumber,
        hershyNumber: SENDER_ACCESS.hershyNumber || null,
        rejectedNumbers: Array.from(SENDER_ACCESS.rejectedNumbers),
        accessRequestNumbers: Array.from(SENDER_ACCESS.accessRequestNumbers),
    });
    console.log(`SMS server running on port ${PORT}`);
    console.log(`[bridge] Session routing enabled. Owner number: ${SENDER_ACCESS.ownerNumber}`);
    console.log(`[bridge] Mode commands: '${MODE_COMMAND_BUCHERIM}' and '${MODE_COMMAND_MASHBAK}'`);
    console.log(`[bridge] Bucherim timeout: ${sessionManager.BUCHERIM_TIMEOUT_MS / 1000 / 60} minutes`);
});