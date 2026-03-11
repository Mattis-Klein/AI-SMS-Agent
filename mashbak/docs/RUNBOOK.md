# Runbook - Operational Commands

Daily operations and standard commands for running the system.

## Quick Reference - Unified Launcher (Recommended)

The entire system can be started with a single command:

```powershell
.\scripts\dev-start.ps1
```

This launcher:
- Creates Python virtual environment if needed
- Installs all dependencies automatically
- Launches all three services with labeled log output
- Monitors processes and allows clean shutdown with Ctrl+C

All log lines are prefixed with their component: `[agent]`, `[bridge]`, or `[tunnel]`.

## Alternative - Manual Three-Terminal Startup

For debugging or development, you can launch components separately:

### Terminal 1: Local Agent

```powershell
cd c:\AI-SMS-Agent\agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787
```

**Wait for:** `Uvicorn running on http://127.0.0.1:8787`

---

### Terminal 2: SMS Bridge

```powershell
cd c:\AI-SMS-Agent\sms-bridge
npm start
```

**Wait for:** `Bridge listening on port 34567`

---

### Terminal 3: Cloudflare Tunnel

```powershell
cloudflared tunnel --url http://localhost:34567
```

**Expected:** Setup or status displayed.

---

## System Health Checks

### Check Agent Health

```powershell
curl.exe http://127.0.0.1:8787/health
```

**Expected response:**
```
{"status":"ok"}
```

---

### Check Bridge Health

```powershell
curl.exe http://127.0.0.1:34567/health
```

**Expected response:**
```json
{"status": "ok"}
```

---

### Check Cloudflare Tunnel Status

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'cloudflared' } | Select-Object ProcessId, Name
```

**Expected output:**
```
cloudflared process is running and printing an active `https://...trycloudflare.com` URL in its terminal.
```

---

### Check Listening Ports

```powershell
netstat -ano | findstr LISTENING | findstr ":8787 :34567"
```

**Expected:** Should show agent on 8787 and bridge on 34567.

---

## Managing Services

### Stop Everything (Clean Shutdown)

1. **Terminal 3:** Press `Ctrl+C` in Cloudflare terminal
2. **Terminal 2:** Press `Ctrl+C` in Bridge terminal
3. **Terminal 1:** Press `Ctrl+C` in Agent terminal

**Wait 2-3 seconds between each stop.**

---

### Kill Everything (Force Shutdown)

Use if services won't stop cleanly:

```powershell
# Kill agent
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force

# Kill bridge/node
Get-Process | Where-Object {$_.ProcessName -eq "node"} | Stop-Process -Force

# Kill Cloudflare tunnel
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'cloudflared' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

---

### Restart Bridge Only

```powershell
# Terminal 2
Ctrl+C
npm start
```

---

### Restart Agent Only

```powershell
# Terminal 1
Ctrl+C
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787
```

---

### Restart Tunnel Only

```powershell
# Terminal 3
Ctrl+C
cloudflared tunnel --url http://localhost:34567
```

---

## Logs & Monitoring

### View Bridge Logs (Last 20 lines)

```powershell
Get-Content sms-bridge\logs\bridge.log -Tail 20
```

---

### View Agent Logs (Last 20 lines)

```powershell
Get-Content agent\workspace\logs\agent.log -Tail 20
```

---

### Follow Bridge Logs (Live)

```powershell
Get-Content -Path sms-bridge\logs\bridge.log -Wait
```

**Press `Ctrl+C` to exit.**

---

### Follow Agent Logs (Live)

```powershell
Get-Content -Path agent\workspace\logs\agent.log -Wait
```

---

### View Full Bridge Log

```powershell
notepad "$(pwd)\sms-bridge\logs\bridge.log"
```

---

### Clear Logs

```powershell
# Clear bridge log
Clear-Content sms-bridge\logs\bridge.log

# Clear agent log
Clear-Content agent\workspace\logs\agent.log
```

---

## Testing & Verification

