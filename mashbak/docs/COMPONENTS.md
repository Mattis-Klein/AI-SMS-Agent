# Components - Technical Details

Deep dive into system components and architecture.

---

## Overview

The system has 3 main components:

1. **SMS Bridge** (Node.js) - HTTP endpoint, Twilio handler, AI router
2. **Local Agent** (Python) - File/command operations, REST API
3. **Public Tunnel** (Cloudflare Tunnel) - Makes bridge accessible to Twilio

---

## SMS Bridge Component

**File:** `sms-bridge/sms-server.js`  
**Language:** Node.js (JavaScript)  
**Framework:** Express  
**Port:** 34567 (default)  

### Responsibilities

1. **Receive Twilio webhooks** at `/sms` endpoint
2. **Validate request signature** using `TWILIO_AUTH_TOKEN`
3. **Apply sender access control** (owner forward, special responses, denied senders)
4. **Route request** to fixed command handler or AI
5. **Call agent API** to execute operations
6. **Format TwiML response** back to Twilio
7. **Notify owner on access requests** when approved request numbers send `@mashbak`
8. **Log all events** to `logs/bridge.log`

### Key Flows

#### Fixed Command Flow

```
SMS: "read inbox/file.txt"
  ↓
Bridge receives and parses
  ↓
Checks: is "read" a fixed command? Yes
  ↓
Calls Node.js "read_file" handler
  ↓
Handler constructs agent API request
  ↓
Makes POST to http://127.0.0.1:8787/read
  ↓
Agent returns file content
  ↓
Handler formats response (max 160 chars)
  ↓
Bridge returns TwiML to Twilio
  ↓
SMS reply sent
```

#### AI Command Flow

```
SMS: "List my inbox"
  ↓
Bridge receives and parses
  ↓
Checks: is "list my inbox" a fixed command? No
  ↓
Is AI enabled (OPENAI_API_KEY set)? Yes
  ↓
Calls OpenAI API with message + tool definitions
  ↓
OpenAI returns tool to use: run_command("dir_inbox")
  ↓
Bridge calls agent: POST /run with name="dir_inbox"
  ↓
Agent returns directory listing
  ↓
Bridge sends listing back to OpenAI
  ↓
OpenAI formats natural language response
  ↓
Bridge returns TwiML to Twilio
  ↓
SMS reply sent
```

### Configuration Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| AGENT_URL | Yes | Where to find local agent |
| AGENT_API_KEY | Yes | Authentication to agent |
| BRIDGE_PORT | Yes | Port to listen on |
| PUBLIC_BASE_URL | Yes | Base URL for Twilio |
| TWILIO_AUTH_TOKEN | No | Validate webhook signature |
| TWILIO_ACCOUNT_SID | No | Owner notification SMS |
| TWILIO_FROM_NUMBER | No | Owner notification sender |
| OPENAI_API_KEY | No | Enable AI mode |
| OPENAI_MODEL | No | Which AI model to use |

### Key Functions

#### `handleSMS()` - Main Request Handler

```javascript
app.post("/sms", (req, res) => {
  // 1. Validate Twilio signature
  // 2. Check sender
  // 3. Extract message
  // 4. Detect command type
  // 5. Route to handler
  // 6. Return TwiML
})
```

#### `handleFixed Command()` - Direct Command Handler

```javascript
// For "hello", "help", "read", "write", "overwrite", "run"
// Converts SMS command to agent API call
```

#### `handleAI()` - AI Handler

```javascript
// For natural language
// Calls OpenAI
// Interprets tool response
// Makes agent API calls
// Formats response
```

### Logging

Each request logs:
- `timestamp` - When request arrived
- `from` - Sender phone number  
- `body` - SMS message content
- `event_type` - What happened (incoming_sms, ai_request, agent_request, etc.)
- `request_id` - Unique ID for tracing
- `status` - Result (success, error, rejected)

---

## Local Agent Component

**File:** `agent/agent.py`  
**Language:** Python  
**Framework:** FastAPI  
**Port:** 8787 (default)  

### Responsibilities

1. **Receive REST requests** from bridge
2. **Authenticate requests** using `X-API-Key` header
3. **Validate file paths** (no directory traversal)
4. **Read/write files** in workspace
5. **Execute allowed commands** from allowlist
6. **Return results** as JSON
7. **Log all operations** to `logs/agent.log`

### Endpoints

#### `/health` (GET)

```http
GET /health
Response: {"status": "ok"}
```

Quick liveness check.

---

#### `/read` (POST)

