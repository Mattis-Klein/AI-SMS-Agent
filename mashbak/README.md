# Mashbak Assistant

Mashbak is the current production assistant in this repository.

- Desktop-first local application
- Optional SMS bridge for remote transport
- Shared backend runtime for both desktop and SMS inputs

## Run

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

## Build

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```
