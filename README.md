# AI-SMS-Agent

**Control your computer from SMS using a tool-based AI agent.**

AI-SMS-Agent is a secure, local AI system that interprets SMS messages, maps them to allowed tools, executes them safely, and returns results via text. It features a clean tool registry architecture, natural language interpretation, and structured logging for full observability and audit trails.

## ✨ What's New in v2.0

- **Tool-Based Architecture**: Clean, modular system where each capability is a defined tool
- **Natural Language Support**: SMS messages like "check my inbox" or "show CPU" are automatically mapped to tools
- **Tool Registry**: Extensible system for adding new tools
- **Structured Logging**: Full request lifecycle tracking with JSON logs
- **Improved Dispatcher**: Smart routing through tool system with input validation
- **Cleaner API**: Separate `/execute` and `/execute-nl` endpoints

## 🎯 Core Concept: Tools

Everything the agent does is expressed as a **tool**:

```
Tool = { name, description, input schema, validation, execution }

Examples:
  - dir_inbox: List files in inbox folder
  - cpu_usage: Check current CPU usage
  - list_files: List files in a directory (requires path argument)
  - system_info: Get OS name, version, memory info
  - current_time: Get current date/time
```

When you send an SMS:

```
"Check my inbox"
  ↓
[Natural Language Interpreter]
  ↓
Tool: dir_inbox
  ↓
[Validate & Execute]
  ↓
"Directory listing: file1.txt, file2.txt"
```

## 🏗️ Architecture

```
SMS Request
    ↓
📱 SMS Bridge (Node.js)
  - Validates Twilio signature
  - Checks sender allowlist
    ↓
🤖 FastAPI Agent (Python)
  - POST /execute-nl (natural language)
  - POST /execute (direct tool)
    ↓
📋 Dispatcher
  - Logs request
  - Routes to interpreter or tool
    ↓
🔍 Interpreter (for natural language)
  - Pattern matches message
  - Extracts arguments
  - Maps to tool name
    ↓
🛠️ Tool Registry
  - Holds all available tools
  - Validates inputs
  - Executes selected tool
    ↓
📝 Structured Logger
  - Records all events as JSON
  - Tracks full request lifecycle
  - Enables audit trail
    ↓
📞 Response sent via SMS
```

