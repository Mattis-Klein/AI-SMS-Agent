# Environment Configuration (.env.master Reference)

Complete reference for Mashbak's master configuration system.

## 2026-03 Update: Master Configuration File + Chat Configuration

- **NEW**: Single master configuration file consolidates all environment variables: `mashbak/.env.master`
- Configuration variables can be provided directly through chat
- Backend maintains in-memory session context per sender/source
- Email setup guidance supports both canonical and alias variable names
- SMS sender access control is configuration-driven, not hardcoded

## Master Configuration System

### Single Source of Truth: `.env.master`

All Mashbak configuration is now centralized in a single file:

```
mashbak/.env.master
```

Loading order:
1. **Master config** (`mashbak/.env.master`) - primary source
2. **Local overrides** (`mashbak/agent/.env` or `mashbak/sms-bridge/.env`) - optional development overrides
3. **OS environment** - if neither file exists

### Setup

**1. Create from template:**
```powershell
cd mashbak
cp .env.master.example .env.master
```

**2. Edit with your credentials:**
```powershell
notepad .env.master
```

**3. Secure the file (never commit to git):**
```
.env.master is in .gitignore - your secrets are safe
```

### Configuration via Chat (Recommended)

Configure variables directly through assistant conversation:

```
User:  EMAIL_ADDRESS = myemail@gmail.com
Assistant: ✓ Configuration updated: EMAIL_ADDRESS has been set.

User:  EMAIL_PASSWORD = app-password-123
Assistant: ✓ Configuration updated: EMAIL_PASSWORD has been set.

User:  Show my recent emails
Assistant: [emails load successfully]
```

**How it works:**
- You send: `VARIABLE_NAME = value`
- Assistant validates the variable name and value format
- If valid, updates `mashbak/.env.master` and applies immediately
- Sensitive values (passwords, API keys) are never echoed in responses

**Supported variables for chat configuration:**
- Email: `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `EMAIL_IMAP_HOST`, `IMAP_SERVER`, `EMAIL_IMAP_PORT`, `IMAP_PORT`, `EMAIL_MAILBOX`, `EMAIL_PROVIDER`, `EMAIL_USE_SSL`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`
- Desktop: `LOCAL_APP_PIN`
- SMS / Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `SMS_OWNER_NUMBER`

**Security Notes:**
- Validated but not echoed: passwords, API keys, tokens, PINs
- Changes persist across service restarts
- All validation in backend tool system (never in UI/bridge)

### Configuration via File (Developers)

Edit `mashbak/.env.master` directly:

```
OPENAI_API_KEY=sk-proj-...
EMAIL_ADDRESS=user@gmail.com
EMAIL_PASSWORD=app-password
```

Changes are immediately available to all services on next execution.

---

## Master Configuration Variables

Organized by system component.

### OPENAI / AI MODEL

**Purpose:** Enable ChatGPT-powered features for conversation summarization

```
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```

- `OPENAI_API_KEY`: Leave empty to disable AI (fallback replies will be used)
- `OPENAI_MODEL`: Default `gpt-4o-mini` (cheapest tier)

### AGENT SECURITY & IDENTITY

**Purpose:** Secure bridge-to-agent communication; agent workspace configuration

API key used by backend assistant for richer conversational responses and tool-result summarization.

**Example:**
```
OPENAI_API_KEY=sk-proj-abc123...
```

**Rules:**
- Stored in `agent/.env` or process environment
- If missing, Mashbak still runs with deterministic fallback replies

---

### Email Tool Configuration (`agent/.env`)

Required values (canonical + alias support):
- `EMAIL_IMAP_HOST` or `IMAP_SERVER`
- `EMAIL_IMAP_PORT` or `IMAP_PORT`
- `EMAIL_USERNAME` or `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`

Optional:
- `EMAIL_PROVIDER`
- `EMAIL_MAILBOX`
- `EMAIL_USE_SSL`

When missing, assistant responses now include:
- exact missing variable names,
- config file location (`mashbak/agent/.env`),
- and clear remediation instructions.

---

#### `OPENAI_MODEL`

**Type:** String  
**Required:** No (default: `gpt-4.1-mini`)

Model used by desktop freeform AI chat.

**Example:**
```
OPENAI_MODEL=gpt-4.1-mini
```

---

## `sms-bridge/.env`

Configuration for the SMS bridge and Twilio integration.

### Required Variables - Agent Connection

#### `AGENT_URL`

**Type:** URL  
**Required:** Yes

Where the bridge can reach the local agent.

**Example:**
```
AGENT_URL=http://127.0.0.1:8787
```

