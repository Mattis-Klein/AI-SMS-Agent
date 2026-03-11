# AI-SMS-Agent

This repository hosts multiple assistant applications.

## Assistants

- Mashbak: current production assistant in [mashbak/README.md](mashbak/README.md)
- Bucherim: scaffold-only placeholder for a future assistant in [bucherim/README.md](bucherim/README.md)

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
- Bucherim is scaffold-only and not runnable yet.
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

Incoming SMS routing is being prepared for a future router layer:

```text
incoming SMS
  -> router
     -> mashbak
     -> bucherim
```

## Documentation

- Root structure guide: [PROJECT-ORGANIZATION.md](PROJECT-ORGANIZATION.md)
- Mashbak overview: [mashbak/README.md](mashbak/README.md)
- Mashbak docs index: [mashbak/docs/INDEX.md](mashbak/docs/INDEX.md)

## Notes

- Real `.env` files are local-only and must remain untracked.
- Mashbak runtime data lives under `mashbak/agent/workspace/` and `mashbak/sms-bridge/logs/`.
