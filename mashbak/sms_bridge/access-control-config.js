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

function parseRejectedNumbers(rawValue, digits = 10) {
    return new Set(parseCsvNumbers(rawValue, digits));
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

    const hershyNumber = normalizePhoneNumber(
        env.HERSHY_NUMBER || fileConfig.hershy_number || "",
        normalizationDigits
    );

    const rejectedNumbers = parseRejectedNumbers(
        env.REJECTED_NUMBERS || fileConfig.rejected_numbers || "",
        normalizationDigits
    );

    return {
        ownerNumber,
        accessRequestNumbers,
        hershyNumber,
        hershyResponse: env.HERSHY_RESPONSE || fileConfig.hershy_response || "",
        rejectedNumbers,
        rejectedResponse: env.REJECTED_RESPONSE || fileConfig.rejected_response || "you are not authorized to use this system",
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

    if (config.hershyNumber && normalizedFrom === config.hershyNumber) {
        return {
            action: "special_response",
            normalizedFrom,
            shouldForward: false,
            reply: config.hershyResponse,
        };
    }

    if (config.rejectedNumbers.has(normalizedFrom)) {
        return {
            action: "rejected",
            normalizedFrom,
            shouldForward: false,
            reply: config.rejectedResponse,
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
