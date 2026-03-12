# Project Organization Guide

This file reflects the current multi-assistant repository layout.

## Root Structure

```text
C:\AI-SMS-Agent\
├── .gitignore
├── .vscode/
├── README.md
├── PROJECT-ORGANIZATION.md
├── mashbak/
│   ├── README.md
│   ├── agent/
│   ├── bucherim/
│   ├── desktop_app/
│   ├── sms-bridge/
│   ├── scripts/
│   ├── docs/
│   └── workspace/
└── bucherim/
    ├── README.md
    ├── agent/
    ├── sms-bridge/
    ├── config/
    └── workspace/
```

## Environment Files Policy

- Tracked in repo: `mashbak/agent/.env.example`, `mashbak/sms-bridge/.env.example`
- Not tracked in repo: `mashbak/.env.master` with real secrets
- Do not create per-component `.env` files; runtime configuration is centralized in `mashbak/.env.master`

## Runtime Clutter Policy

Generated artifacts stay out of source control:

- Python virtual environments and caches
- PyInstaller build output
- `mashbak/sms-bridge/node_modules/`
- `mashbak/agent/workspace/` runtime contents except `.gitkeep`
- `mashbak/sms-bridge/logs/` except `.gitkeep`
- local `.env` files

## Application Roles

- `mashbak/`: active production assistant, desktop-first with optional SMS transport
- `mashbak/bucherim/`: Bucherim SMS subsystem data and per-user logs
- `bucherim/`: legacy scaffold folder retained for future standalone split if needed

## Start Points

- Repo overview: `README.md`
- Mashbak overview: `mashbak/README.md`
- Mashbak docs index: `mashbak/docs/INDEX.md`
- Mashbak build script: `mashbak/scripts/build-app.ps1`