```http
POST /read
Headers: X-API-Key: key, X-Request-Id: id
Body: {"path": "inbox/file.txt"}

Response: {"path": "...", "content": "..."}
Error: {"detail": "File not found"}
```

Reads a file from workspace.

---

#### `/write` (POST)

```http
POST /write
Headers: X-API-Key: key, X-Request-Id: id
Body: {"path": "inbox/new.txt", "content": "text", "overwrite": false}

Response: {"path": "...", "status": "created"}
Error: {"detail": "File already exists"}
```

Creates a new file (or overwrites if flagged).

---

#### `/run` (POST)

```http
POST /run
Headers: X-API-Key: key, X-Request-Id: id
Body: {"name": "dir_inbox"}

Response: {"name": "dir_inbox", "stdout": "..."}
Error: {"detail": "Command rejected"}
```

Executes an allowed command.

---

### Path Validation

**Rule:** All paths must be within `agent/workspace/`.

**Implementation:**

```python
def safe_path(user_path: str) -> Path:
    p = (WORKSPACE / user_path).resolve()
    
    # Check: Is p inside WORKSPACE?
    if WORKSPACE not in p.parents and p != WORKSPACE:
        raise HTTPException(400, "Invalid path")
    
    return p
```

**Examples:**
- ✅ `inbox/file.txt` → OK (inside workspace)
- ✅ `inbox/sub/file.txt` → OK (inside workspace)
- ❌ `../../../etc/passwd` → REJECTED (outside workspace)
- ❌ `/etc/passwd` → REJECTED (absolute path)
- ❌ `C:\Windows\System32` → REJECTED (outside workspace)

---

### Command Allowlist

Only these commands are executable:

```python
ALLOWLIST = {
    "dir_inbox": ["cmd", "/c", "dir", str(WORKSPACE / "inbox")],
    "dir_outbox": ["cmd", "/c", "dir", str(WORKSPACE / "outbox")],
}
```

**To add a command:**

```python
ALLOWLIST = {
    ...
    "custom_command": ["cmd", "/c", "desired", "command"],
}
```

⚠️ Only pre-approved commands can run. No arbitrary shell access.

---

### Configuration Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| AGENT_API_KEY | (required) | Auth key |
| AGENT_WORKSPACE | `agent/workspace` | Data directory |

---

### Logging

Each operation logs:
- `request_id` - Traceability
- `action` - What was done (read, write, run)
- `path` - File path (if applicable)
- `status` - Success or error
- `time` - ISO 8601 timestamp

---

## Cloudflare Tunnel Component

**Service:** Cloudflare Tunnel (`cloudflared`)  
**Port Tunneled:** 34567 (local)  
**Public URL:** `https://YOUR-ID.trycloudflare.com`  

### Responsibilities

1. **Create encrypted tunnel** from local port 34567 to internet
2. **Provide public HTTPS URL** for Twilio to call
3. **Terminate HTTPS** at Cloudflare edge
4. **Forward requests** to local bridge on localhost

### Configuration

Started from terminal. The URL must be copied into `mashbak/.env.master` as `PUBLIC_BASE_URL`:

```powershell
cloudflared tunnel --url http://localhost:34567
```

This:
- Creates a temporary HTTPS endpoint
- Forwards traffic to local port 34567
- Prints the public URL to the terminal

### Public URL

Get it from terminal output when starting `cloudflared`.

```powershell
Example:
```
https://abc123.trycloudflare.com
```

---

## Data Flow Diagram

```
[Your Phone SMS]
        ↓
    [Twilio]
        ↓
[Cloudflare Tunnel]
        ↓
[SMS Bridge: sms-server.js]
        ├─→ Signature validation
        ├─→ Sender allowlisting
        ├─→ Command detection
        ├─→ [Fixed Command]
        │    └─→ Convert to API call
        │
        └─→ [AI Mode]
             ├─→ Call OpenAI
             ├─→ OpenAI decides tool
             └─→ Make API call
        ↓
[Local Agent: agent.py]
        ├─→ Auth check
        ├─→ Path validation
        ├─→ Execute (read/write/run)
        └─→ Return JSON result
        ↓
[SMS Bridge]
        ├─→ Format response
        ├─→ Truncate to 160 chars
        └─→ Send TwiML to Twilio
        ↓
    [Twilio]
        ↓
