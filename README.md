# AI-SMS-Agent

This repository hosts multiple assistant applications.

## Assistants

- Mashbak: current production assistant in [mashbak/README.md](mashbak/README.md)
- Bucherim: SMS-first assistant subsystem now implemented inside `mashbak/` (see [mashbak/docs/BUCHERIM.md](mashbak/docs/BUCHERIM.md))

## Repository Layout

```text
AI-SMS-Agent/
├── mashbak/
│   ├── agent/
│   ├── desktop_app/
│   ├── sms-bridge/
│   ├── scripts/
│   ├── docs/
│   └── workspace/
└── bucherim/
    ├── agent/
    ├── sms-bridge/
    ├── config/
    └── workspace/
```

## Current Status

- Mashbak is the active app and retains the current desktop, agent, and SMS functionality.
- Bucherim membership-gated SMS flow is live in Mashbak runtime and bridge routing.
- Repo-level docs are now an index; assistant-specific operational details live inside each assistant folder.

## Run Mashbak

```powershell
# Agent
cd mashbak/agent
python -m uvicorn agent:app --host 127.0.0.1 --port 8787

# SMS bridge
cd mashbak/sms-bridge
npm start

# Desktop UI
python mashbak/desktop_app/main.py
```

Build the Windows executable with:

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Output: `mashbak/dist/Mashbak.exe`

## Routing Direction

Incoming SMS routing now supports explicit assistant destination routing:

```text
incoming SMS
  -> mashbak/sms-bridge transport
     -> Mashbak sender-access route (existing number behavior)
     -> Bucherim route when inbound To is +18772683048
```

## Documentation

- Root structure guide: [PROJECT-ORGANIZATION.md](PROJECT-ORGANIZATION.md)
- Mashbak overview: [mashbak/README.md](mashbak/README.md)
- Mashbak docs index: [mashbak/docs/INDEX.md](mashbak/docs/INDEX.md)

## Notes

- Real `.env` files are local-only and must remain untracked.
- Mashbak runtime data lives under `mashbak/agent/workspace/` and `mashbak/sms-bridge/logs/`.
