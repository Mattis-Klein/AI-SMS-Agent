# Testing Guide

How to test the AI SMS Agent system.

---

## Testing Levels

### 1. Unit Testing (Code Level)

Test individual functions in isolation.

**Agent (Python):**

```python
# Test safe_path validation
from pathlib import Path
from agent import safe_path, WORKSPACE

# Test: Valid path
p = safe_path("inbox/file.txt")
assert p == WORKSPACE / "inbox/file.txt"

# Test: Invalid path (traversal)
try:
    safe_path("../../etc/passwd")
    assert False, "Should have raised"
except HTTPException:
    assert True  # Good

# Test: Invalid path (absolute)
try:
    safe_path("/etc/passwd")
    assert False
except HTTPException:
    assert True
```

**Bridge (Node):**

```javascript
// Test: Request validation
const { validateTwilioSignature } = require("./sms-server");

const signature = computeSignature(body, token);
assert(validateTwilioSignature(body, signature, token));
assert(!validateTwilioSignature(body, "wrong", token));
```

---

### 2. Integration Testing (Component Level)

Test components working together.

**Agent API Test:**

```powershell
# Start agent
cd agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787

# Test read endpoint
$headers = @{"X-API-Key" = "test-key"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/test.txt"}'

# Expected: Either 404 (not found) or file content
```

**Bridge API Test:**

```powershell
# Start agent first!

# Start bridge
cd sms-bridge
npm start

# Test bridge health
curl.exe http://127.0.0.1:34567/health

# Test bridge SMS handling
curl.exe -X POST http://127.0.0.1:34567/sms `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "Body=hello&From=%2B18005551234"

# Expected: TwiML response
```

---

### 3. System Testing (End-to-End)

Test entire system with real SMS.

**Requirements:**
- All three services running (agent, bridge, tunnel)
- Twilio account with SMS number
- Your phone number allowed in ALLOWED_SMS_FROM

**Test Steps:**

```
1. Start all services:
  Recommended: .\scripts\dev-start.ps1
   Or manually in three terminals if debugging

2. Send SMS from your phone: "hello"

3. Wait for reply (< 30 sec)

4. Check logs: sms-bridge/logs/bridge.log
   - Should see: incoming_sms, agent_request, agent_response

5. Check logs: agent/workspace/logs/agent.log
   - Should see: request_id matching bridge log
```

---

## Test Cases

### Basic Connectivity Tests

#### Test 1.1: Agent Health

```powershell
curl.exe http://127.0.0.1:8787/health
# Expected: {"status":"ok"}
```

**Pass Condition:** 200 status, JSON response

---

#### Test 1.2: Bridge Health

```powershell
curl.exe http://127.0.0.1:34567/health
# Expected: {"status":"ok"}
```

**Pass Condition:** 200 status, JSON response

---

#### Test 1.3: Tunnel Status

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'cloudflared' } | Select-Object ProcessId, Name
# Expected: cloudflared process running
```

**Pass Condition:** cloudflared process exists and tunnel terminal shows a valid public URL

---

### Fixed Command Tests

#### Test 2.1: "hello" Command

**SMS:** `hello`

**Expected Response:** "Hello from the AI SMS agent! I'm alive."

**Logs Should Contain:**
- bridge: `event_type: "incoming_sms"`, `body: "hello"`
- bridge: `event_type: "fixed_command"`, `command: "hello"`
- bridge: `event_type: "reply_sent"`

---

#### Test 2.2: "help" Command

**SMS:** `help`

**Expected Response:** List of available commands

**Logs Should Contain:**
- bridge: `event_type: "fixed_command"`, `command: "help"`

---

#### Test 2.3: "run dir_inbox" Command

**SMS:** `run dir_inbox`

**Expected Response:** Directory listing of inbox folder

**Logs Should Contain:**
- bridge: `event_type: "agent_request"`, `name: "dir_inbox"`
- agent: `action: "command_run"`, `command: "dir_inbox"`

---

#### Test 2.4: "write" Command

**SMS:** `write inbox/test.txt :: Hello World`

