# Runbook

## Start Services

Backend:

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

Bridge:

```powershell
cd mashbak/sms-bridge
npm start
```

Desktop:

```powershell
cd mashbak
python desktop_app/main.py
```

## Stop Services

Use Ctrl+C in active terminals, or stop listeners by port when needed.

## Health Checks

Backend:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8787/health -Headers @{"x-api-key"="<AGENT_API_KEY>"}
```

Bridge:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:34567/health
```

## Incident Checklist

1. Verify backend health.
2. Verify bridge health.
3. Check agent log at mashbak/agent/workspace/logs/agent.log.
4. Check bridge log at mashbak/sms-bridge/logs/bridge.log.
5. Confirm .env.master values and restart requirements.

## Restart Rules

- Backend dynamic settings reload in-process on request execution.
- Bridge sender access-control and Twilio settings require bridge restart.
- AGENT_API_KEY changes require caller key update and service/client re-auth.
