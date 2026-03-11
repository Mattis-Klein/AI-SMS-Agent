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

function loadEnvFile(envPath) {
    if (!fs.existsSync(envPath)) {
        return;
    }

    const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);
    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.startsWith("#")) {
            continue;
        }

        const separator = line.indexOf("=");
        if (separator === -1) {
            continue;
        }

        const key = line.slice(0, separator).trim();
        const value = line.slice(separator + 1).trim();
        if (!(key in process.env)) {
            process.env[key] = value;
        }
    }
}

loadEnvFile(path.join(__dirname, ".env"));

const app = express();
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

const BASE_DIR = __dirname;
const AGENT_URL = process.env.AGENT_URL || "http://127.0.0.1:8787";
const AGENT_API_KEY = process.env.AGENT_API_KEY || "";
const PORT = Number(process.env.BRIDGE_PORT || 34567);
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL || "").replace(/\/$/, "");
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID || "";
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN || "";
const TWILIO_FROM_NUMBER = process.env.TWILIO_FROM_NUMBER || "";
const LOG_DIR = path.join(BASE_DIR, "logs");
const LOG_FILE = path.join(LOG_DIR, "bridge.log");
const LOG_ARCHIVE_FILE = path.join(LOG_DIR, "bridge.log.1");
const LOG_MAX_BYTES = Number(process.env.BRIDGE_LOG_MAX_BYTES || 1_000_000);
const SENDER_ACCESS = loadSenderAccessConfig(process.env);

fs.mkdirSync(LOG_DIR, { recursive: true });

const twilioRestClient = (TWILIO_ACCOUNT_SID && TWILIO_AUTH_TOKEN)
    ? twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    : null;

if (!AGENT_API_KEY) {
    throw new Error("AGENT_API_KEY is required. Set it in sms-bridge/.env or the environment.");
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
        ...event
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

async function postJson(endpoint, payload, requestId, sender = null) {
    logBridgeEvent({
        requestId,
        stage: "agent_request",
        endpoint,
        payload: truncateText(JSON.stringify(payload), 1000),
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

app.get("/", (req, res) => {
    res.status(200).send("SMS bridge is running.");
});

app.get("/health", (req, res) => {
    res.status(200).json({
        status: "ok",
        port: PORT,
        logFile: LOG_FILE,
        twilioValidationEnabled: Boolean(TWILIO_AUTH_TOKEN),
        senderAccessControlEnabled: true
    });
});

app.get("/sms", (req, res) => {
    res.status(200).send("SMS endpoint is reachable.");
});

app.post("/sms", async (req, res) => {
    const requestId = createRequestId();
    const message = (req.body.Body || "").trim();
    const from = req.body.From || "";
    const to = req.body.To || "";
    const senderDecision = resolveSenderAction(from, SENDER_ACCESS);

    console.log(`[sms] requestId=${requestId} from=${from} body=${message}`);
    logBridgeEvent({
        requestId,
        stage: "incoming_sms",
        from,
        normalizedFrom: senderDecision.normalizedFrom,
        message,
        url: getRequestUrlCandidates(req)[0] || req.originalUrl
    });

    if (!isValidTwilioRequest(req)) {
        console.warn(`[sms] requestId=${requestId} rejected invalid Twilio signature from=${from}`);
        logBridgeEvent({
            requestId,
            stage: "rejected",
            reason: "invalid_twilio_signature",
            from,
            message
        });
        res.status(403).send("Forbidden");
        return;
    }

    if (!senderDecision.shouldForward) {
        console.log(
            `[sms] requestId=${requestId} sender=${senderDecision.normalizedFrom} action=${senderDecision.action}`
        );
        logBridgeEvent({
            requestId,
            stage: "sender_access_control",
            from,
            normalizedFrom: senderDecision.normalizedFrom,
            action: senderDecision.action,
            message,
            forwarded: false
        });
    }

    let reply;
    try {
        if (senderDecision.shouldForward) {
            console.log(
                `[sms] requestId=${requestId} sender=${senderDecision.normalizedFrom} action=${senderDecision.action}`
            );
            logBridgeEvent({
                requestId,
                stage: "sender_access_control",
                from,
                normalizedFrom: senderDecision.normalizedFrom,
                action: senderDecision.action,
                message,
                forwarded: true
            });
            reply = await buildReply(message, requestId, from);
        } else {
            reply = senderDecision.reply;
            if (senderDecision.action === "access_request_response" && isAccessRequestCommand(message, SENDER_ACCESS)) {
                await notifyOwnerAccessRequest({
                    requestId,
                    normalizedFrom: senderDecision.normalizedFrom,
                    inboundTo: to,
                });
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
    }

    if (reply.length > 1500) {
        reply = `${reply.slice(0, 1497)}...`;
    }

    logBridgeEvent({
        requestId,
        stage: "reply_ready",
        from,
        reply: truncateText(reply, 2000)
    });

    res.status(200);
    res.type("text/xml");
    res.send(buildTwimlMessage(reply));
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
        ownerNumber: SENDER_ACCESS.ownerNumber,
        specialNumbers: Object.keys(SENDER_ACCESS.specialResponses),
        accessRequestNumbers: Array.from(SENDER_ACCESS.accessRequestNumbers),
    });
    console.log(`SMS server running on port ${PORT}`);
});