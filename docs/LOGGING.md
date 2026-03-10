# Logging Guide

Understanding logs for debugging and monitoring.

## Log Locations

### Bridge Log

Location:
```
sms-bridge/logs/bridge.log
```

Updated by: **SMS Bridge (Node.js)**

Contains:
- Incoming SMS events
- Twilio signature validation
- Sender allowlist checks
- Agent API calls
- AI/OpenAI calls
- Outbound SMS replies
- Errors and warnings

### Agent Log

Location:
```
agent/workspace/logs/agent.log
```

Updated by: **Local Agent (Python)**

Contains:
- File read/write operations
- Command execution
- Path validation
- Authentication attempts
- Workspace access logs

---

## Log Format

Both logs use JSON format (one entry per line) for easy parsing.

### Bridge Log Entry Example

```json
{
  "timestamp": "2025-03-08T10:35:45.123Z",
  "request_id": "abc-123-def-456",
  "event_type": "incoming_sms",
  "from": "+18005551234",
  "body": "hello",
  "status": "received"
}
```

### Agent Log Entry Example

```json
{
  "request_id": "abc-123-def-456",
  "time": "2025-03-08T10:35:45",
  "action": "read",
  "path": "inbox/test.txt",
  "status": "success"
}
```

---

## Reading Logs

### View Last 20 Lines

```powershell
Get-Content sms-bridge\logs\bridge.log -Tail 20
Get-Content agent\workspace\logs\agent.log -Tail 20
```

---

### Follow Logs Live

```powershell
Get-Content -Path sms-bridge\logs\bridge.log -Wait
```

Press `Ctrl+C` to exit. Updates as new entries appear.

---

### Open in Text Editor

```powershell
notepad sms-bridge\logs\bridge.log
notepad agent\workspace\logs\agent.log
```

---

### Search for Errors

```powershell
Select-String "error\|failed\|rejected" sms-bridge\logs\bridge.log
Select-String "auth_failed\|invalid_path" agent\workspace\logs\agent.log
```

---

### Filter by Request ID

When an SMS fails, trace through both logs using the `request_id`:

```powershell
# Find in bridge log
Select-String "abc-123-def-456" sms-bridge\logs\bridge.log

# Find in agent log
Select-String "abc-123-def-456" agent\workspace\logs\agent.log
```

---

## Common Log Events

### Bridge Log Events

#### `incoming_sms`

New SMS received from Twilio.

```json
{
  "event_type": "incoming_sms",
  "from": "+18005551234",
  "body": "hello",
  "timestamp": "...",
  "request_id": "..."
}
```

**Action:** Bridge received the SMS from Twilio.

---

#### `signature_validated`

Twilio signature verification passed.

```json
{
  "event_type": "signature_validated",
  "status": "ok"
}
```

**Action:** SMS is confirmed to be from Twilio.

---

#### `sender_allowed`

Phone number is in allowlist.

```json
{
  "event_type": "sender_allowed",
  "from": "+18005551234"
}
```

**Action:** Sender is permitted to use the bridge.

---

#### `fixed_command`

Fixed command detected (not AI).

```json
{
  "event_type": "fixed_command",
  "command": "hello",
  "request_id": "..."
}
```

**Action:** Handled as direct command, not sent to AI.

---

#### `agent_request`

Bridge calling the local agent.

```json
{
  "event_type": "agent_request",
  "method": "read",
  "path": "inbox/test.txt",
  "request_id": "...",
  "agent_url": "http://127.0.0.1:8787"
}
```

**Action:** Bridge is calling agent to read/write/run command.

---

#### `agent_response`

Agent returned successfully.

```json
{
  "event_type": "agent_response",
  "status": 200,
  "result": "File contents...",
  "request_id": "..."
}
```

**Action:** Agent completed the task.

---

#### `reply_ready`

Response ready to send back.

```json
{
  "event_type": "reply_ready",
  "message": "Response text",
  "length": 160
}
```

**Action:** Bridge prepared TwiML response.

---

#### `reply_sent`

Response sent to Twilio.

```json
{
  "event_type": "reply_sent",
  "status": "sent",
  "twilio_sid": "SM..."
}
```

**Action:** TwiML delivered to Twilio.

---

### Bridge Error Events

#### `invalid_twilio_signature`

Webhook signature validation failed.

```json
{
  "event_type": "rejected",
  "reason": "invalid_twilio_signature"
}
```

**Likely causes:**
- `TWILIO_AUTH_TOKEN` is wrong
- `PUBLIC_BASE_URL` doesn't match
- Twilio sent different signature

**Fix:** Check `.env` settings and Twilio Console.

---

#### `sender_not_allowed`

Phone number not in allowlist.

```json
{
  "event_type": "rejected",
  "reason": "sender_not_allowed",
  "from": "+15555551234"
}
```

**Likely causes:**
- `ALLOWED_SMS_FROM` doesn't include this number
- Number format mismatch (+1 prefix missing?)

**Fix:** Add the number to `ALLOWED_SMS_FROM` in `.env`.

---

#### `agent_error`

Bridge couldn't reach or parse agent response.

```json
{
  "event_type": "agent_error",
  "reason": "connection_failed",
  "error": "..."
}
```

