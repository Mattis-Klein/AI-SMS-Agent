# Quick Start

Get Mashbak running quickly from repository root.

## 1. Prepare Config

```powershell
Copy-Item mashbak/.env.master.example mashbak/.env.master
notepad mashbak/.env.master
```

Minimum values to set:
- AGENT_API_KEY
- AGENT_URL=http://127.0.0.1:8787
- BRIDGE_PORT=34567
- PUBLIC_BASE_URL=<your tunnel url for Twilio>

## 2. Start Backend

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

## 3. Start Bridge

In a second terminal:

```powershell
cd mashbak/sms_bridge
npm start
```

## 4. Start Desktop

In a third terminal:

```powershell
cd mashbak
python desktop_app/main.py
```

## 5. Optional Build

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Output executable:
- mashbak/dist/Mashbak.exe

## 6. Sanity Checks

- Backend: GET http://127.0.0.1:8787/health
- Bridge: GET http://127.0.0.1:34567/health
- Desktop smoke: python mashbak/desktop_app/main.py --ui-smoke

## Chat Config Example

Use natural language or direct assignment:
- set MODEL_RESPONSE_MAX_TOKENS to 250
- EMAIL_PASSWORD = app-password

Backend applies dynamic config updates in-process. Bridge transport/access-control changes require bridge restart.
