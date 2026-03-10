# Command Whitelist and Security Guide

## 📋 Command Whitelist System

The AI-SMS-Agent uses a whitelist-based security model. Only pre-approved commands can execute on your machine.

### How It Works

1. **Commands are defined** in `agent/config.json`
2. **When an SMS arrives**, the bridge forwards it to the agent
3. **The agent validates** the command name against the whitelist
4. **If approved**, the command executes with validated arguments
5. **If blocked**, an error message is returned

This prevents arbitrary code execution while allowing safe, controlled operations.

### Command Structure

Each command in `config.json` has this structure:

```json
{
  "allowed_commands": {
    "command_name": {
      "description": "Human-readable description",
      "command": ["executable", "arg1", "arg2", "{placeholder}"],
      "requires_args": false,
      "validate_path": false
    }
  }
}
```

**Fields:**
- `description` - What the command does (shown in `commands` list)
- `command` - Array of command parts (executable + arguments)
- `requires_args` - Whether user must provide arguments
- `validate_path` - Whether to validate path arguments against allowed directories

### Placeholders

Commands can use these placeholders:

- `{workspace}` - Replaced with `agent/workspace` absolute path
- `{path}` - Replaced with user-provided path (validated if `validate_path: true`)

**Example:**
```json
"list_files": {
  "command": ["cmd", "/c", "dir", "{path}"],
  "validate_path": true
}
```

When user sends `list C:\Projects`, the system:
1. Validates `C:\Projects` is in `allowed_directories`
2. Replaces `{path}` with `C:\Projects`
3. Executes: `cmd /c dir C:\Projects`

### Path Validation

**Purpose:** Prevent unauthorized file system access

**Rules:**
1. Paths are always validated before use
2. Only these locations are allowed:
   - Agent workspace (`agent/workspace/`)
   - Directories listed in `allowed_directories`
3. Directory traversal is blocked (`.`, `..`, etc.)
4. Symbolic links are resolved before validation

**Allowed Directories:**

Configured in `config.json`:
```json
{
  "allowed_directories": [
    "C:\\Users\\Public\\Documents",
    "C:\\Projects",
    "C:\\Temp"
  ]
}
```

**What happens when validation fails:**
- Command is blocked
- Error logged with `status: "blocked"`
- SMS response: `"Path is not in allowed directories"`

### Extension Blocking

**Purpose:** Prevent creation of executable files

**Blocked extensions:**
- `.exe` - Executables
- `.bat` - Batch files
- `.cmd` - Command scripts
- `.ps1` - PowerShell scripts
- `.vbs` - VBScript files
- `.js` - JavaScript files (can execute via Windows Script Host)

Configured in `config.json`:
```json
{
  "security": {
    "blocked_extensions": [".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js"]
  }
}
```

**What happens when blocked:**
- Write operation is blocked
- Error logged with `status: "blocked"`
- SMS response: `"Blocked file extension: .exe"`

### File Size Limits

**Purpose:** Prevent disk space exhaustion

**Default limit:** 10MB (10,485,760 bytes)

Configured in `config.json`:
```json
{
  "security": {
    "max_file_size_bytes": 10485760
  }
}
```

**Applies to:**
- File reads
- File writes
- File content validation

**What happens when exceeded:**
- Operation is blocked
- Error logged
- SMS response: `"File too large"` or `"Content too large"`

### Command Timeout

**Purpose:** Prevent long-running commands from blocking the system

**Timeout:** 30 seconds per command

**What happens on timeout:**
- Command process is terminated
- Error logged with `status: "error"`
- SMS response: `"Command timed out after 30 seconds"`

## 📊 Structured Logging

Every action is logged in JSON format for easy parsing and auditing.

### Log Locations

- **Agent logs:** `agent/workspace/logs/agent.log`
- **Bridge logs:** `sms-bridge/logs/bridge.log`

### Log Entry Structure

Each log entry is a single JSON object per line:

```json
{
  "time": "2026-03-09T14:30:15",
  "hostname": "DESKTOP-ABC123",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "sender": "+15551234567",
  "action": "command_complete",
  "name": "system_info",
  "return_code": 0,
  "status": "success"
}
```

