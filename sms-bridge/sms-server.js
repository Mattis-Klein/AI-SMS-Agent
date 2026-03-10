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
    "Use tools only when needed.",
    "The available tools are read_file, write_file, and run_command.",
    "Paths are relative to the local agent workspace.",
    "The run_command tool only supports allowlisted command names exposed by the local agent.",
    "If something cannot be done with the available tools, say so briefly."
].join(" ");

const AI_TOOLS = [
    {
        type: "function",
        function: {
            name: "read_file",
            description: "Read a text file from the local agent workspace.",
            parameters: {
                type: "object",
                additionalProperties: false,
                properties: {
                    path: { type: "string", description: "Relative file path, for example inbox/todo.txt" }
                },
                required: ["path"]
            }
        }
    },
    {
        type: "function",
        function: {
            name: "write_file",
            description: "Create or overwrite a text file in the local agent workspace.",
            parameters: {
                type: "object",
                additionalProperties: false,
                properties: {
                    path: { type: "string", description: "Relative file path inside the workspace." },
                    content: { type: "string", description: "Full text content to write." },
                    overwrite: { type: "boolean", description: "Whether an existing file may be replaced." }
                },
                required: ["path", "content", "overwrite"]
            }
        }
    },
    {
        type: "function",
        function: {
            name: "run_command",
            description: "Run a named allowlisted command. Available commands: dir_inbox, dir_outbox, list_files, system_info, cpu_usage, disk_space, current_time, network_status, list_processes, uptime. Some commands like list_files require a 'path' argument.",
            parameters: {
                type: "object",
                additionalProperties: false,
                properties: {
                    name: { type: "string", description: "Allowlisted command name." },
                    args: {
                        type: "object",
                        description: "Optional arguments for the command. For list_files, include 'path'.",
                        properties: {
                            path: { type: "string", description: "Path argument for commands that require it (e.g., list_files)" }
                        }
                    }
                },
                required: ["name"]
            }
        }
    }
];

