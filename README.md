# AI SMS Agent

**Control your computer safely from a flip phone using SMS messages.**

AI SMS Agent is a secure, local SMS-controlled system that lets you execute pre-approved commands on your Windows PC via text messages. The system uses a command whitelist, path validation, and structured logging to ensure safe operation.

## 🏗️ Architecture Overview

The system connects your flip phone to your computer through a secure chain:

```
📱 Flip Phone (SMS)
   ↓
☁️ Twilio (SMS Gateway)
   ↓
🌐 Cloudflare Tunnel (Secure Public Access)
   ↓
🌉 SMS Bridge (Node.js Express)
   ↓
🤖 FastAPI Agent (Python)
   ↓
💻 Local Computer (Controlled Commands)
   ↓
📨 Response flows back through the chain
```

**How it works:**
1. You send an SMS from your flip phone to your Twilio number
2. Twilio forwards the webhook through a Cloudflare Tunnel
3. The Node.js SMS bridge receives and validates the request
4. The bridge forwards the command to the FastAPI agent
5. The agent validates the command against the whitelist and executes it safely
6. Results flow back through the bridge and Twilio to your phone

## 🔐 Security Features

- **Command Whitelist**: Only pre-approved commands can execute
- **Path Validation**: File access restricted to allowed directories
- **Sender Validation**: Only authorized phone numbers can send commands
- **Twilio Signature Verification**: Prevents unauthorized webhook access
- **File Extension Blocking**: Dangerous file types (.exe, .bat, etc.) are blocked
- **Structured Logging**: Every action is logged with timestamp, sender, and result
- **No Arbitrary Code**: System cannot execute arbitrary commands

## ⚡ Quick Start

Launch the entire system with one command:

```powershell
.\scripts\start-all.ps1
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
