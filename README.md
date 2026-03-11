# AI-SMS-Agent

This repository now supports multiple assistant applications.

## Assistants

- **Mashbak** (`mashbak/`): desktop-first Windows assistant with optional SMS access.
- **Bucherim** (`bucherim/`): SMS-only visual/chat assistant (coming soon).

## Repository Layout

```
AI-SMS-Agent/
  mashbak/
    agent/
    desktop_app/
    sms-bridge/
    scripts/
    docs/
    workspace/
  bucherim/
    agent/
    sms-bridge/
    config/
    workspace/
```

## Multi-Assistant Routing (Preparation)

Incoming SMS messages will eventually be routed by sender/number rules:

```
incoming SMS
     ↓
router
     ├── mashbak
     └── bucherim
```

## Run Mashbak

All current production functionality remains in `mashbak/`.

### Start Agent

```powershell
cd mashbak/agent
python -m uvicorn agent:app --host 127.0.0.1 --port 8787
```

### Start SMS Bridge

```powershell
cd mashbak/sms-bridge
npm start
```

### Start Desktop App

```powershell
python mashbak/desktop_app/main.py
```

### Build Desktop EXE

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Output:

- `mashbak/dist/Mashbak.exe`

## Documentation

- Mashbak docs: `mashbak/docs/`
- Legacy Mashbak docs: `mashbak/docs/legacy/`

## Notes

- The Bucherim folder is scaffolding only right now.
- Existing Mashbak behavior is preserved, just moved under `mashbak/`.

### Via Local Desktop App

1. Start `python desktop_app/main.py`
2. Type a request such as `check my inbox` or `show cpu usage`
3. Review trace details, activity, logs, and service status from the right panel

Local app requests execute locally through shared runtime logic and are never routed to Twilio replies.

### Via SMS

```
📱 You:    "check my inbox"
📲 Agent:  "Directory listing: meeting.txt budget.doc notes.txt"

📱 You:    "system info"
📲 Agent:  "OS Name: Windows 11, Memory: 16 GB, Type: PC"

📱 You:    "cpu usage"
📲 Agent:  "CPU Usage: 23.5%"

📱 You:    "list documents"
📲 Agent:  "files: resume.pdf report.docx plans.xlsx"
```

### Via Direct API

```bash
# List files in a specific path
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "list_files",
    "args": {"path": "C:\\Users\\Documents"}
  }'
```

## 🔧 Configuration

### agent/config.json

```json
{
  "allowed_directories": [
    "C:\\Users\\owner\\Documents",
    "C:\\Temp"
  ],
  "allowed_tools": null,
  "logging": {
    "max_log_size_bytes": 5000000,
    "log_retention_days": 30,
    "log_level": "info"
  },
  "security": {
    "max_file_size_bytes": 10485760,
    "blocked_extensions": [".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js"],
    "require_sender_validation": true
  }
}
```

**Fields:**

- `allowed_directories`: Paths that tools can access (file path tools)
- `allowed_tools`: If set, only these tools are available (null = all allowed)
- `logging.log_level`: "debug", "info", or "error"
- `security.blocked_extensions`: File extensions that cannot be accessed

## 📊 Logging & Monitoring

All events logged as JSON lines:

```json
{"time": "2026-03-09T14:30:15", "request_id": "abc-123", "event_type": "request", "sender": "+15551234567", "raw_message": "check inbox"}
{"time": "2026-03-09T14:30:15", "request_id": "abc-123", "event_type": "tool_execution", "tool_name": "dir_inbox", "success": true}
{"time": "2026-03-09T14:30:16", "request_id": "abc-123", "event_type": "response", "status": "success"}
```

**Log Query Examples:**

```bash
# All requests from a sender
grep '+15551234567' agent/workspace/logs/agent.log

# Tool execution errors
grep 'event_type.*error' agent/workspace/logs/agent.log

# Specific request trace (all events with same ID)
grep 'request_id=abc-123' agent/workspace/logs/agent.log
```

## 🛠️ Adding New Tools

1. Create tool file in `agent/tools/builtin/your_tool.py`
2. Implement Tool interface (validate_args, execute)
3. Register in `agent/tools/builtin/__init__.py`
4. Add interpretation patterns in `agent/interpreter.py`
5. Document in TOOLS.md

## 📋 API + Local Console Summary

- `/execute` runs a specific tool with structured args.
- `/execute-nl` runs natural-language requests through interpreter + dispatcher.
- `desktop_app/main.py` starts local agent service automatically and sends local chat requests to it.
- Both API and local desktop include step-by-step `trace` output in responses.

## 📁 Project Structure

