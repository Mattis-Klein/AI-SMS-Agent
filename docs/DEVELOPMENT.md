# Development Guide

Contributing and extending the project.

---

## Project Status

**Current Version:** 1.0 (Functional but Not Production-Ready)

**What Works:**
- SMS receiving and routing
- Fixed command execution
- File read/write operations
- AI natural language mode (when enabled)
- Logging and debugging

**What's Missing:**
- Rate limiting
- Request approval workflows
- Rate-limited API responses
- Production error handling
- Multi-user support
- Automatic failover

---

## Development Setup

### Prerequisites

- VS Code
- Python 3.9+
- Node.js 18+
- Git (optional, for cloning)
- Cloudflare Tunnel + Twilio (for testing with live SMS)

### Local Setup

```powershell
# 1. Clone or download repository
cd C:\AI-SMS-Agent

# 2. Setup Python
cd agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt  # If available

# 3. Setup Node
cd ..\sms-bridge
npm install

# 4. Create .env files (copy from .env.example)
copy .env.example .env
copy ..\agent\.env.example ..\agent\.env

# 5. Edit .env files with real configuration
```

---

## Project Structure for Development

```
C:\AI-SMS-Agent\
├── agent/
│   ├── agent.py              # Main FastAPI app
│   ├── .env                  # Config
│   ├── workspace/            # Data directory
│   └── .venv/                # Python dependencies
│
├── sms-bridge/
│   ├── sms-server.js         # Main Express app
│   ├── .env                  # Config
│   ├── logs/                 # Runtime logs
│   └── node_modules/         # Node dependencies
│
└── docs/                     # Documentation (this folder)
```

### Local Session Notes

Use [local-memory-notes/](../local-memory-notes) for personal markdown notes and temporary operational context.

- This folder is intentionally gitignored.
- Keep local troubleshooting history there instead of committed docs.
- Do not store secrets in committed markdown files.

---

## Code Style Guidelines

### Python (`agent/agent.py`)

**Style:** PEP 8

```python
# Good
def safe_path(user_path: str) -> Path:
    """Validate and resolve file path within workspace."""
    p = (WORKSPACE / user_path).resolve()
    if WORKSPACE not in p.parents and p != WORKSPACE:
        raise HTTPException(status_code=400, detail="Invalid path")
    return p

# Bad
def safe_path(user_path):
    p = (WORKSPACE / user_path).resolve()
    if WORKSPACE not in p.parents and p != WORKSPACE:
        raise HTTPException(400, "Invalid path")
    return p
```

**Conventions:**
- Use type hints
- Name functions with `_` suffixes for private functions
- Use descriptive variable names
- Add docstrings to public functions
- Keep functions under 50 lines when possible

---

### JavaScript/Node (`sms-bridge/sms-server.js`)

**Style:** Airbnb/ESLint compatible

```javascript
// Good
function handleSMS(body, from) {
  const command = body.trim().toLowerCase();
  
  if (this.isFixedCommand(command)) {
    return this.handleFixedCommand(command);
  }
  
  return this.handleAI(body);
}

// Bad
function handleSMS(body,from){
  var cmd = body.trim();
  if(isFixedCommand(cmd)) return handleFixed(cmd);
  return handleAI(body);
}
```

**Conventions:**
- Use `const` over `let` over `var`
- Name functions with camelCase
- Use async/await (not callbacks)
- Keep functions under 30 lines when possible
- Add JSDoc comments

---

## Code Organization

### Adding a New SMS Command

**Example: Add "delete" command**

#### Step 1: Bridge Handler

In `sms-bridge/sms-server.js`, add handler:

```javascript
async function handleDelete(path) {
  try {
    const response = await fetch(`${AGENT_URL}/delete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": AGENT_API_KEY,
        "X-Request-Id": generateRequestId(),
      },
      body: JSON.stringify({ path }),
    });
    
    const result = await response.json();
    return {
      status: response.status,
      message: `File deleted: ${path}`,
    };
  } catch (err) {
    logEvent({
      event_type: "agent_error",
      action: "delete",
      error: err.message,
    });
    throw err;
  }
}
```

#### Step 2: Command Router

In `handleSMS()`, add pattern match:

```javascript
if (body.startsWith("delete ")) {
  const path = body.substring(7).trim();
  const result = await handleDelete(path);
  return buildResponse(result.message);
}
```

#### Step 3: Agent Endpoint

In `agent/agent.py`, add endpoint:

```python
@app.post("/delete")
def delete_file(req: DeleteRequest, x_api_key: str = Header(None)):
    auth(x_api_key)
    p = safe_path(req.path)
    
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    p.unlink()  # Delete file
    log_event({"action": "delete", "path": str(p)})
    return {"status": "deleted"}
```

#### Step 4: Test

```powershell
# Local test
curl.exe -X POST http://127.0.0.1:8787/delete \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"path":"inbox/temp.txt"}'

# SMS test
# Send: delete inbox/temp.txt
```

#### Step 5: Document

Update [COMMANDS.md](COMMANDS.md):

```markdown
### `delete <path>`

Delete a file from the workspace.

**Usage:**
delete inbox/file.txt
```

---

## Making Changes

### Before You Start

1. **Read the architecture** → [ARCHITECTURE.md](legacy/ARCHITECTURE.md)
2. **Read the code** → Both `agent.py` and `sms-server.js`
3. **Run tests locally** → See [TESTING.md](TESTING.md)
4. **Check existing issues** → GitHub (if available)

---

### Development Workflow

```
1. Create feature branch (recommended)
   git checkout -b feature/my-feature

