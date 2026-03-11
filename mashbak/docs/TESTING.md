# Testing Guide

Run tests from mashbak root unless noted.

## Automated Regression Suite

Python:

```powershell
python -m pytest -q
```

Bridge:

```powershell
cd sms-bridge
npm test
```

Optional Python syntax compile sweep:

```powershell
$files = git ls-files "*.py"
foreach ($f in $files) { python -m py_compile $f }
```

## High-Value Areas Covered

- Interpreter mapping and follow-up carryover
- Session isolation by source and sender
- Missing-configuration error shaping
- Config-through-chat validation and persistence
- Redaction behavior in backend and bridge helpers
- Bridge access-control routing decisions

## Backend Smoke Checks

Start backend:

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

Health:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8787/health -Headers @{"x-api-key"="<AGENT_API_KEY>"}
```

Direct tool path:

```powershell
$h = @{"x-api-key"="<AGENT_API_KEY>";"x-sender"="review"}
$b = '{"tool_name":"list_files","args":{"path":"inbox"}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/execute -Headers $h -ContentType "application/json" -Body $b
```

Natural-language path:

```powershell
$h = @{"x-api-key"="<AGENT_API_KEY>";"x-sender"="review"}
$b = '{"message":"set MODEL_RESPONSE_MAX_TOKENS to 250"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/execute-nl -Headers $h -ContentType "application/json" -Body $b
```

## Desktop Smoke Checks

```powershell
python desktop_app/main.py --ui-smoke
```

Expected:
- process exits 0
- startup path succeeds without interactive crash

## Bridge Smoke Checks

Start bridge:

```powershell
cd sms-bridge
npm start
```

Health:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:34567/health
```

Expected health fields include:
- status
- port
- logFile
- twilioValidationEnabled
- senderAccessControlEnabled
- accessControlConfigLoadedAt
- accessControlReloadRequiresRestart

## Redaction Verification

After sending a message with a secret-like assignment, verify logs do not contain raw values:

```powershell
Select-String -Path agent/workspace/logs/agent.log -Pattern "hunter2" -SimpleMatch
Select-String -Path sms-bridge/logs/bridge.log -Pattern "hunter2" -SimpleMatch
```

Expected: no raw secret hits.

## Notes

- Keep smoke checks on isolated ports if another local service is already using 8787 or 34567.
- /run exists only as compatibility path and forwards to /execute.
