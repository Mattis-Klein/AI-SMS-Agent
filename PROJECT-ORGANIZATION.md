# Project Organization Guide

This file matches the current repository layout exactly.

## Root Structure

```text
C:\AI-SMS-Agent\
├── .gitignore
├── .vscode/
│   └── settings.json
├── README.md
├── PROJECT-ORGANIZATION.md
├── scripts/
│   ├── dev-start.ps1
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
        └── mashbak-integration.md
```

## Environment Files Policy

- Tracked in repo: `agent/.env.example`, `sms-bridge/.env.example`
- Not tracked in repo: real `.env` files with secrets
- Create local `.env` files by copying from each `.env.example`

## Runtime Clutter Policy

Runtime artifacts are not part of source structure:

- `agent/.venv/`
- `agent/__pycache__/`
- `sms-bridge/node_modules/`
- `sms-bridge/logs/`
- local `.env` files

VS Code also hides these in Explorer via `.vscode/settings.json`.

## Architecture Flow

```text
Flip phone SMS
  -> Twilio number
  -> Cloudflare tunnel URL
  -> sms-bridge/sms-server.js
  -> agent/agent.py
  -> SMS response back through Twilio
```

## Start Points

- Main overview: `README.md`
- Unified launcher: `.\scripts\dev-start.ps1` (recommended - starts all services)
- Documentation index: `docs/INDEX.md`
- Operations: `docs/RUNBOOK.md`
- Structure reference: `docs/PROJECT-STRUCTURE.md`
