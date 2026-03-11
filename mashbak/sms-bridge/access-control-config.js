const fs = require("fs");
const path = require("path");

function normalizePhoneNumber(value, digits = 10) {
    const maxDigits = Number(digits) > 0 ? Number(digits) : 10;
    const cleaned = String(value || "").replace(/\D/g, "");
    if (cleaned.length > maxDigits) {
        return cleaned.slice(-maxDigits);
    }
    return cleaned;
}

function parseCsvNumbers(rawValue, digits = 10) {
    return String(rawValue || "")
        .split(",")
        .map((item) => normalizePhoneNumber(item, digits))
        .filter(Boolean);
}

function parseSpecialResponses(rawJson, digits = 10) {
    if (!rawJson) {
        return {};
    }
    try {
        const parsed = JSON.parse(rawJson);
        if (!parsed || typeof parsed !== "object") {
            return {};
        }
        const normalized = {};
        for (const [key, value] of Object.entries(parsed)) {
            const normalizedKey = normalizePhoneNumber(key, digits);
            if (normalizedKey) {
                normalized[normalizedKey] = String(value);
            }
        }
        return normalized;
    } catch {
        return {};
    }
}

function loadConfigFile(configPath) {
    if (!configPath) {
        return {};
    }

    const resolvedPath = path.isAbsolute(configPath)
        ? configPath
        : path.join(__dirname, configPath);

    if (!fs.existsSync(resolvedPath)) {
        return {};
    }

    try {
        const content = fs.readFileSync(resolvedPath, "utf8");
        const parsed = JSON.parse(content);
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
        return {};
    }
}

function loadSenderAccessConfig(env) {
    const fileConfig = loadConfigFile(env.SMS_ACCESS_CONFIG_FILE);
    const normalizationDigits = Number(
        env.SMS_PHONE_NORMALIZATION_DIGITS ||
        fileConfig.phone_normalization_digits ||
        10
    ) || 10;

    const ownerNumber = normalizePhoneNumber(
        env.SMS_OWNER_NUMBER || fileConfig.owner_number || "8483291230",
        normalizationDigits
    );

    const accessRequestNumbers = new Set(
        parseCsvNumbers(
            env.SMS_ACCESS_REQUEST_NUMBERS || fileConfig.access_request_numbers || "9297546860,9176355825",
            normalizationDigits
        )
    );

    const specialResponses = parseSpecialResponses(
        env.SMS_SPECIAL_RESPONSES_JSON || JSON.stringify(fileConfig.special_responses || {}),
        normalizationDigits
    );

    return {
        ownerNumber,
        accessRequestNumbers,
        specialResponses,
        denialResponse: env.SMS_DENIAL_RESPONSE || fileConfig.denial_response || "This number is not allowed.",
        accessRequestResponse:
            env.SMS_ACCESS_REQUEST_RESPONSE
            || fileConfig.access_request_response
            || "This number is not authorized to use this program. To request access, send @mashbak to this number and we will review your request.",
        accessRequestKeyword:
            String(env.SMS_ACCESS_REQUEST_KEYWORD || fileConfig.access_request_keyword || "@mashbak").trim().toLowerCase(),
        normalizationDigits,
    };
}

function isAccessRequestCommand(message, config) {
    const keyword = (config.accessRequestKeyword || "@mashbak").toLowerCase();
    return String(message || "").trim().toLowerCase() === keyword;
}

function resolveSenderAction(from, config) {
    const normalizedFrom = normalizePhoneNumber(from, config.normalizationDigits);

    if (normalizedFrom === config.ownerNumber) {
        return {
            action: "forwarded",
            normalizedFrom,
            shouldForward: true,
            reply: null,
        };
    }

    if (config.specialResponses[normalizedFrom]) {
        return {
            action: "special_response",
            normalizedFrom,
            shouldForward: false,
            reply: config.specialResponses[normalizedFrom],
        };
    }

    if (config.accessRequestNumbers.has(normalizedFrom)) {
        return {
            action: "access_request_response",
            normalizedFrom,
            shouldForward: false,
            reply: config.accessRequestResponse,
        };
    }

    return {
        action: "denied",
        normalizedFrom,
        shouldForward: false,
        reply: config.denialResponse,
    };
}

module.exports = {
    isAccessRequestCommand,
    loadSenderAccessConfig,
    normalizePhoneNumber,
    resolveSenderAction,
};