**Common fields:**
- `time` - ISO 8601 timestamp
- `hostname` - Machine hostname (agent only)
- `request_id` - Unique ID for the request
- `sender` - Phone number that sent the SMS
- `action` - What happened
- `status` - `success`, `error`, `blocked`, or `running`

### Agent Log Actions

| Action | Description | Status |
|--------|-------------|--------|
| `auth_failed` | Invalid API key | `error` |
| `command_start` | Command execution started | `running` |
| `command_complete` | Command finished | `success`/`failed` |
| `command_rejected` | Command not in whitelist | `blocked` |
| `command_missing_args` | Required args not provided | `error` |
| `command_timeout` | Command exceeded 30s | `error` |
| `read` | File read successful | `success` |
| `read_missing` | File not found | `error` |
| `write` | File written successfully | `success` |
| `write_exists` | File already exists | `error` |
| `blocked_extension` | Dangerous file extension | `blocked` |
| `invalid_path` | Path outside allowed areas | `blocked` |
| `list_commands` | Command list requested | `success` |

### Bridge Log Actions

| Action | Description |
|--------|-------------|
| `startup` | Bridge server started |
| `incoming_sms` | SMS received from Twilio |
| `rejected` | Request rejected (invalid signature or sender) |
| `agent_request` | Sending request to agent |
| `agent_response` | Response received from agent |
| `reply_ready` | SMS response prepared |
| `reply_sent` | SMS response sent to Twilio |
| `bridge_error` | Bridge encountered an error |
| `ai_request` | OpenAI request sent |
| `ai_response` | OpenAI response received |
| `ai_tool_error` | AI tool call failed |

### Analyzing Logs

**View recent activity:**
```powershell
# Last 10 entries
Get-Content agent\workspace\logs\agent.log -Tail 10 | ConvertFrom-Json | Format-Table
```

**Find blocked commands:**
```powershell
Get-Content agent\workspace\logs\agent.log | ConvertFrom-Json | Where-Object { $_.status -eq "blocked" }
```

**Track a specific request:**
```powershell
$requestId = "550e8400-e29b-41d4-a716-446655440000"
Get-Content agent\workspace\logs\agent.log | ConvertFrom-Json | Where-Object { $_.request_id -eq $requestId }
```

**Count commands by sender:**
```powershell
Get-Content agent\workspace\logs\agent.log | ConvertFrom-Json | Where-Object { $_.sender } | Group-Object sender | Select-Object Count, Name
```

### Log Rotation

**Agent logs** do not rotate automatically. Monitor file size manually.

**Bridge logs** rotate automatically:
- When `bridge.log` exceeds 1MB
- Old log is renamed to `bridge.log.1`
- Previous `bridge.log.1` is deleted

Configure in `sms-bridge/.env`:
```
BRIDGE_LOG_MAX_BYTES=1000000
```

### Privacy Considerations

Logs contain:
- ✅ Phone numbers of SMS senders
- ✅ Commands executed
- ✅ File paths accessed
- ✅ Error messages
- ❌ File contents (not logged)
- ❌ API keys (never logged)

**For production use:**
- Encrypt log files at rest
- Restrict file system permissions on log directories
- Implement log retention policies
- Redact sensitive information before sharing logs

## 🔐 Sender Validation

**Purpose:** Only allow SMS from authorized phone numbers

**Configuration:** `sms-bridge/.env`
```
ALLOWED_SMS_FROM=+15551234567,+15559876543
```

**How it works:**
1. SMS arrives at bridge
2. Bridge extracts `From` field
3. Normalizes phone number (removes spaces, dashes, parentheses)
4. Checks against allowed list
5. If not allowed, returns 403 Forbidden

**Bypass:** Set `ALLOWED_SMS_FROM` to empty string to disable (not recommended)

## 🔒 Twilio Signature Verification

**Purpose:** Verify SMS webhooks came from Twilio, not an attacker