[Your Phone SMS]
```

---

## Logging Architecture

### Bridge Logs

Format: JSON, one object per line

```json
{
  "timestamp": "2025-03-08T10:35:45.123Z",
  "request_id": "abc-123",
  "event_type": "incoming_sms",
  "from": "+18005551234",
  "body": "hello",
  ...
}
```

Rotation: Max 1 MB (configurable), then rolls to `.log.1`

---

### Agent Logs

Format: JSON, one object per line

```json
{
  "request_id": "abc-123",
  "time": "2025-03-08T10:35:45",
  "action": "read",
  "path": "inbox/file.txt",
  "status": "success"
}
```

No automatic rotation (can grow large).

---

## Error Handling

### Bridge Error Categories

| Error | Cause | Response |
|-------|-------|----------|
| invalid_twilio_signature | Token mismatch | 403 Forbidden |
| sender_not_allowed | Allowlist check | 403 Forbidden |
| agent_unavailable | Can't reach agent | 500 Internal |
| ai_error | OpenAI API failed | 500 Internal |
| malformed_request | Bad JSON/params | 400 Bad Request |

### Agent Error Categories

| Error | HTTP Code | Cause |
|-------|-----------|-------|
| Unauthorized | 401 | Wrong API key |
| Invalid path | 400 | Path outside workspace |
| File not found | 404 | Reading non-existent file |
| File exists | 409 | Writing to existing file |
| Command rejected | 400 | Command not in allowlist |

---

## Performance Characteristics

### Engine Latency

| Operation | Latency | Notes |
|-----------|---------|-------|
| Read file | ~10-50 ms | File I/O |
| Write file | ~10-50 ms | File I/O |
| Run command | ~100-500 ms | Command startup |
| AI call | 1-3 seconds | Network to OpenAI |

### Throughput

- **Without AI:** ~10-20 SMS/sec per bridge
- **With AI:** ~1-2 SMS/sec per bridge
- **Limited by:** OpenAI rate limits, Twilio limits

### Scalability

Current system is single-threaded and single-server:
- Not suitable for high throughput
- Good for personal/small use
- Would need major redesign for enterprise

---

## Security Architecture

### Authentication Flow

1. Bridge receives SMS from Twilio
2. Bridge calls agent with `X-API-Key` header
3. Agent checks: Does key match `AGENT_API_KEY`?
4. If no match: Return 401, log auth_failed
5. If match: Continue to authorization

### Authorization Flow

After auth, agent checks:
1. Is requested path within workspace?
2. Is requested command in allowlist?
3. If not: Return 400, log invalid_path or command_rejected
4. If yes: Proceed with operation

### Signature Validation Flow

1. Bridge receives Twilio webhook
2. Bridge reconstructs signed content
3. Uses `TWILIO_AUTH_TOKEN` to validate
4. Twilio signature matches? Continue
5. Otherwise: Reject 403, log invalid_twilio_signature

---

## Integration Points

### Twilio Integration

- **Endpoint:** `/sms` (POST)
- **Authentication:** Signature validation
- **Response Format:** TwiML XML
- **Rate Limit:** Twilio limits (usually OK for SMS)

### OpenAI Integration

- **API:** `https://api.openai.com/v1/chat/completions`
- **Authentication:** Bearer token (OPENAI_API_KEY)
- **Model:** Configurable (gpt-4.1-mini, gpt-4, gpt-3.5-turbo)
- **Tool Calling:** Using function calling API

### Cloudflare Integration

- **Tunnel:** `cloudflared tunnel --url http://localhost:34567`
- **URL type:** `trycloudflare.com` quick tunnel URL
- **Encryption:** HTTPS on public edge
- **Forwarding:** Public URL to local bridge port

---

## Extension Points

### Adding New Commands

In `agent/agent.py`:

```python
ALLOWLIST = {
    "dir_inbox": [...],
    "dir_outbox": [...],
    "custom_cmd": ["cmd", "/c", "your-command"],  # Add here
}
```

### Adding New File Endpoints

In `agent/agent.py`:

```python
@app.post("/custom")
def custom_handler(req: CustomRequest, x_api_key=Header(None)):
    auth(x_api_key)
    # your logic here
```

### Adding New Bridge Features

In `sms-bridge/sms-server.js`:

```javascript
// In handleSMS():
if (command === "new_feature") {
    return await handleNewFeature(body);
}
```

---

## Testing Components

### Test Bridge Locally

```powershell
curl.exe -X POST http://127.0.0.1:34567/sms \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "Body=hello&From=%2B18005551234"
```

### Test Agent Locally

```powershell
curl.exe -X POST http://127.0.0.1:8787/read \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"path":"inbox/test.txt"}'
```

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [API.md](API.md), [ARCHITECTURE.md](legacy/ARCHITECTURE.md), [DEVELOPMENT.md](DEVELOPMENT.md)