2. Make changes (small, focused commits)
   - Change agent.py
   - Change sms-server.js
   - Update tests
   - Update docs

3. Test locally
   npm run check  # Node syntax
   python -m py_compile agent.py  # Python syntax
   Manual testing with SMS

4. Verify no breaking changes
   - All health endpoints work
   - All fixed commands work
   - Logs are clean

5. Commit with clear message
   git commit -m "feat: add delete command"

6. Create pull request (if collaborative)
   - Describe changes
   - Reference related issues
   - Request review
```

---

### Testing Locally

**Never commit untested code.**

```powershell
# Start services
cd agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787

# In other terminal
cd sms-bridge
npm start

# Now test your changes
# Send SMS, check logs, verify behavior
```

---

## Common Development Tasks

### Add a Fixed SMS Command

Process (see example above):
1. Add handler in bridge
2. Add pattern match in `handleSMS()`
3. Add endpoint in agent
4. Test locally
5. Update docs

---

### Add an Agent API Endpoint

Example: Add `/list` endpoint

```python
class ListRequest(BaseModel):
    path: str

@app.post("/list")
def list_files(req: ListRequest, x_api_key: str = Header(None)):
    auth(x_api_key)
    p = safe_path(req.path)
    
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")
    
    files = [f.name for f in p.iterdir()]
    log_event({"action": "list", "path": str(p), "count": len(files)})
    return {"path": str(p), "files": files}
```

Then call from bridge when needed.

---

### Configure Debugging

#### Python Debugging

```python
# Add print statements for quick debug
print(f"DEBUG: path={p}, exists={p.exists()}")

# Or use logging module
import logging
logger = logging.getLogger(__name__)
logger.debug(f"File read: {p}")
```

#### Node Debugging

```javascript
// Add console logs
console.log(`DEBUG: body=${body}, command=${command}`);

// Or use debug module (recommended)
const debug = require("debug")("bridge:sms");
debug(`Received from ${from}: ${body}`);
```

Run with:
```powershell
# For Node
$env:DEBUG="bridge:*"
npm start
```

---

### Performance Optimization

#### Agent (Python)

```python
# Before: Slow (reads file twice)
content = p.read_text()
if len(content) > 1000000:
    content = content[:1000000]

# After: Faster (reads once)
content = p.read_text()[:1000000]
```

#### Bridge (Node)

```javascript
// Before: Sequential
const result1 = await handleCommand1();
const result2 = await handleCommand2();

// After: Parallel (if independent)
const [result1, result2] = await Promise.all([
  handleCommand1(),
  handleCommand2(),
]);
```

---

## Testing Your Changes

See [TESTING.md](TESTING.md) for comprehensive testing guide.

Quick checklist:

- [ ] Code compiles (no syntax errors)
- [ ] Local endpoints respond
- [ ] Test SMS received and processed
- [ ] Logs show correct events
- [ ] No breaking changes
- [ ] Security checks pass (path validation, auth)

---

## Version Control

### `.gitignore`

Protect sensitive data:

```
.env
.env.local
.venv/
node_modules/
*.log
workspace/
logs/
.DS_Store
```

**Before committing:**

```powershell
git status
# Make sure .env files are NOT listed

# If you accidentally added them:
git rm --cached .env
git commit -m "Remove .env from tracking"
```

---

### Commit Messages

Use clear, descriptive messages:

```
Good:
- "feat: add file delete command"
- "fix: validate paths before processing"
- "docs: update SMS commands reference"
- "test: add agent API tests"

Bad:
- "fix stuff"
- "update"
- "wip"
- "asdf"
```

---

## Deployment Checklist

Before deploying to "production" (personal use):

- [ ] All tests pass
- [ ] Logs are clean (no errors)
- [ ] `.env` files updated with real credentials
- [ ] Twilio webhook URL is correct
- [ ] Cloudflare tunnel is running
- [ ] Security review done (see Security Hardening)
- [ ] Documentation updated
- [ ] Backup created

---

## Known Limitations & Future Work

### Current Limitations

- Single-threaded (not suitable for high throughput)
- No rate limiting built-in
- No request approval workflows
- No multi-user support
- No OAuth integrations
- Logs grow unbounded (no auto-rotation for agent)

### Future Enhancements

1. **Add rate limiting** - Prevent abuse
2. **Add approval workflow** - For risky actions
3. **Add user management** - Multi-user support
4. **Add OAuth** - Google, Amazon interactions
5. **Add database** - For persistent state
6. **Add web UI** - For non-SMS management
7. **Add monitoring** - Real-time alerts
8. **Add load balancing** - For production scale

---

## Getting Help

### When You're Stuck

1. **Check logs first** → Answer is almost always there
2. **Read the docs** → [docs/INDEX.md](INDEX.md)
3. **Search existing code** → Similar patterns elsewhere?
4. **Ask in an issue** → If available on GitHub
5. **Debug locally** → Reproduce with print statements

### Debug Workflow

```powershell
# 1. See what's happening
Get-Content sms-bridge\logs\bridge.log -Tail 20 | ConvertFrom-Json | FL

# 2. Identify the request_id
# (shown in logs)

# 3. Trace through agent logs
Get-Content agent\workspace\logs\agent.log | 
  Select-String "request-id-here"

# 4. Understand the flow
# Is request validating? 
# Is bridge calling agent?
# Is agent responding?
# Where does it fail?

# 5. Fix the issue
# Update code, test, verify
```

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [TESTING.md](TESTING.md), [COMPONENTS.md](COMPONENTS.md), [BEST-PRACTICES.md](BEST-PRACTICES.md)
