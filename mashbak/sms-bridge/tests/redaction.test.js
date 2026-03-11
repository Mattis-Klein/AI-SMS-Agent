const test = require("node:test");
const assert = require("node:assert/strict");

const { redactConfigAssignments, sanitize } = require("../redaction");

test("redactConfigAssignments hides config values", () => {
    const source = "EMAIL_PASSWORD=hunter2 and TWILIO_AUTH_TOKEN: abc123";
    const redacted = redactConfigAssignments(source);
    assert.equal(redacted.includes("hunter2"), false);
    assert.equal(redacted.includes("abc123"), false);
    assert.equal(redacted.includes("EMAIL_PASSWORD=[REDACTED]"), true);
    assert.equal(redacted.includes("TWILIO_AUTH_TOKEN:[REDACTED]"), true);
});

test("sanitize redacts variable_value and sensitive keys recursively", () => {
    const payload = {
        args: {
            variable_name: "EMAIL_PASSWORD",
            variable_value: "super-secret",
        },
        message: "EMAIL_PASSWORD=super-secret",
    };

    const safe = sanitize(payload);
    assert.equal(safe.args.variable_value, "[REDACTED]");
    assert.equal(String(JSON.stringify(safe)).includes("super-secret"), false);
});
