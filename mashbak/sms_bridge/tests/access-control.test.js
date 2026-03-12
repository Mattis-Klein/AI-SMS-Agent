const test = require("node:test");
const assert = require("node:assert/strict");

const {
    isAccessRequestCommand,
    loadSenderAccessConfig,
    normalizePhoneNumber,
    resolveSenderAction,
} = require("../access-control-config");

test("normalizePhoneNumber keeps last 10 digits", () => {
    assert.equal(normalizePhoneNumber("+1 (848) 329-1230"), "8483291230");
    assert.equal(normalizePhoneNumber("18483291230"), "8483291230");
});

test("owner number is forwarded", () => {
    const config = loadSenderAccessConfig({
        SMS_OWNER_NUMBER: "8483291230",
        SMS_ACCESS_REQUEST_NUMBERS: "9297546860",
    });

    const decision = resolveSenderAction("+1 848 329 1230", config);
    assert.equal(decision.action, "forwarded");
    assert.equal(decision.shouldForward, true);
});

test("access request number is not forwarded", () => {
    const config = loadSenderAccessConfig({
        SMS_OWNER_NUMBER: "8483291230",
        SMS_ACCESS_REQUEST_NUMBERS: "9297546860",
    });

    const decision = resolveSenderAction("9297546860", config);
    assert.equal(decision.action, "access_request_response");
    assert.equal(decision.shouldForward, false);
});

test("Hershy number gets special response", () => {
    const config = loadSenderAccessConfig({
        SMS_OWNER_NUMBER: "8483291230",
        HERSHY_NUMBER: "8457017405",
        HERSHY_RESPONSE: "custom response",
    });

    const decision = resolveSenderAction("8457017405", config);
    assert.equal(decision.action, "special_response");
    assert.equal(decision.reply, "custom response");
});

test("rejected numbers get rejection response", () => {
    const config = loadSenderAccessConfig({
        SMS_OWNER_NUMBER: "8483291230",
        REJECTED_NUMBERS: "4155988428,3475988428",
        REJECTED_RESPONSE: "rejected message",
    });

    const decision1 = resolveSenderAction("4155988428", config);
    assert.equal(decision1.action, "rejected");
    assert.equal(decision1.reply, "rejected message");

    const decision2 = resolveSenderAction("3475988428", config);
    assert.equal(decision2.action, "rejected");
    assert.equal(decision2.reply, "rejected message");
});

test("access request keyword is configurable", () => {
    const config = loadSenderAccessConfig({
        SMS_ACCESS_REQUEST_KEYWORD: "@grant",
    });

    assert.equal(isAccessRequestCommand("@grant", config), true);
    assert.equal(isAccessRequestCommand("@mashbak", config), false);
});