```
Mashbak/
├── agent/                          # Python FastAPI agent + shared runtime
│   ├── agent.py                    # FastAPI API layer
│   ├── runtime.py                  # Shared runtime (used by API + desktop)
│   ├── config.json                 # Tool/config allowlists and security settings
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Environment template
│   ├── dispatcher.py               # Shared request execution pipeline
│   ├── interpreter.py              # Natural language intent mapping
│   ├── logger.py                   # Structured JSON logging
│   └── tools/                      # Tool registry and built-in tools
│   └── workspace/                  # Agent workspace for file operations
│       ├── inbox/                  # Incoming files
│       ├── outbox/                 # Outgoing files
│       └── logs/                   # Agent logs (JSON format)
├── desktop_app/                    # Local desktop transport (no SMS replies)
│   ├── main.py                     # Desktop app entry point
│   ├── agent_service.py            # Embedded FastAPI agent process manager
│   ├── agent_client.py             # Local API client for desktop chat
│   ├── ui.py                       # Desktop UI controller
│   └── widgets.py                  # Reusable Tkinter UI helpers
├── sms-bridge/                     # Node.js SMS bridge
│   ├── sms-server.js               # Bridge server
│   ├── package.json                # Node dependencies
│   ├── .env.example                # Environment template
│   └── logs/                       # Bridge logs (JSON format)
├── scripts/                        # PowerShell launchers
│   ├── dev-start.ps1               # Launch everything (recommended)
│   ├── build-app.ps1               # Build Windows desktop .exe via PyInstaller
│   ├── start-agent.ps1             # Launch agent only
│   ├── start-bridge.ps1            # Launch bridge only
│   └── start-cloudflare.ps1        # Launch tunnel only
└── docs/                           # Complete documentation
```

### Tool and Security Configuration (`agent/config.json`)

Tool and security policy are configured in `agent/config.json`.

- `allowed_directories`: explicit safe directories for path-based tools.
- `allowed_tools`: optional tool allowlist (`null` means all registered tools).
- `security`: file/extension constraints, sender validation, and `tool_timeout_seconds`.

### Environment Configuration

Create `.env` files from templates before first run:

**`agent/.env`:**
```
AGENT_API_KEY=your-secret-key-here
AGENT_WORKSPACE=C:\AI-SMS-Agent\agent\workspace
```

**`sms-bridge/.env`:**
```
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=your-secret-key-here
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://your-tunnel-url.trycloudflare.com
TWILIO_AUTH_TOKEN=your-twilio-token
ALLOWED_SMS_FROM=+15551234567
OPENAI_API_KEY=sk-your-key-here
```

⚠️ **Security**: Never commit `.env` files. Only `.env.example` templates are tracked in git.

## 📊 Logging

All actions are logged in structured JSON format:

- **Agent logs**: `agent/workspace/logs/agent.log`
- **Bridge logs**: `sms-bridge/logs/bridge.log`

Each log entry includes:
- `time`: ISO timestamp
- `request_id`: Unique request ID
- `sender`: Phone number (when applicable)
- `action`: What happened
- `status`: success/error/blocked

Example log entry:
```json
{"time":"2026-03-09T14:30:15","request_id":"abc-123","sender":"+15551234567","action":"command_complete","name":"system_info","return_code":0,"status":"success"}
```

## 🚀 Usage Examples

**Natural Language:**
```
SMS: check my CPU usage
Response: CPU usage is at 23.5%

SMS: what files are in my inbox
Response: [directory listing]
```

## ➕ Adding New Tools

To extend behavior safely, add a new tool module under `agent/tools/builtin/`, register it in `agent/tools/builtin/__init__.py`, and add optional NL patterns in `agent/interpreter.py`.

## 🐙 Pushing to GitHub

The repository is already initialized with git and ready to push:

```powershell
# Add GitHub remote (replace with your repo URL)
git remote add origin https://github.com/mattis-Klein/Mashbak.git

# Push to GitHub
git branch -M main
git push -u origin main
```

The `.gitignore` is configured to exclude:
- Environment files (`.env`)
- Virtual environments (`.venv`, `node_modules`)
- Log files (`logs/`)
- Runtime artifacts (`__pycache__`)

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

- [INDEX.md](docs/INDEX.md) - Master documentation index
- [QUICK-START.md](docs/QUICK-START.md) - Get running in 5 minutes
- [INSTALLATION.md](docs/INSTALLATION.md) - Complete setup guide
- [COMMANDS.md](docs/COMMANDS.md) - SMS command reference
- [SECURITY-HARDENING.md](docs/SECURITY-HARDENING.md) - Advanced security
- [API.md](docs/API.md) - Agent API reference

## 🛠️ Alternative: Manual Startup

If you prefer to launch components individually, use these helper scripts:

```powershell
.\scripts\start-agent.ps1
.\scripts\start-bridge.ps1
.\scripts\start-cloudflare.ps1
```

Or run the manual commands:

```powershell
# Agent
cd agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn agent:app --host 127.0.0.1 --port 8787

# Bridge
cd ..\sms-bridge
npm install
npm start

# Cloudflare tunnel
cloudflared tunnel --url http://localhost:34567
```

## Notes

- Bridge start command is defined in `sms-bridge/package.json` as `start: node sms-server.js`.
- Runtime artifacts such as `node_modules`, `__pycache__`, logs, and `.venv` are hidden from normal VS Code Explorer view.
- See `docs/INDEX.md` for full documentation.
