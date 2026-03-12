# Logging Guide

## Backend Log

Path:
- mashbak/data/logs/agent.log

Backend writes structured JSON line events for:
- request lifecycle
- tool execution
- validation and failure categories
- startup/shutdown

## Bridge Log

Path:
- mashbak/data/logs/bridge.log

Bridge logs transport/access-control events and backend forwarding stages.

## Redaction

Sensitive values are sanitized before persistence.

Backend redaction:
- agent/redaction.py

Bridge redaction:
- sms_bridge/redaction.js

## Quick Checks

Tail backend log:

```powershell
Get-Content mashbak/data/logs/agent.log -Tail 50
```

Tail bridge log:

```powershell
Get-Content mashbak/data/logs/bridge.log -Tail 50
```

Search for accidental secret leak marker:

```powershell
Select-String -Path mashbak/data/logs/agent.log -Pattern "hunter2" -SimpleMatch
```