**Configuration:** `sms-bridge/.env`
```
TWILIO_AUTH_TOKEN=your-twilio-token
PUBLIC_BASE_URL=https://your-tunnel.trycloudflare.com
```

**How it works:**
1. Twilio sends webhook with `X-Twilio-Signature` header
2. Bridge computes expected signature using:
   - Webhook URL
   - POST parameters
   - Twilio auth token
3. If signatures match, request is authentic
4. If mismatch, returns 403 Forbidden

**Bypass:** Set `TWILIO_AUTH_TOKEN` to empty string to disable (not recommended)

## 🛡️ Defense in Depth

The system uses multiple security layers:

| Layer | Purpose | Failure Impact |
|-------|---------|----------------|
| Sender validation | Block unauthorized numbers | Medium (all requests blocked if compromised) |
| Twilio signature | Verify webhook authenticity | High (prevents replay attacks) |
| Command whitelist | Block unauthorized commands | Critical (prevents arbitrary code) |
| Path validation | Block unauthorized file access | Critical (prevents data exfiltration) |
| Extension blocking | Block executable creation | High (prevents malware deployment) |
| File size limits | Prevent DOS attacks | Medium (prevents resource exhaustion) |
| Structured logging | Detect intrusions | Low (detective, not preventive) |

Even if one layer fails, others provide protection.

## 📝 Best Practices

1. **Regular audit:** Review logs weekly for suspicious activity
2. **Minimize whitelist:** Only add commands you actually need
3. **Restrict directories:** Keep `allowed_directories` minimal
4. **Keep secrets secret:** Never commit `.env` files
5. **Update dependencies:** Run `npm audit` and `pip list --outdated` regularly
6. **Test changes:** Test new commands in a safe environment first
7. **Monitor logs:** Set up alerts for `status: "blocked"` entries
8. **Rotate secrets:** Change `AGENT_API_KEY` and `TWILIO_AUTH_TOKEN` periodically

## 🚨 Incident Response

**If you suspect unauthorized access:**

1. **Immediate:** Shut down the system (`Ctrl+C` the launcher)
2. **Review logs:** Check for `status: "blocked"` or unknown senders
3. **Rotate credentials:** Change `AGENT_API_KEY`, `TWILIO_AUTH_TOKEN`, and OpenAI key
4. **Check file system:** Look for unexpected files in workspace
5. **Review config:** Ensure `config.json` hasn't been modified
6. **Restart:** Only restart after confirming security

**Investigation commands:**
```powershell
# Find all blocked attempts
Get-Content agent\workspace\logs\agent.log | ConvertFrom-Json | Where-Object { $_.status -eq "blocked" } | Format-Table

# Find unknown senders
Get-Content sms-bridge\logs\bridge.log | ConvertFrom-Json | Where-Object { $_.reason -eq "sender_not_allowed" } | Format-Table

# Check recent file operations
Get-Content agent\workspace\logs\agent.log | ConvertFrom-Json | Where-Object { $_.action -match "read|write" } | Format-Table
```

## 🔧 Troubleshooting

**Problem:** Commands are being blocked unexpectedly

**Solution:**
1. Check if command is in `config.json` whitelist
2. Check logs for exact error: `Get-Content agent\workspace\logs\agent.log -Tail 20`
3. Verify sender is in `ALLOWED_SMS_FROM`
4. Confirm path is in `allowed_directories` (for path-based commands)

**Problem:** Logs are too large

**Solution:**
1. Implement log rotation for agent logs
2. Archive old logs: `Move-Item agent\workspace\logs\agent.log agent\workspace\logs\agent.log.old`
3. Reduce logging verbosity (requires code changes)

**Problem:** Suspicious activity in logs

**Solution:**
1. Follow incident response procedure above
2. Add monitoring/alerting for blocked events
3. Consider reducing attack surface (fewer allowed commands, stricter paths)

---

For more information, see:
- [SECURITY-HARDENING.md](SECURITY-HARDENING.md) - Advanced security configurations
- [COMMANDS.md](COMMANDS.md) - Complete command reference
- [API.md](API.md) - Agent API documentation