**Rules:**
- Must match the agent's `--host` and `--port` startup args
- Must be `http://` (not https for local connections)
- Using `127.0.0.1` is fine if on same machine
- No trailing slash

---

#### `AGENT_API_KEY`

**Type:** String (secret)  
**Required:** Yes

API key for authenticating agent requests.

**Example:**
```
AGENT_API_KEY=my-super-secret-key-12345
```

**Rules:**
- Must match `AGENT_API_KEY` in `agent/.env`
- Same as in agent config

---

### Required Variables - Bridge & Network

#### `BRIDGE_PORT`

**Type:** Integer  
**Required:** Yes

Port the bridge listens on locally.

**Example:**
```
BRIDGE_PORT=34567
BRIDGE_PORT=3001
BRIDGE_PORT=9000
```

**Rules:**
- Must not conflict with other services
- Common conflicts: 3000 (VS Code), 3001 (some dev servers)
- Using `34567` is safe
- Must match the local port used by your public tunnel process

**Testing:**
```powershell
netstat -ano | findstr :34567
```

---

#### `PUBLIC_BASE_URL`

**Type:** URL  
**Required:** Yes

Exact public URL that Twilio calls.

**Example:**
```
PUBLIC_BASE_URL=https://abc123.trycloudflare.com
PUBLIC_BASE_URL=https://my-bridge.example.com
```

**Rules:**
- Must include `https://`
- Must be the exact public URL currently used by your tunnel
- No trailing slash
- Must match webhook URL in Twilio Console

**Get your URL:**
Use the URL printed by your tunnel command, for example:

```powershell
cloudflared tunnel --url http://localhost:34567
```

---

### Sender Access Control Variables (`sms-bridge/.env`)

These preserve current behavior while making routing configurable:

- `SMS_OWNER_NUMBER`
- `SMS_ACCESS_REQUEST_NUMBERS` (comma-separated)
- `SMS_ACCESS_REQUEST_KEYWORD`
- `SMS_ACCESS_REQUEST_RESPONSE`
- `SMS_DENIAL_RESPONSE`
- `SMS_SPECIAL_RESPONSES_JSON` (JSON map)
- `SMS_PHONE_NORMALIZATION_DIGITS`
- `SMS_ACCESS_CONFIG_FILE` (optional JSON file path)

These settings are evaluated in the bridge transport layer; the backend remains the only reasoning core.

---

### Required Variables - Twilio

#### `TWILIO_AUTH_TOKEN`

**Type:** String (secret)  
**Required:** Yes (for production)

Auth token for validating Twilio webhook signatures.

**Example:**
```
TWILIO_AUTH_TOKEN=abc123def456ghi789jkl
```

**Rules:**
- Get from Twilio Console → Account → Auth Token
- Used to verify webhook comes from Twilio
- Empty string = signature validation disabled
- Recommended: Always set for security

**Find it:**
1. Go https://www.twilio.com/console
2. Account (top right) → Settings
3. Copy "Auth Token"

---

#### `TWILIO_ACCOUNT_SID`

**Type:** String (secret)  
**Required:** Yes (for owner notification SMS)

Twilio Account SID used by the bridge when sending owner notification SMS
after an access-request number texts `@mashbak`.

**Example:**
```
TWILIO_ACCOUNT_SID=AC1234567890abcdef1234567890abcd
```

---

#### `TWILIO_FROM_NUMBER`

**Type:** Phone number (E.164)  
**Required:** Recommended

Outbound Twilio number used when bridge sends owner notifications.

**Example:**
```
TWILIO_FROM_NUMBER=+18005551234
```

**Rules:**
- Must be a Twilio SMS-capable number on your account
- If empty, bridge falls back to webhook `To` value when available

---

### Sender Access Control (Bridge Code)

Sender access is now enforced in `sms-bridge/sms-server.js` using
normalized phone-number matching (last 10 digits).

Current behavior:
- Owner `8483291230` -> forwarded to agent backend
- Special `8457017405` -> fixed special response
- Access-request numbers (`9297546860`, `9176355825`) -> fixed access-request response
- All others -> `This number is not allowed.`

If an access-request number sends exactly `@mashbak`, bridge sends an owner
notification SMS without forwarding the request to the agent.

---

### Optional Variables - AI Mode

#### `OPENAI_API_KEY`

**Type:** String (secret)  
**Required:** No (AI mode disabled if missing)

OpenAI API key for natural language processing.

**Example:**
```
OPENAI_API_KEY=sk-proj-abc123...
```

**Rules:**
- If empty or missing: AI mode disabled, fixed commands only
- If set: Every SMS that's not a fixed command goes to AI
- Get from https://platform.openai.com/api-keys

