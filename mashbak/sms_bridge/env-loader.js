const fs = require("fs");
const dotenv = require("dotenv");

function loadEnvFile(envPath, targetEnv = process.env) {
    if (!fs.existsSync(envPath)) {
        return {};
    }

    const parsed = dotenv.parse(fs.readFileSync(envPath, "utf8"));
    for (const [key, value] of Object.entries(parsed)) {
        if (!(key in targetEnv)) {
            targetEnv[key] = value;
        }
    }
    return parsed;
}

module.exports = {
    loadEnvFile,
};
