# Project Organization Guide

This repository now uses one canonical platform root: mashbak/.

## Canonical Architecture

```text
AI-SMS-Agent/
├── mashbak/
│   ├── agent/
│   ├── assistants/
│   │   ├── mashbak/
│   │   └── bucherim/
│   ├── sms_bridge/
│   ├── desktop_app/
│   ├── data/
│   │   ├── users/
│   │   ├── logs/
│   │   ├── media/
│   │   └── workspace/
│   ├── docs/
│   ├── scripts/
│   └── tests/
├── README.md
├── PROJECT-ORGANIZATION.md
└── .gitignore
```

## Responsibility Boundaries

- mashbak/ is the platform root.
- mashbak/agent is the shared reasoning and execution core.
- mashbak/assistants contains assistant-specific behavior/config.
- mashbak/sms_bridge is transport-only.
- mashbak/desktop_app is UI-only.
- mashbak/data holds runtime users, logs, media, and workspace data.

## Runtime Data Policy

Runtime data is consolidated under mashbak/data:

- mashbak/data/users/bucherim/ for Bucherim membership and conversation records
- mashbak/data/logs/ for agent and bridge logs
- mashbak/data/media/bucherim/ for assistant media indexes/files
- mashbak/data/workspace/ for backend workspace tool operations

## Environment Files Policy

- Runtime source: mashbak/.env.master
- Template: mashbak/.env.master.example
- Bridge template: mashbak/sms_bridge/.env.example

Do not commit real secrets.

## Cleanup Outcome

- Legacy duplicate roots (agent/, bucherim/, sms-bridge/) are not part of canonical architecture.
- All active implementation, scripts, tests, and docs should reference mashbak/ paths only.
