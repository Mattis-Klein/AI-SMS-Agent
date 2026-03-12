const fs = require("fs");
const os = require("os");
const path = require("path");
const test = require("node:test");
const assert = require("node:assert/strict");

const { loadEnvFile } = require("../env-loader");

function makeTempEnvFile(contents) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "mashbak-env-"));
    const envPath = path.join(dir, ".env.master");
    fs.writeFileSync(envPath, contents, "utf8");
    return envPath;
}

test("dotenv loader parses quoted values, URLs, inline comments, and special chars", () => {
    const envPath = makeTempEnvFile(
        [
            'PUBLIC_BASE_URL="https://example.com/path?a=1&b=2"',
            "OPENAI_BASE_URL=https://api.openai.com/v1 # comment",
            "OPENAI_TIMEOUT_SECONDS=41.5",
            "OPENAI_TEMPERATURE=0.7",
            'SPECIAL_VALUE="abc#123=xyz"',
            "RAW_TOKEN=hello_world",
        ].join("\n")
    );

    const target = {};
    loadEnvFile(envPath, target);

    assert.equal(target.PUBLIC_BASE_URL, "https://example.com/path?a=1&b=2");
    assert.equal(target.OPENAI_BASE_URL, "https://api.openai.com/v1");
    assert.equal(target.OPENAI_TIMEOUT_SECONDS, "41.5");
    assert.equal(target.OPENAI_TEMPERATURE, "0.7");
    assert.equal(target.SPECIAL_VALUE, "abc#123=xyz");
    assert.equal(target.RAW_TOKEN, "hello_world");
});

test("dotenv loader does not override existing process values", () => {
    const envPath = makeTempEnvFile(
        [
            "AGENT_URL=http://127.0.0.1:8787",
            "BRIDGE_PORT=34567",
        ].join("\n")
    );

    const target = {
        AGENT_URL: "http://override.local:9999",
    };

    loadEnvFile(envPath, target);

    assert.equal(target.AGENT_URL, "http://override.local:9999");
    assert.equal(target.BRIDGE_PORT, "34567");
});