**Likely causes:**
- Agent not running
- Wrong `AGENT_URL` in `.env`
- Port mismatch

**Fix:** Check agent is running on correct port.

---

#### `ai_error`

OpenAI API call failed.

```json
{
  "event_type": "ai_error",
  "reason": "invalid_api_key"
}
```

**Likely causes:**
- `OPENAI_API_KEY` is invalid
- Out of API credits
- Model name is wrong

**Fix:** Verify API key and credits.

---

### Agent Log Events

#### `read`

File read successful.

```json
{
  "request_id": "...",
  "action": "read",
  "path": "inbox/test.txt",
  "status": "success"
}
```

---

#### `read_missing`

File doesn't exist.

```json
{
  "request_id": "...",
  "action": "read_missing",
  "path": "inbox/missing.txt"
}
```

---

#### `write`

File created successfully.

```json
{
  "request_id": "...",
  "action": "write",
  "path": "inbox/new.txt"
}
```

---

#### `write_exists`

File already exists, not overwriting.

```json
{
  "request_id": "...",
  "action": "write_exists",
  "path": "inbox/test.txt"
}
```

---

#### `invalid_path`

Path is outside workspace.

```json
{
  "request_id": "...",
  "action": "invalid_path",
  "path": "C:/Windows/System32/config"
}
```

---

#### `auth_failed`

Wrong API key.

```json
{
  "request_id": "...",
  "action": "auth_failed"
}
```

---

#### `command_rejected`

Command not in allowlist.

```json
{
  "request_id": "...",
  "action": "command_rejected",
  "command": "rm_all_files"
}
```

---

## Debugging Workflow

### Step 1: Identify the Request ID

When SMS fails, find the entry in bridge log:

```powershell
Get-Content sms-bridge\logs\bridge.log | Select-String "incoming_sms" | Tail -1
```

Note the `request_id` field.

---

### Step 2: Trace Bridge Log

Search bridge log for that request ID:

```powershell
Select-String "abc-123-def-456" sms-bridge\logs\bridge.log
```

Look for these events in order:
1. `incoming_sms` - SMS entered the system
2. `signature_validated` or `invalid_twilio_signature` - signature check
3. `sender_allowed` or `sender_not_allowed` - allowlist check
4. `fixed_command` or `ai_request` - what kind of request
5. `agent_request` - bridge calling agent (if applicable)
6. `agent_response` or `agent_error` - agent result
7. `reply_ready` - response prepared
8. `reply_sent` - sent to Twilio

---

### Step 3: Trace Agent Log

If there was an `agent_request`, search the agent log:

```powershell
Select-String "abc-123-def-456" agent\workspace\logs\agent.log
```

Look for the action:
- `read` or `read_missing`
- `write` or `write_exists`
- `run` or `command_rejected`
- `auth_failed` or `invalid_path`

---

### Step 4: Cross-Reference

Match events between logs. Example:

**Bridge log:**
```
agent_request: path=inbox/test.txt, request_id=abc-123
agent_response: status=404, request_id=abc-123
```

**Agent log:**
```
action=read_missing, path=inbox/test.txt, request_id=abc-123
```

This shows: Agent was asked to read `inbox/test.txt`, but file didn't exist.

---

## Log Rotation

Logs may grow large over time. Manual rotation:

```powershell
# Backup old logs
Move-Item sms-bridge\logs\bridge.log sms-bridge\logs\bridge.log.bak
Move-Item agent\workspace\logs\agent.log agent\workspace\logs\agent.log.bak

# Clear current logs
Clear-Content sms-bridge\logs\bridge.log
Clear-Content agent\workspace\logs\agent.log

# Restart services to recreate log files
```

Or set `BRIDGE_LOG_MAX_BYTES` in `.env` for automatic rotation.

---

## Log File Size Limits

Check how big logs are:

```powershell
(Get-Item sms-bridge\logs\bridge.log).Length / 1MB  # Size in MB
(Get-Item agent\workspace\logs\agent.log).Length / 1MB
```

If over 100 MB, consider clearing old entries or rotating.

---

## Good Log Habits

1. **Check logs first** - Most issues are in the logs
2. **Use request_id** - Trace through both logs at once
3. **Look for error events** - Rejected, failed, error
4. **Note timestamps** - Match to when SMS was sent
5. **Keep old logs** - Don't rotate too frequently
6. **Grep/search regularly** - Catch patterns early

---

## JSON Log Parsing (Advanced)

You can parse logs as JSON in PowerShell:

```powershell
Get-Content sms-bridge\logs\bridge.log | ForEach-Object { 
  try { 
    $_ | ConvertFrom-Json 
  } catch { 
    Write-Error "Invalid JSON: $_" 
  } 
} | Where-Object event_type -eq "agent_error"
```

Or convert to CSV:

```powershell
Get-Content sms-bridge\logs\bridge.log | 
  ForEach-Object { $_ | ConvertFrom-Json } | 
  Export-Csv bridge-logs.csv -NoTypeInformation
```

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [Runbook](RUNBOOK.md), [Troubleshooting](legacy/TROUBLESHOOTING.md)
