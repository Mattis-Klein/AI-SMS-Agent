# Local Agent API Reference

API endpoints and usage for the local FastAPI agent (`agent/agent.py`).

## Base URL

```
http://127.0.0.1:8787
```

All requests require `X-API-Key` header with value matching `AGENT_API_KEY`.

---

## Health Check

### `GET /health`

Check if the agent is running.

**Request:**
```http
GET /health HTTP/1.1
Host: 127.0.0.1:8787
```

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

**Usage:**
```powershell
curl.exe http://127.0.0.1:8787/health
```

---

## File Operations

### `POST /read`

Read a file from the agent workspace.

**Request:**
```http
POST /read HTTP/1.1
Host: 127.0.0.1:8787
Content-Type: application/json
X-API-Key: your-api-key
X-Request-Id: req-123

{
  "path": "inbox/notes.txt"
}
```

**Parameters:**

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `path` | String | Yes | Relative path in workspace |

**Response (200 OK):**
```json
{
  "path": "C:/AI-SMS-Agent/agent/workspace/inbox/notes.txt",
  "content": "File contents here..."
}
```

**Response (404 Not Found):**
```json
{
  "detail": "File not found"
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Invalid path"
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Unauthorized"
}
```

**Usage:**
```powershell
$headers = @{
  "X-API-Key" = "your-api-key"
  "X-Request-Id" = "test-123"
}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/test.txt"}'
```

---

### `POST /write`

Create a new file in the agent workspace.

**Request:**
```http
POST /write HTTP/1.1
Host: 127.0.0.1:8787
Content-Type: application/json
X-API-Key: your-api-key
X-Request-Id: req-124

{
  "path": "inbox/notes.txt",
  "content": "New file content",
  "overwrite": false
}
```

**Parameters:**

| Name | Type | Required | Default | Notes |
|------|------|----------|---------|-------|
| `path` | String | Yes | - | Relative path in workspace |
| `content` | String | Yes | - | File content to write |
| `overwrite` | Boolean | No | false | Replace if exists? |

**Response (200 OK):**
```json
{
  "path": "C:/AI-SMS-Agent/agent/workspace/inbox/notes.txt",
  "status": "created",
  "overwritten": false
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Invalid path"
}
```

**Response (409 Conflict):**
```json
{
  "detail": "File already exists"
}
```

**Usage (Create New):**
```powershell
$headers = @{
  "X-API-Key" = "your-api-key"
  "X-Request-Id" = "test-124"
}
curl.exe -X POST http://127.0.0.1:8787/write `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/new.txt","content":"Hello world"}'
```

**Usage (Overwrite Existing):**
```powershell
curl.exe -X POST http://127.0.0.1:8787/write `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/new.txt","content":"Updated","overwrite":true}'
```

---

## Command Execution

### `POST /run`

Execute a pre-approved command from the allowlist.

**Request:**
```http
POST /run HTTP/1.1
Host: 127.0.0.1:8787
Content-Type: application/json
X-API-Key: your-api-key
X-Request-Id: req-125