## Troubleshooting - Frozen Desktop Startup

### Error: `Unable to configure formatter 'default'`

Symptom in packaged executable:

```
Failed to execute script 'main' due to unhandled exception:
Unable to configure formatter 'default'
AttributeError: 'NoneType' object has no attribute 'isatty'
```

Root cause:
- In frozen GUI startup, `sys.stderr`/`sys.stdout` may be unavailable.
- Uvicorn's default logging formatter path probes `isatty()` and crashes when stream objects are `None`.

Stabilized fix in code:
- File: `mashbak/desktop_app/agent_service.py`
- Change: in `_start_in_process`, set `uvicorn.Config(..., log_config=None, access_log=False)`.
- Result: packaged app no longer executes Uvicorn's formatter dictConfig path that triggers this crash.

Operator check:
1. Rebuild executable: `./mashbak/scripts/build-app.ps1 -Clean`
2. Launch `mashbak/dist/Mashbak.exe`
3. Confirm desktop opens and embedded agent starts without formatter errors.

Prevention note:
- Keep packaged GUI startup on `log_config=None` unless a custom stream-safe logging config is introduced and tested in frozen mode.

### Error Chain: `No module named 'runtime'` / `config` / `imaplib`

Symptom in packaged executable:

```
ModuleNotFoundError: No module named 'imaplib'
...
ModuleNotFoundError: No module named 'config'
...
ModuleNotFoundError: No module named 'runtime'
```

Root cause:
- Broad `except ImportError` fallback imports in startup/runtime modules masked the original error and cascaded into misleading module-not-found exceptions.
- Email tools imported `imaplib` at module import time; if unavailable in a given build, startup could fail instead of degrading gracefully.

Stabilized fix in code:
- Files: `mashbak/agent/runtime.py`, `mashbak/agent/agent.py`, `mashbak/agent/dispatcher.py`, `mashbak/desktop_app/main.py`
- Change: replace broad import fallback blocks with package-context import paths so real root-cause exceptions surface.
- File: `mashbak/agent/tools/builtin/email_tools.py`
- Change: guard `imaplib` import and return a tool-level error when IMAP support is unavailable instead of crashing app startup.
- File: `mashbak/scripts/build-app.ps1`
- Change: include hidden imports for `imaplib` and core `email` modules.

### Test Local SMS Endpoint (No Twilio)

Simulate an SMS locally:

```powershell
curl.exe -X POST http://127.0.0.1:34567/sms `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "Body=hello&From=%2B18005551234"
```

**Expected:** TwiML XML response.

---

### Test Agent Directly

Read a test file:

```powershell
$headers = @{
  "X-API-Key" = "your-api-key"
  "X-Request-Id" = "test-123"
}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -d '{"path":"inbox/test.txt"}'
```

---

### Test Twilio Webhook Connectivity

```powershell
curl.exe https://YOUR-CLOUDFLARE-URL.trycloudflare.com/sms
```

**Expected:** 405 error (method not allowed) - that's fine, it means the public URL works.

---

## Configuration Management

### Update Twilio Webhook

When your tunnel URL changes:

1. Get new URL:
   ```powershell
   cloudflared tunnel --url http://localhost:34567
   ```

2. Update `sms-bridge/.env`:
   ```
   PUBLIC_BASE_URL=https://YOUR-NEW-URL.trycloudflare.com
   ```

3. Restart bridge:
   ```powershell
   cd sms-bridge && npm start
   ```

4. Update Twilio Console webhook URL to: `https://YOUR-NEW-URL.trycloudflare.com/sms`

---

### Update API Key

If you need to change the API key:

1. Update `agent/.env`:
   ```
   AGENT_API_KEY=new-super-secret-key
   ```

2. Update `sms-bridge/.env`:
   ```
   AGENT_API_KEY=new-super-secret-key
   ```

3. Restart both services

---

### Enable AI Mode

1. Get OpenAI API key from https://platform.openai.com/api-keys

