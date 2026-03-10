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
const ALLOWED_SMS_FROM = new Set(
    (process.env.ALLOWED_SMS_FROM || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
);

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

if (ALLOWED_SMS_FROM.size === 0) {
    console.warn("[bridge] ALLOWED_SMS_FROM is not set. Sender allowlisting is disabled.");
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
    return String(value || "").replace(/[\s()-]/g, "");
}

function isAllowedSender(from) {
    if (ALLOWED_SMS_FROM.size === 0) {
        return true;
    }

    return ALLOWED_SMS_FROM.has(normalizePhoneNumber(from));
}

function getRequestUrl(req) {
    if (PUBLIC_BASE_URL) {
        return `${PUBLIC_BASE_URL}${req.originalUrl}`;
    }

    const forwardedProtocol = (req.headers["x-forwarded-proto"] || "").split(",")[0].trim();
    const protocol = forwardedProtocol || req.protocol || "https";
    const host = req.headers["x-forwarded-host"] || req.get("host");
    return `${protocol}://${host}${req.originalUrl}`;
}

function isValidTwilioRequest(req) {
    if (!TWILIO_AUTH_TOKEN) {
        return true;
    }

    const signature = req.get("x-twilio-signature") || "";
    if (!signature) {
        return false;
    }

    return twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, getRequestUrl(req), req.body || {});
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

async function callAgentExecuteTool(toolName, args, requestId, sender = null) {
    return postJson("/execute", { tool_name: toolName, args }, requestId, sender);
}

async function callAgentExecuteNaturalLanguage(message, requestId, sender = null) {
    return postJson("/execute-nl", { message }, requestId, sender);
}

// Legacy compatibility functions (forward to new endpoints)
async function callAgentRun(name, requestId, sender = null, args = {}) {
    return callAgentExecuteTool(name, args, requestId, sender);
}

async function executeAiTool(toolName, args, requestId, sender = null) {
    // Deprecated: This function is kept for backward compatibility only.
    // The agent now handles tool execution directly.
    return {
        ok: false,
        status: 400,
        data: { detail: "Direct AI tool execution is no longer supported. Use /execute-nl for natural language." }
    };
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

function formatHelp() {
    return [
        "Commands:",
        "hello - Test connection",
        "help - Show this help",
        "tools - List available tools",
        "run <name> - Run a tool",
        "  Examples: run system_info, run cpu_usage, run dir_inbox",
        "list <path> - List files",
        "  Example: list C:\\Users\\Documents",
        "",
        "Or send natural language requests - agent will interpret:"
        "  'check my inbox', 'show cpu', 'what time is it'"
    ].join("\n");
}

async function buildReply(message, requestId, from) {
    const normalized = message.trim();
    const lower = normalized.toLowerCase();

    if (!normalized) {
        return "Empty message.";
    }

    // Handle special commands
    if (lower === "hello") {
        return "Hi. SMS link is working.";
    }

    if (lower === "help") {
        return formatHelp();
    }

    // List available tools
    if (lower === "tools") {
        try {
            const response = await fetch(`${AGENT_URL}/tools`, {
                method: "GET",
                headers: {
                    "x-api-key": AGENT_API_KEY,
                    "x-request-id": requestId,
                    "x-sender": from
                }
            });

            if (response.ok) {
                const data = await response.json();
                const toolList = Object.entries(data.tools)
                    .map(([name, info]) => `${name}: ${info.description}`)
                    .join("\n");
                return `Available tools:\n${toolList}`;
            } else {
                return "Could not fetch tool list.";
            }
        } catch (error) {
            return `Error fetching tools: ${error.message}`;
        }
    }

    // Handle "run <name>" command
    if (lower.startsWith("run ")) {
        const toolName = normalized.slice(4).trim();
        if (!toolName) {
            return "Please specify a tool name. Example: run system_info";
        }
        const result = await callAgentExecuteTool(toolName, {}, requestId, from);
        if (!result.ok) {
            return formatAgentError(result);
        }
        const output = result.data.output || "";
        return output || `${toolName} executed successfully.`;
    }

    // Handle "list <path>" command
    if (lower.startsWith("list ")) {
        const path = normalized.slice(5).trim();
        if (!path) {
            return "Please specify a path. Example: list C:\\Projects";
        }
        const result = await callAgentExecuteTool("list_files", { path }, requestId, from);
        if (!result.ok) {
            return formatAgentError(result);
        }
        const output = result.data.output || "";
        return output || `Listed files in ${path}.`;
    }

    // Forward any other message to natural language interpreter
    const result = await callAgentExecuteNaturalLanguage(normalized, requestId, from);
    
    if (!result.ok) {
        return formatAgentError(result);
    }
    
    const output = result.data.output || "";
    const error = result.data.error || "";
    
    if (result.data.success) {
        return output || "Command executed successfully.";
    } else {
        return error || "Could not process your request. Text HELP for available commands.";
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
        senderAllowlistEnabled: ALLOWED_SMS_FROM.size > 0
    });
});

app.get("/sms", (req, res) => {
    res.status(200).send("SMS endpoint is reachable.");
});

app.post("/sms", async (req, res) => {
    const requestId = createRequestId();
    const message = (req.body.Body || "").trim();
    const from = req.body.From || "";

    console.log(`[sms] requestId=${requestId} from=${from} body=${message}`);
    logBridgeEvent({
        requestId,
        stage: "incoming_sms",
        from,
        message,
        url: getRequestUrl(req)
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

    if (!isAllowedSender(from)) {
        console.warn(`[sms] requestId=${requestId} rejected sender not on allowlist from=${from}`);
        logBridgeEvent({
            requestId,
            stage: "rejected",
            reason: "sender_not_allowed",
            from,
            message
        });
        res.status(403).send("Forbidden");
        return;
    }

    let reply;
    try {
        reply = await buildReply(message, requestId, from);
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
        senderAllowlistEnabled: ALLOWED_SMS_FROM.size > 0
    });
    console.log(`SMS server running on port ${PORT}`);
});