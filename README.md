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

## Stabilization Update (2026-03-12)

- Filesystem mutation replies are now execution-grounded: success language is emitted only after verified tool success.
- Follow-up references like "delete that file" resolve from session-backed successful actions (`last_result`, `last_task`, `last_created_path`).
- Email failures are now categorized as missing configuration, authentication failure, or connection failure for clearer guidance.
- Desktop chat rendering now replaces pending replies in-place to avoid duplicate-looking timestamp artifacts.
