# AI-SMS-Agent

This repository is organized around one canonical platform root: mashbak/.

## Platform Overview

- Shared backend reasoning engine: mashbak/agent
- Assistant-specific modules: mashbak/assistants
- SMS transport-only bridge: mashbak/sms_bridge
- Desktop UI client: mashbak/desktop_app
- Runtime data root: mashbak/data

## Current Assistants

- Mashbak profile: mashbak/assistants/mashbak
- Bucherim SMS assistant: mashbak/assistants/bucherim

## Quick Run

```powershell
# Backend
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787

# SMS bridge
cd mashbak/sms_bridge
npm start

# Desktop UI
cd ..
python desktop_app/main.py
```

## Runtime Data Paths

- Workspace data: mashbak/data/workspace/
- User records: mashbak/data/users/
- Logs: mashbak/data/logs/
- Media: mashbak/data/media/

## Docs

- Organization guide: PROJECT-ORGANIZATION.md
- Platform README: mashbak/README.md
- Docs index: mashbak/docs/INDEX.md