**Cost:**
- API charges apply per message
- ~$0.01 per message typical

---

#### `OPENAI_MODEL`

**Type:** String  
**Required:** No (default: `gpt-4.1-mini`)

Which OpenAI model to use for AI mode.

**Example:**
```
OPENAI_MODEL=gpt-4.1-mini
OPENAI_MODEL=gpt-4
OPENAI_MODEL=gpt-3.5-turbo
```

**Rules:**
- Only matters if `OPENAI_API_KEY` is set
- Newer models cost more, faster
- Older models cost less, slower/less capable

**Recommendations:**
- Start with `gpt-4.1-mini` (good balance)
- Increase to `gpt-4` for complex tasks
- Decrease to `gpt-3.5-turbo` to save cost

---

#### `AI_MAX_TOOL_ROUNDS`

**Type:** Integer  
**Required:** No (default: `6`)

Max times AI can call the agent tools in one conversation.

**Example:**
```
AI_MAX_TOOL_ROUNDS=6
AI_MAX_TOOL_ROUNDS=3
AI_MAX_TOOL_ROUNDS=10
```

**Rules:**
- Default (6) is good for most cases
- Higher = more flexible but slower
- Lower = faster but less capable

---

### Optional Variables - Logging

#### `BRIDGE_LOG_MAX_BYTES`

**Type:** Integer  
**Required:** No (default: `1000000`)

Max size of bridge log before rotation.

**Example:**
```
BRIDGE_LOG_MAX_BYTES=1000000
BRIDGE_LOG_MAX_BYTES=5000000
BRIDGE_LOG_MAX_BYTES=100000
```

**Rules:**
- Default is 1 MB
- When exceeded, log rolls to `.log.1`
- Smaller = more frequent rotation

---

## Example `.env` Files

### `agent/.env` (Minimal)

```env
AGENT_API_KEY=my-secret-key-12345
AGENT_WORKSPACE=agent/workspace
```

### `agent/.env` (Full)

```env
# Local agent config
AGENT_API_KEY=dev-sk-abc123xyz789def456
AGENT_WORKSPACE=agent/workspace
```

### `sms-bridge/.env` (Minimal - Testing Only)

```env
# Agent connection
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=my-secret-key-12345

# Bridge network
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://my-bridge.trycloudflare.com

# Twilio (disabled for local testing)
TWILIO_AUTH_TOKEN=
ALLOWED_SMS_FROM=
```

### `sms-bridge/.env` (Production - Recommended)

```env
# Agent connection
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=dev-sk-abc123xyz789def456

# Bridge network
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://my-bridge.trycloudflare.com

# Twilio security
TWILIO_AUTH_TOKEN=auth_token_from_twilio_console
ALLOWED_SMS_FROM=+18005551234

# Optional: AI mode
OPENAI_API_KEY=sk-proj-abc123xyz789...
OPENAI_MODEL=gpt-4.1-mini
AI_MAX_TOOL_ROUNDS=6

# Logging
BRIDGE_LOG_MAX_BYTES=1000000
```

---

## Validation Checklist

Before starting the system:

- [ ] Both `.env` files exist
- [ ] `AGENT_API_KEY` is identical in both files
- [ ] `AGENT_URL` matches agent startup command
- [ ] `BRIDGE_PORT` is not in use (check with `netstat`)
- [ ] `PUBLIC_BASE_URL` matches your current public tunnel URL
- [ ] `TWILIO_AUTH_TOKEN` is from Twilio Console
- [ ] `ALLOWED_SMS_FROM` is your phone number or blank
- [ ] If using AI: `OPENAI_API_KEY` is valid
- [ ] All URLs have no trailing slash
- [ ] Phone numbers start with `+`

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| `AGENT_API_KEY` mismatch | Compare both `.env` files, must be identical |
| Can't reach agent | Verify `AGENT_URL` matches agent startup port |
| Port in use | Change `BRIDGE_PORT` to different number |
| Twilio rejects webhook | Verify `PUBLIC_BASE_URL` and `TWILIO_AUTH_TOKEN` |
| SMS from unknown number accepted | Check `ALLOWED_SMS_FROM`, may be empty |
| AI not working | Ensure `OPENAI_API_KEY` is set and valid |
| Connection refused | Are agent and bridge running? Check ports |

---

## Security Notes

- **API Keys**: Treat like passwords, never commit to git
- **Auth Token**: Twilio can validate signatures with this (good)
- **Allowed From**: Restrict to your number only
- **Public URL**: Must be exact match or signature validation fails

See [Security Hardening](SECURITY-HARDENING.md) for advanced security practices.

---

**Last Updated**: March 8, 2026  
**Version**: 1.0