{
  "name": "dir_inbox"
}
```

**Parameters:**

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `name` | String | Yes | Command name from allowlist |

**Available Commands:**

| Name | Description |
|------|-------------|
| `dir_inbox` | List `agent/workspace/inbox/` |
| `dir_outbox` | List `agent/workspace/outbox/` |

**Response (200 OK):**
```json
{
  "name": "dir_inbox",
  "stdout": "Volume in drive C is ...\nDirectory of C:\\...\n..."
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Command rejected"
}
```

**Usage:**
```powershell
$headers = @{
  "X-API-Key" = "your-api-key"
  "X-Request-Id" = "test-125"
}
curl.exe -X POST http://127.0.0.1:8787/run `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"name":"dir_inbox"}'
```

---

## Error Handling

### Error Response Format

All errors return JSON with a `detail` message:

```json
{
  "detail": "Description of the error"
}
```

### Common Status Codes

| Code | Meaning | Likely Cause |
|------|---------|--------------|
| 200 | Success | Operation completed |
| 400 | Bad Request | Invalid path or command |
| 401 | Unauthorized | Missing or wrong API key |
| 404 | Not Found | File doesn't exist |
| 409 | Conflict | File already exists |
| 500 | Server Error | Internal agent error |

---

## Request Headers

All requests must include these headers:

### `X-API-Key` (Required)

API key for authentication.

```
X-API-Key: your-api-key-here
```

Must match `AGENT_API_KEY` in `agent/.env`.

---

### `X-Request-Id` (Optional but Recommended)

Unique request identifier for logging.

```
X-Request-Id: unique-id-12345
```

Appears in both bridge and agent logs for tracing.

---

## Content-Type

All API endpoints use JSON:

```
Content-Type: application/json
```

---

## Workspace Paths

All file operations are relative to the workspace root:

```
agent/workspace/
├── inbox/     (can read/write)
└── outbox/    (can read/write)
```

Examples:
- `inbox/notes.txt`
- `outbox/response.txt`
- `inbox/subfolder/file.txt`

**Note:** Paths outside the workspace are rejected with 400 error.

---

## Logging

All API calls are logged to:

```
agent/workspace/logs/agent.log
```

Each entry includes:
- `request_id` - Unique request ID (if sent)
- `action` - Operation (read, write, run)
- `path` - File path
- `time` - ISO 8601 timestamp

---

## Rate Limiting

No rate limiting currently implemented. Plan to add in future versions.

---

## Examples

### Example 1: Read a File

```powershell
$headers = @{"X-API-Key" = "dev-secret-key"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/todo.txt"}'
```

Expected response:
```json
{
  "path": ".../inbox/todo.txt",
  "content": "Buy milk\nBuy eggs\nBuy bread"
}
```

---

### Example 2: Create a File

```powershell
$headers = @{"X-API-Key" = "dev-secret-key"}
curl.exe -X POST http://127.0.0.1:8787/write `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/notes.txt","content":"Important reminder"}'
```

Expected response:
```json
{
  "path": "...",
  "status": "created",
  "overwritten": false
}
```

---

### Example 3: List Directory

```powershell
$headers = @{"X-API-Key" = "dev-secret-key"}
curl.exe -X POST http://127.0.0.1:8787/run `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"name":"dir_inbox"}'
```

Expected response:
```json
{
  "name": "dir_inbox",
  "stdout": "[Directory listing]"
}
```

---

### Example 4: Error - File Not Found

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers @{"X-API-Key" = "dev-secret-key"} `
  -Body '{"path":"inbox/missing.txt"}'
```

Expected response (404):
```json
{
  "detail": "File not found"
}
```

---

### Example 5: Error - Invalid Path

```powershell
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers @{"X-API-Key" = "dev-secret-key"} `
  -Body '{"path":"../../etc/passwd"}'
```

Expected response (400):
```json
{
  "detail": "Invalid path"
}
```

---

## Integration with SMS Bridge

The SMS Bridge (`sms-bridge/sms-server.js`) calls these endpoints when:

1. **Fixed command** (like `read inbox/file.txt`):
   - Calls `/read`, `/write`, or `/run`
   - Sends result back as SMS

2. **AI mode** (natural language):
   - AI model plans which endpoint to call
   - Bridge makes the call
   - AI interprets and formats response

---

## Advanced Usage

### Batch Operations

The API doesn't support batch operations yet. Use multiple requests:

```powershell
# Request 1
curl.exe -X POST http://127.0.0.1:8787/read ... 

# Request 2
curl.exe -X POST http://127.0.0.1:8787/write ...
```

---

### Large Files

Reading files larger than 1 MB may be slow. No hard limit, but not recommended for SMS.

---

## Future API Enhancements

Planned features (not yet implemented):

- List directory endpoint
- Delete file endpoint
- Rename file endpoint
- More commands in allowlist
- Rate limiting
- Batching API

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [Commands Reference](COMMANDS.md), [Logging Guide](LOGGING.md)