async function postJson(endpoint, payload, requestId, sender = null) {
    logBridgeEvent({
        requestId,
        stage: "agent_request",
        endpoint,
        payload,
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
            data: parsed
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

async function callAgentRun(name, requestId, sender = null, args = {}) {
    return postJson("/run", { name, args }, requestId, sender);
}

async function callAgentRead(filePath, requestId, sender = null) {
    return postJson("/read", { path: filePath }, requestId, sender);
}

async function callAgentWrite(filePath, content, overwrite, requestId, sender = null) {
    return postJson("/write", { path: filePath, content, overwrite }, requestId, sender);
}

async function executeAiTool(toolName, args, requestId, sender = null) {
    if (toolName === "read_file") {
        return callAgentRead(args.path, requestId, sender);
    }

    if (toolName === "write_file") {
        return callAgentWrite(args.path, args.content, Boolean(args.overwrite), requestId, sender);
    }

    if (toolName === "run_command") {
        return callAgentRun(args.name, requestId, sender, args.args || {});
    }

    return {
        ok: false,
        status: 400,
        data: { detail: `Unknown AI tool: ${toolName}` }
    };
}

function formatAgentError(result) {
    if (result.data && result.data.detail) {
        return `Agent error (${result.status}): ${result.data.detail}`;
    }

    return `Agent error (${result.status}): ${JSON.stringify(result.data)}`;
}

function formatHelp() {
    return [
        "Commands:",
        "hello - Test connection",
        "help - Show this help",
        "commands - List all available commands",
        "run <name> - Run a whitelisted command",
        "  Examples: run system_info, run cpu_usage, run dir_inbox",
        "list <path> - List files in directory",
        "  Example: list C:\\Projects",
        "read <path> - Read a file",
        "  Example: read inbox/notes.txt",
        "write <path> :: <text> - Write to file",
        "overwrite <path> :: <text> - Overwrite file",
        "",
        "Or just send plain English - AI will help when OpenAI is configured."
    ].join("\n");
}

function shouldUseAi(lowerMessage) {
    if (!openai) {
        return false;
    }

    return !(
        lowerMessage === "hello" ||
        lowerMessage === "help" ||
        lowerMessage === "commands" ||
        lowerMessage.startsWith("run ") ||
        lowerMessage.startsWith("list ") ||
        lowerMessage.startsWith("read ") ||
        lowerMessage.startsWith("write ") ||
        lowerMessage.startsWith("overwrite ")
    );
}

async function buildAiReply(message, from, requestId) {
    const messages = [
        { role: "system", content: AI_SYSTEM_PROMPT },
        { role: "user", content: `Sender: ${from}\nMessage: ${message}` }
    ];

    for (let round = 0; round < AI_MAX_TOOL_ROUNDS; round += 1) {
        logBridgeEvent({
            requestId,
            stage: "ai_request",
            model: OPENAI_MODEL,
            round: round + 1,
            messages: messages.map((entry) => ({
                role: entry.role,
                content: truncateText(typeof entry.content === "string" ? entry.content : JSON.stringify(entry.content), 1500),
                tool_call_id: entry.tool_call_id,
                name: entry.name
            }))
        });

        const response = await openai.chat.completions.create({
            model: OPENAI_MODEL,
            messages,
            tools: AI_TOOLS,
            tool_choice: "auto"
        });

        const choice = response.choices[0];
        const assistantMessage = choice.message;

        logBridgeEvent({
            requestId,
            stage: "ai_response",
            model: OPENAI_MODEL,
            round: round + 1,
            finishReason: choice.finish_reason,
            content: truncateText(assistantMessage.content || "", 1500),
            toolCalls: (assistantMessage.tool_calls || []).map((toolCall) => ({
                id: toolCall.id,
                name: toolCall.function.name,
                arguments: truncateText(toolCall.function.arguments || "", 1500)
            }))
        });

        messages.push(assistantMessage);

        if (!assistantMessage.tool_calls || assistantMessage.tool_calls.length === 0) {
            return assistantMessage.content || "I could not produce a reply.";
        }

        for (const toolCall of assistantMessage.tool_calls) {
            let toolArgs;
            try {
                toolArgs = JSON.parse(toolCall.function.arguments || "{}");
            } catch (error) {
                const toolError = `Invalid tool arguments for ${toolCall.function.name}: ${error.message}`;
                logBridgeEvent({
                    requestId,
                    stage: "ai_tool_error",
                    tool: toolCall.function.name,
                    error: toolError
                });
                messages.push({
                    role: "tool",
                    tool_call_id: toolCall.id,
                    content: JSON.stringify({ ok: false, error: toolError })
                });
                continue;
            }

            const toolResult = await executeAiTool(toolCall.function.name, toolArgs, requestId, from);
            messages.push({
                role: "tool",
                tool_call_id: toolCall.id,
                content: JSON.stringify(toolResult)
            });
        }
    }

    return "I hit the tool-call limit before finishing the request.";
}

async function buildReply(message, requestId, from) {
    const normalized = message.trim();
    const lower = normalized.toLowerCase();

    if (!normalized) {
        return "Empty message.";
    }

    if (lower === "hello") {
        return "Hi. SMS link is working.";
    }

    if (lower === "help") {
        return formatHelp();
    }

    // New commands command - list available commands
    if (lower === "commands") {
        try {
            const response = await fetch(`${AGENT_URL}/commands`, {
                method: "GET",
                headers: {
                    "x-api-key": AGENT_API_KEY,
                    "x-request-id": requestId,
                    "x-sender": from
                }
            });

            if (response.ok) {
                const data = await response.json();
                const cmdList = Object.entries(data.commands)
                    .map(([name, info]) => `${name}: ${info.description}`)
                    .join("\n");
                return `Available commands:\n${cmdList}`;
            } else {
                return "Could not fetch command list.";
            }
        } catch (error) {
            return `Error fetching commands: ${error.message}`;
        }
    }

    if (shouldUseAi(lower)) {
        return buildAiReply(normalized, from, requestId);
    }

    // Handle "list <path>" as shorthand for "run list_files" with path argument
    if (lower.startsWith("list ")) {
        const path = normalized.slice(5).trim();
        if (!path) {
            return "Please specify a path. Example: list C:\\Projects";
        }
        const result = await callAgentRun("list_files", requestId, from, { path });
        if (!result.ok) {
            return formatAgentError(result);
        }
        const stdout = (result.data.stdout || "").trim();
        const stderr = (result.data.stderr || "").trim();
        return stdout || stderr || `Listed ${path}`;
    }

    if (lower.startsWith("run ")) {
        const commandName = normalized.slice(4).trim();
        const result = await callAgentRun(commandName, requestId, from, {});
        if (!result.ok) {
            return formatAgentError(result);
        }

        const stdout = (result.data.stdout || "").trim();
        const stderr = (result.data.stderr || "").trim();
        return stdout || stderr || `${commandName} ran successfully.`;
    }

    if (lower.startsWith("read ")) {
        const filePath = normalized.slice(5).trim();
        const result = await callAgentRead(filePath, requestId, from);
        if (!result.ok) {
            return formatAgentError(result);
        }

        const content = (result.data.content || "").trim();
        return content || `${filePath} is empty.`;
    }

    if (lower.startsWith("write ") || lower.startsWith("overwrite ")) {
        const overwrite = lower.startsWith("overwrite ");
        const prefixLength = overwrite ? "overwrite ".length : "write ".length;
        const body = normalized.slice(prefixLength);
        const separator = body.indexOf("::");

        if (separator === -1) {
            return "Use write path :: text or overwrite path :: text";
        }

        const filePath = body.slice(0, separator).trim();
        const content = body.slice(separator + 2).trim();

        if (!filePath) {
            return "A file path is required.";
        }

        const result = await callAgentWrite(filePath, content, overwrite, requestId, from);
        if (!result.ok) {
            return formatAgentError(result);
        }

        return `Saved ${filePath}`;
    }

    if (!openai) {
        return "AI is not configured yet. Text HELP for fixed commands or set OPENAI_API_KEY in sms-bridge/.env.";
    }

    return "Command not recognized. Text HELP for the current command list.";
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