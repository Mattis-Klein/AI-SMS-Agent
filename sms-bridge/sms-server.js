const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const express = require("express");
const bodyParser = require("body-parser");
const OpenAI = require("openai");
const twilio = require("twilio");

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
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN || "";
const LOG_DIR = path.join(BASE_DIR, "logs");
const LOG_FILE = path.join(LOG_DIR, "bridge.log");
const LOG_ARCHIVE_FILE = path.join(LOG_DIR, "bridge.log.1");
const LOG_MAX_BYTES = Number(process.env.BRIDGE_LOG_MAX_BYTES || 1_000_000);
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4.1-mini";
const AI_MAX_TOOL_ROUNDS = Number(process.env.AI_MAX_TOOL_ROUNDS || 6);

const OWNER_NUMBER = "8483291230";
const SPECIAL_RESPONSES = new Map([
    ["8457017405", "placeholder1"],
    ["9178486202", "placeholder2"],
]);

fs.mkdirSync(LOG_DIR, { recursive: true });

const openai = OPENAI_API_KEY ? new OpenAI({ apiKey: OPENAI_API_KEY }) : null;

if (!AGENT_API_KEY) {
    throw new Error("AGENT_API_KEY is required. Set it in sms-bridge/.env or the environment.");
}

if (!PUBLIC_BASE_URL) {
    console.warn("[bridge] PUBLIC_BASE_URL is not set. Twilio signature validation will use request headers.");
}

if (!TWILIO_AUTH_TOKEN) {
    console.warn("[bridge] TWILIO_AUTH_TOKEN is not set. Twilio signature validation is disabled.");
}

if (!OPENAI_API_KEY) {
    console.warn("[bridge] OPENAI_API_KEY is not set. Natural-language AI mode is disabled.");
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

function normalizePhoneNumber(value) {
    const digits = String(value || "").replace(/\D/g, "");
    if (digits.length > 10) {
        return digits.slice(-10);
    }
    return digits;
}

function resolveSenderAction(from) {
    const normalizedFrom = normalizePhoneNumber(from);

    if (normalizedFrom === OWNER_NUMBER) {
        return {
            action: "forwarded",
            normalizedFrom,
            shouldForward: true,
            reply: null,
        };
    }

    if (SPECIAL_RESPONSES.has(normalizedFrom)) {
        return {
            action: "special_response",
            normalizedFrom,
            shouldForward: false,
            reply: SPECIAL_RESPONSES.get(normalizedFrom),
        };
    }

    return {
        action: "denied",
        normalizedFrom,
        shouldForward: false,
        reply: "This number is not allowed.",
    };
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

const AI_SYSTEM_PROMPT = [
    "You are an SMS-based assistant for a Windows PC.",
    "Keep replies concise because they are sent over SMS.",
    "The local agent handles all tool execution and natural language interpretation.",
].join(" ");


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

async function buildAiReply(message, from, requestId) {
    // Simply forward to agent's natural language interpreter
    const result = await callAgentExecuteNaturalLanguage(message, requestId, from);

    if (!result.ok) {
        return formatAgentError(result);
    }

    const output = result.data.output || "";
    const error = result.data.error || "";

    if (result.data.success) {
        return output || "Command executed successfully.";
    } else {
        return error || "Command failed.";
    }
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
    const senderDecision = resolveSenderAction(from);

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
        ownerNumber: OWNER_NUMBER,
        specialNumbers: Array.from(SPECIAL_RESPONSES.keys())
    });
    console.log(`SMS server running on port ${PORT}`);
});