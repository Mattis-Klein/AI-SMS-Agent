# Logging Guide

## Backend Log

Path:
- mashbak/agent/workspace/logs/agent.log

Backend writes structured JSON line events for:
- request lifecycle
- tool execution
- validation and failure categories
- startup/shutdown

## Bridge Log

Path:
- mashbak/sms-bridge/logs/bridge.log

Bridge logs transport/access-control events and backend forwarding stages.

## Redaction

Sensitive values are sanitized before persistence.

Backend redaction:
- agent/redaction.py

Bridge redaction:
- sms-bridge/redaction.js

## Quick Checks

Tail backend log:

```powershell
Get-Content mashbak/agent/workspace/logs/agent.log -Tail 50
```

Tail bridge log:

```powershell
Get-Content mashbak/sms-bridge/logs/bridge.log -Tail 50
```

Search for accidental secret leak marker:

```powershell
Select-String -Path mashbak/agent/workspace/logs/agent.log -Pattern "hunter2" -SimpleMatch
```
