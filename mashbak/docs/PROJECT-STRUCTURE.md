# Project Structure

This document reflects the current repository structure exactly.

## Directory Tree

```text
C:\AI-SMS-Agent\
├── .gitignore
├── .vscode/
│   └── settings.json
├── README.md
├── PROJECT-ORGANIZATION.md
├── local-memory-notes/      ← Local markdown memory folder (gitignored)
├── scripts/
│   ├── dev-start.ps1         ← Unified launcher (starts everything)
│   ├── build-app.ps1         ← Desktop app packaging script (PyInstaller)
│   ├── start-agent.ps1
│   ├── start-bridge.ps1
│   └── start-cloudflare.ps1
├── agent/
│   ├── .env.example
│   ├── agent.py
│   ├── runtime.py
│   ├── dispatcher.py
│   ├── interpreter.py
│   ├── logger.py
│   ├── tools/
│   ├── requirements.txt
│   └── workspace/
├── desktop_app/
│   ├── main.py
│   ├── agent_service.py
│   ├── agent_client.py
│   ├── ui.py
│   └── widgets.py
├── sms-bridge/
│   ├── .env.example
│   ├── package.json
│   ├── package-lock.json
│   └── sms-server.js
└── docs/
    ├── INDEX.md
    ├── QUICK-START.md
    ├── INSTALLATION.md
    ├── RUNBOOK.md
    ├── COMMANDS.md
    ├── ENVIRONMENT.md
    ├── LOGGING.md
    ├── API.md
    ├── AI-INTEGRATION.md
    ├── FAQ.md
    ├── SECURITY-HARDENING.md
    ├── BEST-PRACTICES.md
    ├── COMPONENTS.md
    ├── PROJECT-STRUCTURE.md
    ├── DEVELOPMENT.md
    ├── TESTING.md
    └── legacy/
        ├── ARCHITECTURE.md
        ├── SECURITY.md
        ├── TROUBLESHOOTING.md
        └── mashbak-integration.md
```

## What Each Top-Level Folder Does

- `agent/`: Python FastAPI agent for controlled local actions
- `sms-bridge/`: Node.js Twilio bridge
- `scripts/`: PowerShell launcher scripts
  - `dev-start.ps1` — Unified launcher (recommended) - starts all three services
  - `build-app.ps1` — Builds `AISMSDesktop.exe` for normal desktop usage
  - `start-agent.ps1` — Launch only the Python agent
  - `start-bridge.ps1` — Launch only the SMS bridge
  - `start-cloudflare.ps1` — Launch only the Cloudflare tunnel
- `desktop_app/`: Local desktop application (header/sidebar/chat/activity-status layout)
  - Starts local agent automatically
  - Uses same dispatcher/tool pipeline as SMS
  - Never sends SMS replies
- `docs/`: project documentation
- `.vscode/`: workspace display settings (hides runtime clutter)

## Environment Files

Tracked templates only:
- `mashbak/.env.master.example`
- `mashbak/.env.master.example`

Local-only runtime files (not tracked):
- `mashbak/.env.master`
- `mashbak/.env.master`

## Runtime-Generated Folders (Excluded)

These are expected during execution but not part of the clean source tree:

- `agent/.venv/`
- `agent/__pycache__/`
- `sms-bridge/node_modules/`
- `sms-bridge/logs/`
- `local-memory-notes/`

## Quick Lookup

- System overview: [README.md](../README.md)
- Documentation index: [INDEX.md](INDEX.md)
- Operations: [RUNBOOK.md](RUNBOOK.md)
- Environment variables: [ENVIRONMENT.md](ENVIRONMENT.md)
- Legacy references: [legacy/](legacy)

---

**Last Updated:** March 10, 2026