**Expected Response:** "File created: inbox/test.txt"

**Logs Should Contain:**
- bridge: `event_type: "agent_request"`, `path: "inbox/test.txt"`
- agent: `action: "write"`, `path: "inbox/test.txt"`

**Verify:** File exists at `agent/workspace/inbox/test.txt` with content "Hello World"

---

#### Test 2.5: "read" Command

**Requirements:** File `agent/workspace/inbox/test.txt` exists

**SMS:** `read inbox/test.txt`

**Expected Response:** File content

**Logs Should Contain:**
- bridge: `event_type: "agent_request"`, `path: "inbox/test.txt"`
- agent: `action: "read"`, `path: "inbox/test.txt"`

---

#### Test 2.6: "overwrite" Command

**SMS:** `overwrite inbox/test.txt :: Updated Content`

**Expected Response:** "File updated: inbox/test.txt"

**Verify:** File content changed to "Updated Content"

---

### Authentication Tests

#### Test 3.1: Wrong API Key

**Manual Test:**

```powershell
$headers = @{"X-API-Key" = "wrong-key"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/test.txt"}'
```

**Expected:** 401 Unauthorized error

**Logs Should Contain:**
- agent: `action: "auth_failed"`

---

#### Test 3.2: Missing API Key

**Manual Test:**

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Body '{"path":"inbox/test.txt"}'
```

**Expected:** 401 Unauthorized error

---

#### Test 3.3: Invalid Twilio Signature

**Manual Test:**

Cannot easily test without modifying Twilio request, but verify in logs:

```powershell
Get-Content sms-bridge\logs\bridge.log | Select-String "signature_validated"
# Should see: status: "ok"
```

---

### Path Validation Tests

#### Test 4.1: Valid Path

**Manual Test:**

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "X-API-Key: your-key" `
  -H "Content-Type: application/json" `
  -Body '{"path":"inbox/file.txt"}'
```

**Expected:** Either 404 (file not found) or file content - but NOT 400 (invalid path)

---

#### Test 4.2: Directory Traversal Attack

**Manual Test:**

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "X-API-Key: your-key" `
  -H "Content-Type: application/json" `
  -Body '{"path":"../../etc/passwd"}'
```

**Expected:** 400 Bad Request

**Logs Should Contain:**
- agent: `action: "invalid_path"`

---

#### Test 4.3: Absolute Path Attack

**Manual Test:**

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "X-API-Key: your-key" `
  -H "Content-Type: application/json" `
  -Body '{"path":"C:\\Windows\\System32\\config"}'
```

**Expected:** 400 Bad Request

---

### Sender Allowlist Tests

#### Test 5.1: Allowed Sender

**Requirements:** `ALLOWED_SMS_FROM=+18005551234` in `.env`

**SMS from +18005551234:** `hello`

**Expected:** Reply received

---

#### Test 5.2: Blocked Sender

**Requirements:** `ALLOWED_SMS_FROM=+18005551234` in `.env`

**SMS from +18881234567:** `hello`

**Expected:** No reply (message silently rejected)

**Logs Should Contain:**
- bridge: `event_type: "rejected"`, `reason: "sender_not_allowed"`

---

### AI Mode Tests (If Enabled)

#### Test 6.1: Natural Language Command

**Requirements:** `OPENAI_API_KEY` set in `.env`

**SMS:** `List my inbox`

**Expected Response:** Natural language list of inbox files

**Logs Should Contain:**
- bridge: `event_type: "ai_request"`, `message: "List my inbox"`
- bridge: `event_type: "ai_response"`, `tool: "run_command"`
- bridge: `event_type: "agent_request"`, `name: "dir_inbox"`

---

#### Test 6.2: AI File Creation

**SMS:** `Create a file called notes.txt with hello world`

**Expected Response:** Confirmation that file was created

**Logs Should Contain:**
- bridge: `event_type: "ai_response"`, `tool: "write_file"`

**Verify:** File created at `agent/workspace/inbox/notes.txt`

---

#### Test 6.3: AI Request Failure

