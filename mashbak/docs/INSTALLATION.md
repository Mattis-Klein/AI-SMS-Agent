# Installation Guide

## Prerequisites

- Windows 10+
- Python 3.11+ recommended
- Node.js 18+
- Optional: cloudflared for public Twilio webhook testing

## 1. Python Dependencies

```powershell
python -m pip install -r mashbak/agent/requirements.txt
```

## 2. Node Dependencies

```powershell
cd mashbak/sms_bridge
npm install
```

## 3. Create Runtime Config

```powershell
cd mashbak
Copy-Item .env.master.example .env.master
notepad .env.master
```

Required baseline keys:
- AGENT_API_KEY
- AGENT_URL
- BRIDGE_PORT
- PUBLIC_BASE_URL

## 4. Run Services

Backend:

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

Bridge:

```powershell
cd mashbak/sms_bridge
npm start
```

Desktop:

```powershell
cd mashbak
python desktop_app/main.py
```

## 5. Verify

Backend health:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8787/health -Headers @{"x-api-key"="<AGENT_API_KEY>"}
```

Bridge health:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:34567/health
```

## 6. Optional Twilio + Tunnel

- Start cloudflared for bridge port.
- Set PUBLIC_BASE_URL to active tunnel URL.
- Configure Twilio webhook to: https://<public-url>/sms

## 7. Build Desktop Executable

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Build output:
- mashbak/dist/Mashbak.exe

## Notes

- Runtime config source is mashbak/.env.master.
- Chat config updates write to mashbak/.env.master.
- Bridge transport/access-control values require bridge restart after change.

## Stabilization Verification (Post-Install)

After install, verify these behavior guarantees from Desktop chat:

- `create a file named verify.txt in data/workspace/inbox`
- `delete that file`
- `delete that file` (should fail clearly, not claim success)
- `list recent emails` (should classify failure as config/auth/connection)
