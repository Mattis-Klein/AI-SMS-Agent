# Security Baseline

This document describes the **baseline security** implemented in the system. For **advanced hardening**, see [../SECURITY-HARDENING.md](../SECURITY-HARDENING.md).

## Current Built-In Security

### Authentication

- **API Key Required:** Bridge and agent communicate with `AGENT_API_KEY`
  - Must be the same in both `mashbak/.env.master` and `mashbak/.env.master`
  - Prevents unauthorized access to the local agent

### Sender Verification

- **Twilio Signature Validation:** Enabled when `TWILIO_AUTH_TOKEN` is set
  - Verifies all webhooks actually come from Twilio
  - Prevents spoofed SMS

- **Sender Allowlist:** Filter by phone number
  - Set `SMS_ACCESS_REQUEST_NUMBERS` to restrict who can use the bridge
  - Recommended: Set to only your phone number

### Path Isolation

- **Workspace Restriction:** All file operations limited to `agent/workspace/`
  - No directory traversal attacks (e.g., `../../etc/passwd` is blocked)
  - Cannot read/write outside the workspace

### Command Control

- **Allowlist Only:** Commands must be explicitly enabled
  - Only `dir_inbox`, `dir_outbox`, and file operations allowed
  - No arbitrary shell execution

---

## Required Settings Before Production Use

✅ **Enable before regular use:**

```env
# In mashbak/.env.master
TWILIO_AUTH_TOKEN=<get from Twilio Console>
SMS_ACCESS_REQUEST_NUMBERS=<your phone number>
AGENT_API_KEY=<strong random string, not default>

# In mashbak/.env.master
AGENT_API_KEY=<same as above>
```

---

## Current Gaps

- ❌ No rate limiting (anyone can spam SMS)
- ❌ No request approval workflows
- ❌ No per-user permissions (shared access)
- ❌ No audit logging (logs aren't immutable)
- ❌ No automatic log rotation (logs grow unbounded)

---

## Recommended Next Steps

1. **Enable the baseline settings** above
2. **Review [Security Hardening Guide](../SECURITY-HARDENING.md)** for advanced hardening
3. **Follow [Best Practices](../BEST-PRACTICES.md)** for operational security
4. **Rotate API keys monthly** (see [../BEST-PRACTICES.md](../BEST-PRACTICES.md))

---

## Production Readiness

⚠️ **Not recommended for production yet.**

This system is suitable for:
- ✅ Personal use
- ✅ Small team experiments
- ✅ Learning and development

Not recommended for:
- ❌ Shared/public access
- ❌ Business-critical operations
- ❌ Handling sensitive data at scale

Consider adding rate limiting, approval workflows, and comprehensive audit logging before production use.

---

## Resources

- **Complete Security Guide:** [../SECURITY-HARDENING.md](../SECURITY-HARDENING.md)
- **Best Practices:** [../BEST-PRACTICES.md](../BEST-PRACTICES.md)
- **Environment Setup:** [../ENVIRONMENT.md](../ENVIRONMENT.md)

---

**Last Updated:** March 8, 2026