**Requirements:** Invalid or expired `OPENAI_API_KEY`

**SMS:** `Any natural language message`

**Expected:** Error response or silence

**Logs Should Contain:**
- bridge: `event_type: "ai_error"`, `reason: "invalid_api_key"`

---

## Performance Tests

### Test 7.1: Latency Check

**Measure:** Time from SMS sent to reply received

**Expected:** < 10 seconds for fixed commands, < 30 seconds with AI

**Test:**
```powershell
# Send SMS and time it
Measure-Command {
  # Send SMS from phone
  # Wait for reply
}
```

---

### Test 7.2: High Volume (Stress Test)

**Warning:** Don't abuse Twilio! Use local testing only.

**Local Test:**

```powershell
# Send 10 test requests rapidly
for ($i = 1; $i -le 10; $i++) {
  curl.exe -X POST http://127.0.0.1:34567/sms `
    -H "Content-Type: application/x-www-form-urlencoded" `
    --data "Body=hello%20$i&From=%2B18005551234" &
}

# Wait for all to complete, then check logs
```

**Expected:** All handle quickly, no errors in logs

---

## Log Verification Tests

### Test 8.1: Request Tracing

Verify that request_id connects bridge and agent logs.

```powershell
# Get a recent request_id from bridge log
$recent = Get-Content sms-bridge\logs\bridge.log -Tail 1 | ConvertFrom-Json
$requestId = $recent.request_id

# Search for it in agent log
Get-Content agent\workspace\logs\agent.log | Select-String $requestId

# Should find matching entries
```

---

### Test 8.2: Event Sequence

Verify all expected events appear in order.

```powershell
# Get recent bridge log
Get-Content sms-bridge\logs\bridge.log -Tail 20 | 
  ConvertFrom-Json | 
  Select-Object event_type

# Expected sequence:
# incoming_sms → [auth checks] → agent_request → agent_response → reply_ready → reply_sent
```

---

## Test Checklist

Run this checklist before considering system "stable":

### Connectivity
- [ ] Agent health endpoint responds
- [ ] Bridge health endpoint responds
- [ ] Funnel status shows running
- [ ] Twilio webhook is reachable

### Fixed Commands
- [ ] `hello` command works
- [ ] `help` command works
- [ ] `run dir_inbox` command works
- [ ] `write` command creates file
- [ ] `read` command reads file
- [ ] `overwrite` command updates file

### Security
- [ ] Wrong API key returns 401
- [ ] Path traversal blocked
- [ ] Non-allowed sender rejected
- [ ] Twilio signature validated

### Logging
- [ ] Bridge logs created and populated
- [ ] Agent logs created and populated
- [ ] Request IDs visible in logs
- [ ] Error events logged

### AI Mode (If Enabled)
- [ ] Natural language message processed
- [ ] AI calls correct tools
- [ ] Response is sensible

---

## Continuous Testing

### Weekly Test Run

```powershell
# 1. Health checks
curl.exe http://127.0.0.1:8787/health
curl.exe http://127.0.0.1:34567/health

# 2. Send quick test SMS
# "hello"

# 3. Check logs
Get-Content sms-bridge\logs\bridge.log -Tail 10 | ConvertFrom-Json | FL
Get-Content agent\workspace\logs\agent.log -Tail 10 | ConvertFrom-Json | FL

# 4. Verify no errors
# Should be all clean
```

---

## Test Report Template

When reporting a bug, include:

```
## Bug Report

**Title:** [Concise description]

**Steps to Reproduce:**
1. Start agent on port 8787
2. Start bridge on port 34567
3. Send SMS: "hello"

**Expected:** Reply within 10 seconds

**Actual:** No reply, or error

**Logs:**
[Relevant bridge.log entries]
[Relevant agent.log entries]

**Environment:**
- Python version: 3.X
- Node version: 18+
- Windows version: 10/11
- cloudflared: [version]
```

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [DEVELOPMENT.md](DEVELOPMENT.md), [LOGGING.md](LOGGING.md), [TROUBLESHOOTING.md](legacy/TROUBLESHOOTING.md)
