# Testing Guide

Run tests from mashbak root unless noted.

## Automated Regression Suite

Python:

```powershell
python -m pytest -q
```

Bridge:

```powershell
cd mashbak/sms_bridge
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
cd mashbak/sms_bridge
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
Select-String -Path data/logs/agent.log -Pattern "hunter2" -SimpleMatch
Select-String -Path data/logs/bridge.log -Pattern "hunter2" -SimpleMatch
```

Expected: no raw secret hits.

## Notes

- Keep smoke checks on isolated ports if another local service is already using 8787 or 34567.
- /run exists only as compatibility path and forwards to /execute.

## Manual Conversation Simulation Checklist

Run these in desktop chat against a fresh session:

1. `create a file named sim-check.txt in data/workspace/inbox`
2. `delete that file`
3. `delete that file` (expect explicit failure reason)
4. `system info`
5. `list recent emails` (expect categorized failure guidance when unavailable)

Expected behavior:

- One assistant completion appears per send cycle.
- Timestamp appears once per final assistant message.
- Success language appears only after verified successful execution.
- Follow-up references resolve from last verified filesystem action in session context.

## Control Board Verification

Validate these in desktop app after unlock:

1. Dashboard shows backend and bridge connectivity and recent actions.
2. Chat / Console still executes natural-language requests.
3. Communications page can enter and save email configuration fields.
4. Communications page can run email connection test and show status/errors clearly.
5. Files & Permissions page can load/edit/save allowed directories.
6. Files & Permissions policy path test returns allowed/blocked reason.
7. Activity / Audit page shows timestamp, tool, state, and target rows.
8. Routing controls and Bucherim list/pending visibility are present.
