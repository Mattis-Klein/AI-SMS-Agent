const REDACTED = "[REDACTED]";

const CONFIG_ASSIGNMENT_RE = /\b([A-Z_][A-Z0-9_]*)\b\s*([:=])\s*(.*?)(?=(?:\s+\b[A-Z_][A-Z0-9_]*\b\s*[:=])|$|\r|\n)/g;

const SENSITIVE_VAR_NAMES = new Set([
    "OPENAI_API_KEY",
    "EMAIL_PASSWORD",
    "EMAIL_PASS",
    "TWILIO_AUTH_TOKEN",
    "AGENT_API_KEY",
    "LOCAL_APP_PIN",
]);

function redactConfigAssignments(text) {
    const value = String(text ?? "");
    return value.replace(CONFIG_ASSIGNMENT_RE, (_full, varName, sep) => `${varName}${sep}${REDACTED}`);
}

function isSensitiveKey(key) {
    const normalized = String(key || "").toLowerCase();
    if (!normalized) {
        return false;
    }
    return (
        normalized === "variable_value"
        || normalized.includes("password")
        || normalized.includes("token")
        || normalized.includes("api_key")
        || normalized.includes("secret")
        || normalized.includes("authorization")
    );
}

function sanitize(value, key = "") {
    if (value === null || value === undefined) {
        return value;
    }

    if (typeof value === "string") {
        if (isSensitiveKey(key)) {
            return REDACTED;
        }
        return redactConfigAssignments(value);
    }

    if (Array.isArray(value)) {
        return value.map((item) => sanitize(item, key));
    }

    if (typeof value === "object") {
        const output = {};
        const variableName = String(value.variable_name || "").toUpperCase();

        for (const [innerKey, innerValue] of Object.entries(value)) {
            if (innerKey === "variable_value" || isSensitiveKey(innerKey)) {
                output[innerKey] = REDACTED;
                continue;
            }

            if (
                variableName
                && SENSITIVE_VAR_NAMES.has(variableName)
                && ["raw_message", "raw_request", "message", "payload", "reply"].includes(innerKey)
            ) {
                output[innerKey] = redactConfigAssignments(String(innerValue));
                continue;
            }

            output[innerKey] = sanitize(innerValue, innerKey);
        }
        return output;
    }

    return value;
}

module.exports = {
    REDACTED,
    redactConfigAssignments,
    sanitize,
};
