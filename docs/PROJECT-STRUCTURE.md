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
├── scripts/
│   ├── start-all.ps1         ← Unified launcher (starts everything)
│   ├── start-agent.ps1
│   ├── start-bridge.ps1
│   └── start-cloudflare.ps1
├── agent/
│   ├── .env.example
│   ├── agent.py
│   ├── requirements.txt
│   └── workspace/
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
        └── ai-sms-integration.md
```

## What Each Top-Level Folder Does

- `agent/`: Python FastAPI agent for controlled local actions
- `sms-bridge/`: Node.js Twilio bridge
- `scripts/`: PowerShell launcher scripts
  - `start-all.ps1` — Unified launcher (recommended) - starts all three services
  - `start-agent.ps1` — Launch only the Python agent
  - `start-bridge.ps1` — Launch only the SMS bridge
  - `start-cloudflare.ps1` — Launch only the Cloudflare tunnel
- `docs/`: project documentation
- `.vscode/`: workspace display settings (hides runtime clutter)

## Environment Files

Tracked templates only:
- `agent/.env.example`
- `sms-bridge/.env.example`

Local-only runtime files (not tracked):
- `agent/.env`
- `sms-bridge/.env`

## Runtime-Generated Folders (Excluded)

These are expected during execution but not part of the clean source tree:

- `agent/.venv/`
- `agent/__pycache__/`
- `sms-bridge/node_modules/`
- `sms-bridge/logs/`

## Quick Lookup

- System overview: [README.md](../README.md)
- Documentation index: [INDEX.md](INDEX.md)
- Operations: [RUNBOOK.md](RUNBOOK.md)
- Environment variables: [ENVIRONMENT.md](ENVIRONMENT.md)
- Legacy references: [legacy/](legacy)

---

**Last Updated:** March 9, 2026