**Full flow documentation**: See [ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 🔐 Security Model

### Three Layers of Validation

1. **Bridge Level**
   - Twilio signature validation (prevents spoofing)
   - Sender allowlist (only known numbers)

2. **Agent Level**
   - API key authentication
   - Tool allowlist (optional: restrict to subset of tools)
   - Input schema validation

3. **Tool Level**
   - Path validation (files only in allowed directories)
   - Timeout enforcement (max 30 seconds per execution)
   - Error encapsulation (failures are safe and logged)

### What's NOT Allowed

- ❌ Arbitrary command execution (no shell access)
- ❌ Access to system files outside allowed directories
- ❌ Execution of .exe, .bat, .cmd, .ps1, .vbs, .js files
- ❌ File operations exceeding 10MB size limit
- ❌ Requests from non-approved phone numbers

## 📚 Available Tools

10 built-in tools for system monitoring:

| Tool | Args | Purpose |
|------|------|---------|
| `dir_inbox` | none | List files in inbox folder |
| `dir_outbox` | none | List files in outbox folder |
| `list_files` | path | List files in directory |
| `system_info` | none | OS name, version, memory |
| `cpu_usage` | none | Current CPU percentage |
| `disk_space` | none | C: drive free/total space |
| `current_time` | none | System date and time |
| `network_status` | none | Network IP configuration |
| `list_processes` | none | Top 10 running processes |
| `uptime` | none | System uptime in hours |

**Full tool documentation**: See [TOOLS.md](docs/TOOLS.md)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/mattis-klein/AI-SMS-Agent.git
cd AI-SMS-Agent
```

### 2. Create Environment Files

**agent/.env**:

```
AGENT_API_KEY=super-secret-key-12345
AGENT_WORKSPACE=agent/workspace
```

**sms-bridge/.env**:

```
AGENT_KEY=super-secret-key-12345
AGENT_URL=http://127.0.0.1:8787
BRIDGE_PORT=34567
TWILIO_AUTH_TOKEN=your-twilio-auth-token
PUBLIC_BASE_URL=https://your-public-url.com
ALLOWED_SMS_FROM=+15551234567
```

### 3. Install Dependencies

**Agent** (Python 3.10+):

```bash
cd agent
pip install fastapi uvicorn pydantic psutil python-dotenv
```

**Bridge** (Node.js 18+):

```bash
cd sms-bridge
npm install
```

### 4. Run Both Services

**Terminal 1 - Agent**:

```bash
cd agent
python -m uvicorn agent:app --host 127.0.0.1 --port 8787
```

**Terminal 2 - SMS Bridge**:

```bash
cd sms-bridge
node sms-server.js
```

### 5. Test via API

```bash
# Via direct tool execution
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: super-secret-key-12345" \
  -H "x-sender: +15551234567" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "system_info", "args": {}}'

# Via natural language
curl -X POST http://localhost:8787/execute-nl \
  -H "x-api-key: super-secret-key-12345" \
  -H "x-sender: +15551234567" \
  -H "Content-Type: application/json" \
  -d '{"message": "what time is it"}'

# List available tools
curl http://localhost:8787/tools \
  -H "x-api-key: super-secret-key-12345"
```

### 6. Configure Twilio Webhook

Set your Twilio webhook URL to: `https://your-public-url.com:34567/sms`

Then text commands to your Twilio number from an approved phone!

## 📖 Usage Examples

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
    "C:\\Users\\Public\\Documents",
    "C:\\Users\\owner\\Documents",
    "C:\\Projects",
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
```

This automatically:
- Creates Python virtual environment if needed
- Installs all dependencies (Python + Node.js)
- Launches agent, bridge, and tunnel with labeled output
- Monitors all processes and handles clean shutdown on Ctrl+C

## 📋 Available Commands

The agent supports these safe commands out of the box:

| Command | Description | Example |
|---------|-------------|---------|
| `hello` | Test connection | `hello` |
| `help` | Show command list | `help` |
| `commands` | List all available commands | `commands` |
| `run <name>` | Execute a whitelisted command | `run system_info` |
| `list <path>` | List files in directory | `list C:\Projects` |
| `read <path>` | Read a file | `read inbox/notes.txt` |
| `write <path> :: <text>` | Write to file | `write inbox/todo.txt :: Buy milk` |

### Built-in System Commands

- `dir_inbox` - List files in inbox
- `dir_outbox` - List files in outbox
- `list_files` - List files in a directory (requires path argument)
- `system_info` - Get OS and hardware info
- `cpu_usage` - Check CPU usage percentage
- `disk_space` - Check C: drive free space
- `current_time` - Get system date and time
- `network_status` - Check network connection
- `list_processes` - Show top 10 running processes
- `uptime` - Get system uptime in hours

### Natural Language Mode

Send plain English messages and the AI will translate them to safe commands:

- "check my inbox" → Runs `dir_inbox`
- "what is my CPU usage" → Runs `cpu_usage`
- "list files in my projects folder" → Runs `list_files C:\Projects`

*Requires OpenAI API key configured in `.env`*

## 📁 Project Structure

```
AI-SMS-Agent/
├── agent/                          # Python FastAPI agent
│   ├── agent.py                    # Main agent code
│   ├── config.json                 # Command whitelist & security settings
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Environment template
│   └── workspace/                  # Workspace for file operations
│       ├── inbox/                  # Incoming files
│       ├── outbox/                 # Outgoing files
│       └── logs/                   # Agent logs (JSON format)
├── sms-bridge/                     # Node.js SMS bridge
│   ├── sms-server.js               # Bridge server
│   ├── package.json                # Node dependencies
│   ├── .env.example                # Environment template
│   └── logs/                       # Bridge logs (JSON format)
├── scripts/                        # PowerShell launchers
│   ├── start-all.ps1               # Launch everything (recommended)
│   ├── start-agent.ps1             # Launch agent only
│   ├── start-bridge.ps1            # Launch bridge only
│   └── start-cloudflare.ps1        # Launch tunnel only
└── docs/                           # Complete documentation
```

### Command Whitelist (`agent/config.json`)

Commands are configured in `agent/config.json`. Each command defines:
- **description**: What the command does
- **command**: The actual system command to run
- **requires_args**: Whether arguments are needed
- **validate_path**: Whether to validate path arguments

Example configuration:
```json
{
   "allowed_commands": {
      "list_files": {
         "description": "List files in a specified directory",
         "command": ["cmd", "/c", "dir", "{path}"],
         "requires_args": true,
         "validate_path": true
      }
   },
   "allowed_directories": [
      "C:\\Users\\Public\\Documents",
      "C:\\Users\\owner\\Documents",
      "C:\\Projects",
      "C:\\Temp"
   ],
   "security": {
      "max_file_size_bytes": 10485760,
      "blocked_extensions": [".exe", ".bat", ".cmd", ".ps1"]
   }
}
```

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

**Basic Commands:**
```
SMS: hello
Response: Hi. SMS link is working.

SMS: run system_info
Response: OS Name: Microsoft Windows 11...

SMS: list C:\Projects
Response: Volume in drive C...

SMS: read inbox/notes.txt
Response: [file contents]
```

**Natural Language:**
```
SMS: check my CPU usage
Response: CPU usage is at 23.5%

SMS: what files are in my inbox
Response: [directory listing]
```

## ➕ Adding New Commands

To safely add a new command:

1. **Edit `agent/config.json`** and add to `allowed_commands`:
```json
"memory_usage": {
   "description": "Check system memory usage",
   "command": ["powershell", "-Command", "Get-WmiObject Win32_OperatingSystem | Select FreePhysicalMemory,TotalVisibleMemorySize"],
   "requires_args": false
}
```

2. **Restart the agent** (Ctrl+C the launcher and run `.\scripts\start-all.ps1` again)

3. **Test via SMS**: `run memory_usage`

Commands with arguments can use placeholders:
- `{workspace}` - Replaced with agent workspace path
- `{path}` - Replaced with validated user-provided path

**Path validation**: Commands with `"validate_path": true` will only accept paths in:
- Agent workspace (`agent/workspace/`)
- Directories listed in `allowed_directories`

**Path validation**: Commands with `"validate_path": true` will only accept paths in:
- Agent workspace (`agent/workspace/`)
- Directories listed in `allowed_directories`

## 🐙 Pushing to GitHub

The repository is already initialized with git and ready to push:

```powershell
# Add GitHub remote (replace with your repo URL)
git remote add origin https://github.com/mattis-Klein/AI-SMS-Agent.git

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