2. Add to `sms-bridge/.env`:
   ```
   OPENAI_API_KEY=sk-proj-your-key-here
   ```

3. Restart bridge:
   ```powershell
   cd sms-bridge && npm start
   ```

---

## Common Operations

### List Inbox Files

```powershell
Get-ChildItem agent\workspace\inbox\
```

Or via SMS:

```
run dir_inbox
```

---

### Create a Test File

```powershell
"Test content" | Out-File agent\workspace\inbox\test.txt
```

Or via SMS:

```
write inbox/test.txt :: Test content
```

---

### Read a File

```powershell
Get-Content agent\workspace\inbox\test.txt
```

Or via SMS:

```
read inbox/test.txt
```

---

### Delete a File

```powershell
Remove-Item agent\workspace\inbox\test.txt
```

---

## Troubleshooting Operations

### Agent Won't Start

```powershell
# Check if port is in use
netstat -ano | findstr 8787

# Check Python syntax
cd agent
python -m py_compile agent.py
```

---

### Bridge Won't Start

```powershell
# Check if port is in use
netstat -ano | findstr 34567

# Check Node syntax
cd sms-bridge
npm run check

# Check dependencies
npm ls
```

---

### No Reply from SMS

1. Check all three services running (health checks above)
2. Check Bridge logs for `incoming_sms` entry
3. Check Agent logs for matching `request_id`
4. See [Troubleshooting](legacy/TROUBLESHOOTING.md)

---

### Port Already in Use

If port conflict:

```powershell
# Find what's using the port
Get-Process | Where-Object {$_.Id -eq (Get-NetTCPConnection | Where-Object LocalPort -eq 34567).OwningProcess}

# Or change BRIDGE_PORT in sms-bridge/.env
BRIDGE_PORT=34568
```

---

## Scheduled Operations

### Daily Startup

```powershell
# Terminal 1
cd c:\AI-SMS-Agent\agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787

# Terminal 2 (after Terminal 1 is ready)
cd c:\AI-SMS-Agent\sms-bridge
npm start

# Terminal 3 (after Terminal 2 is ready)
cloudflared tunnel --url http://localhost:34567
```

---

### Weekly Maintenance

1. Review logs for errors:
   ```powershell
   Get-Content sms-bridge\logs\bridge.log
   Get-Content agent\workspace\logs\agent.log
   ```

2. Check available disk space for logs

3. Rotate logs if they're getting large:
   ```powershell
   Clear-Content sms-bridge\logs\bridge.log
   Clear-Content agent\workspace\logs\agent.log
   ```

4. Test connectivity:
   ```powershell
   curl.exe http://127.0.0.1:8787/health
   curl.exe http://127.0.0.1:34567/health
   ```

---

### Monthly Security Review

See [Security Hardening](SECURITY-HARDENING.md).

---

## Reference Tables

### Port Usage

| Service | Port | Purpose |
|---------|------|---------|
| Agent | 8787 | Local FastAPI |
| Bridge | 34567 | Local Express server |
| Tunnel | (any) | Cloudflare tunnel |

### Environment Variables by Service

| Variable | Agent | Bridge | Notes |
|----------|-------|--------|-------|
| AGENT_API_KEY | ✅ Required | ✅ Required | Must match |
| AGENT_URL | ❌ | ✅ Required | - |
| AGENT_WORKSPACE | ✅ Optional | ❌ | - |
| BRIDGE_PORT | ❌ | ✅ Required | - |
| PUBLIC_BASE_URL | ❌ | ✅ Required | - |
| OPENAI_API_KEY | ❌ | ✅ Optional | AI mode |

### Log Locations

| Log | Location | Service |
|-----|----------|---------|
| Bridge | `sms-bridge/logs/bridge.log` | Node.js |
| Agent | `agent/workspace/logs/agent.log` | Python |

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [Quick Start](QUICK-START.md), [Troubleshooting](legacy/TROUBLESHOOTING.md)
