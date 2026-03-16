# Mashbak

Private operator assistant. Not for public distribution.

## Architecture

Strict boundaries:
- **Backend** (`agent/`): single reasoning engine for all surfaces. All tool execution flows through interpreter → dispatcher → tool registry.
- **Desktop** (`desktop_app/`): UI and presentation only. No local reasoning or tool execution.
- **SMS bridge** (`sms_bridge/`): transport and access-control only. No reasoning.
- **Bucherim** (`assistants/bucherim/`): separate SMS assistant flow with independent membership state and logs.

### Runtime Topology

```
Desktop UI (desktop_app/) ─────────────────────┐
                                                ├──► FastAPI backend (agent/agent.py :8787)
SMS bridge (sms_bridge/) ──────────────────────┘

Control-board API composition:
  agent/routes/system.py
  agent/routes/execution.py
  agent/routes/control_board.py (+ control_board_* submodules)
  agent/voice_handler.py

/execute-nl request path:
  AgentRuntime → AssistantCore → NLInterpreter → Dispatcher → ToolRegistry → Tool

Bucherim SMS path:
  Twilio (+18772683048) → sms_bridge → POST /bucherim/sms → AgentRuntime → BucherimService
```

### Backend Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /tools | Tool list |
| POST | /execute | Structured tool call |
| POST | /execute-nl | Natural language execution |
| POST | /voice | Twilio voice webhook |
| POST | /bucherim/sms | Bucherim SMS flow |
| GET | /control-board/overview | Dashboard overview |
| GET | /control-board/activity | Unified audit/activity stream |
| GET | /control-board/assistants | Runtime and Bucherim assistant summary |
| GET | /control-board/routing | Bucherim routing overview |
| GET | /control-board/email-accounts | Multi-account email config |
| GET | /control-board/files-policy | Allowed directories + blocked attempts |

Headers: `x-api-key` required on protected endpoints.

## Directory Layout

```
mashbak/
├── agent/                 # FastAPI backend + reasoning engine
│   ├── agent.py               # App entry and router composition
│   ├── runtime.py             # Runtime wiring, config reload, source handling
│   ├── assistant_core.py      # Reasoning and response shaping
│   ├── interpreter.py         # NL and config assignment parsing
│   ├── dispatcher.py          # Tool validation/execution path
│   ├── session_context.py     # In-memory context tracking
│   ├── voice_handler.py       # Twilio voice webhook and caller allowlist
│   ├── routes/                # API route modules
│   ├── services/              # Control-board and integration services
│   ├── config_loader.py       # .env.master reader
│   ├── logger.py              # Logging setup
│   ├── redaction.py           # Redaction helpers
│   └── tools/                 # Tool registry + built-in implementations
├── assistants/
│   └── bucherim/          # Bucherim SMS assistant subsystem
│       ├── bucherim_service.py # Conversation service wrapper
│       ├── membership.py      # State transitions
│       ├── storage.py         # File-based persistence
│       ├── admin.py           # Operator routing admin APIs
│       ├── config_store.py    # Canonical config access
│       ├── bucherim_router.py # Routing layer
│       └── config/            # approved/blocked/pending number lists
├── desktop_app/           # Windows control board UI (PySide6)
│   ├── main.py                # Entry point and PIN lock
│   ├── ui_pyside6.py          # Control board layout and page handlers
│   ├── agent_service.py       # Backend process management
│   └── agent_client.py        # HTTP client to backend
├── sms_bridge/            # Node.js Twilio SMS bridge
│   ├── sms-server.js          # Express server + webhook handler
│   ├── access-control-config.js  # Sender allowlist/deny logic
│   ├── env-loader.js          # Bridge env reader
│   └── redaction.js           # Log redaction
├── tests/                 # pytest suite (agent) + jest suite (bridge)
├── scripts/               # Operational PowerShell scripts
├── data/                  # Runtime data (logs, workspace, user state)
└── .env.master            # Runtime configuration (local only, gitignored)
```

## Starting Services

Backend (port 8787):
```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

SMS bridge (port 34567):
```powershell
cd mashbak/sms_bridge ; npm start
```

Desktop:
```powershell
cd mashbak ; python desktop_app/main.py
```

Or use `scripts/start-agent.ps1`, `scripts/start-bridge.ps1`.

## Configuration

Runtime config lives in `mashbak/.env.master` (local only, gitignored). Config changes via chat use the `set_config_variable` tool which writes directly to this file.

Reload behavior:
- Backend/OpenAI/email/runtime tuning: reload in-process.
- Bridge access-control and transport values: require bridge restart.
- `AGENT_API_KEY` change: requires restart of all active clients.

## Built-in Tools

System/File: `dir_inbox`, `dir_outbox`, `list_files`, `create_folder`, `create_file`, `delete_file`, `system_info`, `cpu_usage`, `disk_space`, `current_time`, `network_status`, `list_processes`, `uptime`

Email: `list_recent_emails`, `summarize_inbox`, `search_emails`, `read_email_thread`

Config: `set_config_variable`

All tools: grounded execution — completion claims only after confirmed successful tool run. `create_folder` and `create_file` must return `data.created_path`.

## Bucherim

Dedicated SMS assistant on Twilio number +18772683048. Membership states: `approved`, `pending`, and `blocked` (with legacy migration support in storage). Canonical state/config lives under `assistants/bucherim/config/`. Admin tool: `scripts/approve-bucherim-member.ps1`.

## Voice

Voice webhook at `/voice`. Caller allowlist enforced via `VOICE_ALLOWED_NUMBERS` in `.env.master`. Non-allowlisted callers receive rejection TwiML and hangup.

## Health Checks

```powershell
# Backend
Invoke-RestMethod -Uri http://127.0.0.1:8787/health -Headers @{"x-api-key"="<key>"}
# Bridge
Invoke-RestMethod -Uri http://127.0.0.1:34567/health
```

Logs: `data/logs/agent.log`, `data/logs/bridge.log`.

## Build Desktop Executable

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Output: `mashbak/dist/Mashbak.exe`
