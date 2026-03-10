# Best Practices

Operational and development best practices.

---

## Daily Operations

### 1. Startup Routine

**Recommended Method (Unified Launcher):**

```powershell
# Single command starts all three services
.\scripts\start-all.ps1

# Wait for labeled output showing all services running:
# [agent] Uvicorn running on...
# [bridge] Bridge listening on port 34567
# [tunnel] Your tunnel URL...

# Verify with health checks:
curl.exe http://127.0.0.1:8787/health
curl.exe http://127.0.0.1:34567/health
```

**Alternative Method (Manual Three-Terminal Startup):**

For debugging or development, you can launch components separately:

```powershell
# 1. Open 3 PowerShell terminals in VS Code

# Terminal 1:
cd C:\AI-SMS-Agent\agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787
# Wait for: "Uvicorn running on..."

# Terminal 2 (after Terminal 1 is ready):
cd C:\AI-SMS-Agent\sms-bridge
npm start
# Wait for: "Bridge listening on port 34567"

# Terminal 3 (after Terminal 2 is ready):
cloudflared tunnel --url http://localhost:34567
# Copy URL and ensure it matches PUBLIC_BASE_URL in sms-bridge/.env
```

---

### 2. Verify Twilio Webhook URL

Every few weeks (or after restart), check:

```powershell
# Start tunnel and get current public URL
cloudflared tunnel --url http://localhost:34567

# Check Twilio webhook
# Twilio Console → Phone Numbers → Your Number
# Verify webhook URL is: https://YOUR-URL.trycloudflare.com/sms
```

If URL changed:
1. Update `sms-bridge/.env`: `PUBLIC_BASE_URL=...`
2. Restart bridge
3. Update Twilio webhook

---

### 3. Monitor Health Throughout the Day

Quick health check every few hours:

```powershell
$agent = curl.exe -s http://127.0.0.1:8787/health | ConvertFrom-Json
$bridge = curl.exe -s http://127.0.0.1:34567/health | ConvertFrom-Json
$tunnel = "Confirm cloudflared terminal is running and URL matches PUBLIC_BASE_URL"

Write-Output @"
Agent:  $($agent.status)
Bridge: $($bridge.status)
Tunnel: $tunnel
"@
```

---

### 4. Shutdown Routine

**When you're done for the day:**

**If using unified launcher:**
```powershell
# Simple shutdown: Press Ctrl+C in the terminal running start-all.ps1
# The script automatically stops all services cleanly
```

**If using manual three-terminal startup:**
```powershell
# Clean shutdown in this order (wait 2 sec between each):

# Terminal 3
Ctrl+C

# Terminal 2
Ctrl+C

# Terminal 1
Ctrl+C
```

**Verify all stopped:**
```powershell
netstat -ano | findstr ":8787 :34567"
# Should show nothing (no results)
```

---

## Weekly Maintenance

### Day: Every Monday

```powershell
# 1. Check logs for errors
Get-Content sms-bridge\logs\bridge.log | Select-String "error\|failed\|rejected" -First 10

# 2. Check agent logs
Get-Content agent\workspace\logs\agent.log | Select-String "auth_failed\|invalid_path" -First 10

# 3. Check disk usage
(Get-ChildItem sms-bridge\logs -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
(Get-ChildItem agent\workspace\logs -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB

# 4. List workspace contents
Get-ChildItem agent\workspace\inbox -Count
Get-ChildItem agent\workspace\outbox -Count
```

---

### Clean Old Files (Optional)

If workspace is getting cluttered:

```powershell
# Archive old files to a backup folder
$archive = "C:\AI-SMS-Agent\agent\workspace\archive"
mkdir $archive -ErrorAction SilentlyContinue

# Move files older than 30 days
Get-ChildItem "C:\AI-SMS-Agent\agent\workspace\inbox" |
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
  Move-Item -Destination $archive

Get-ChildItem "C:\AI-SMS-Agent\agent\workspace\outbox" |
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
  Move-Item -Destination $archive
```

---

## Monthly Maintenance

### Day: First of Month

```powershell
# 1. Rotate API key (recommended but not required)
# Edit agent/.env
# Change AGENT_API_KEY to new random string

# Edit sms-bridge/.env
# Change AGENT_API_KEY to same new string

# Restart services

# 2. Check Twilio balance
# Twilio Console → Billing → Account Balance
# Ensure sufficient credits

# 3. Check OpenAI balance (if using AI)
# https://platform.openai.com/account/billing/overview
# Ensure sufficient credits

# 4. Archive and clear logs
Move-Item sms-bridge\logs\bridge.log "sms-bridge\logs\bridge.log.$(Get-Date -Format 'yyyyMMdd')"
New-Item sms-bridge\logs\bridge.log -ItemType File -Force

Move-Item agent\workspace\logs\agent.log "agent\workspace\logs\agent.log.$(Get-Date -Format 'yyyyMMdd')"
New-Item agent\workspace\logs\agent.log -ItemType File -Force
```

---

## Troubleshooting Best Practices

### When Something Breaks

**Do this in order:**

1. **Check all three health endpoints** (before anything else)
   ```powershell
   curl.exe http://127.0.0.1:8787/health
   curl.exe http://127.0.0.1:34567/health
   cloudflared tunnel --url http://localhost:34567
   ```

2. **Check the logs** (recent entries first)
   ```powershell
   Get-Content sms-bridge\logs\bridge.log -Tail 50 | ConvertFrom-Json | FL
   Get-Content agent\workspace\logs\agent.log -Tail 50 | ConvertFrom-Json | FL
   ```

3. **Identify the issue** by looking for:
   - `error` events
   - `rejected` events
   - `failed` events
   - Empty responses

4. **Fix the issue**
   - Wrong API key? Update both `.env` files
   - Port in use? Change `BRIDGE_PORT` or kill process
   - Twilio webhook wrong? Update `.env` and Twilio Console
   - Agent not running? Restart it
   - Bridge not running? Restart it
   - See [Troubleshooting](legacy/TROUBLESHOOTING.md)

5. **Verify the fix** with health checks and a test SMS

---

### Never Do This

❌ **Don't:**
- Commit API keys to git
- Paste secrets in chat/email
- Share `.env` files publicly
- Run agent/bridge as Administrator (unnecessary)
- Delete logs without backing up first
- Change port numbers without updating other configs
- Leave default API keys in production
- Put sensitive files in workspace without encryption

---

## Logging Best Practices

### What to Log

The bridge logs:
- ✅ All incoming SMS
- ✅ Twilio signature validation status
- ✅ Sender allowlist checks
- ✅ Agent API calls and results
- ✅ Errors and rejections

The agent logs:
- ✅ File read/write operations
- ✅ Command execution
- ✅ Authorization attempts
- ✅ Path validation checks

---

### How to Use Logs

**For debugging:**
1. Find the request ID
2. Search both logs for that ID
3. Follow the event chain
4. Identify where it failed

**For monitoring:**
1. Check logs daily
2. Look for error events
3. Note patterns (same error repeated?)
4. Address root cause

**For compliance:**
1. Keep logs for 30+ days
2. Archive old logs
3. Don't delete without reason
4. Review monthly for security

---

### When to Clear Logs

**Clear logs when:**
- File size exceeds 100 MB
- You've archived old entries
- You're testing (after documenting baseline)
- Monthly routine maintenance

**Never clear logs when:**
- Investigating an issue
- Within 30 days of deployment
- Without backing up first

---

## API Usage Best Practices

### Rate Limiting (Recommended Manual)

Without built-in rate limiting:
- Don't send more than 60 SMS/hour
- Monitor bridge logs for errors
- If overloaded, wait before retrying

---

### Error Handling

When calling agent API:
- Always check HTTP response code
- Log failed requests with full payload
- Retry failed requests after delay
- Don't retry forever (max 3 attempts)

---

### Testing

Before deploying:
1. Test with `hello` command
2. Test with `help` command
3. Test with `read` on existing file
4. Test with `write` on new file
5. Test with `run dir_inbox`
6. Test with natural language (if AI enabled)
7. Check logs for any errors

---

## File Management Best Practices

### Inbox/Outbox

**Best practices:**
- Keep file names simple (no special chars)
- Organize into subfolders if needed
- Archive old files monthly
- Use `.txt` extension for text files

**Structure example:**
```
inbox/
├── important/
│   ├── note-2025-03-01.txt
│   └── reminder-2025-03-08.txt
├── archive/
│   └── old-files/
└── current-notes.txt
```

---

### Size Limits

**Recommended limits:**
- Single file: < 10 MB (for SMS speed)
- Total workspace: < 1 GB (for performance)
- Path depth: < 5 levels (keep it simple)

---

## Code Quality

### When Customizing Agent

If you modify `agent.py`:

1. **Keep it simple** - Don't add complexity
2. **Add logging** - Log all new operations
3. **Test thoroughly** - Test locally first
4. **Validate paths** - Always check file paths
5. **Check auth** - Always verify API key
6. **Run syntax check** - `python -m py_compile agent.py`

---

### When Customizing Bridge

If you modify `sms-server.js`:

1. **Keep it simple** - Don't add complexity
2. **Add logging** - Log all new operations
3. **Test locally** - Test before deploying
4. **Handle errors** - Catch and log exceptions
5. **Validate input** - Never trust SMS content
6. **Run syntax check** - `npm run check`

---

## Performance Tips

### Optimize Agent Response Time

- Keep files small (< 1 MB)
- Avoid deep directory structures
- Don't store huge amounts of data in workspace
- Clean up old files regularly

### Optimize Bridge

- Limit AI rounds (AI_MAX_TOOL_ROUNDS=3-6)
- Use faster models if speed matters
- Cache frequently-accessed files

### Optimize Network

- Use Cloudflare Tunnel for encrypted public access
- Don't expose agent directly to internet
- Keep `cloudflared` updated

---

## Data Retention Policy

### Files to Keep

- ✅ Configuration (.env files, when new)
- ✅ Code (agent.py, sms-server.js)
- ✅ Documentation (this directory)
- ✅ Active workspace files
- ✅ Recent logs (30 days)

### Files to Delete

- ❌ Old logs (> 90 days)
- ❌ Temporary test files
- ❌ Backup of old config
- ❌ Duplicate files

### Files to Archive

- 📦 Logs (monthly)
- 📦 Old workspace files (yearly)
- 📦 Backups (keep latest 3)

---

## Disaster Recovery

### Backup Routine (Recommended)

Monthly backup:

```powershell
# 1. Backup configuration
Copy-Item agent\.env "backups\agent\.env.$(Get-Date -Format 'yyyyMMdd')"
Copy-Item sms-bridge\.env "backups\sms-bridge\.env.$(Get-Date -Format 'yyyyMMdd')"

# 2. Backup workspace
Copy-Item agent\workspace\ "backups\workspace.$(Get-Date -Format 'yyyyMMdd')" -Recurse

# 3. Keep 3 most recent backups
Get-ChildItem backups | Sort-Object LastWriteTime | Select-Object -First -3 |
  Remove-Item -Recurse
```

---

### Recovery Steps (If Something Breaks)

1. **Stop all services**
   ```powershell
   Ctrl+C in all three terminals
   ```

2. **Restore from backup**
   ```powershell
   Copy-Item "backups\sms-bridge\.env.20250301" sms-bridge\.env -Force
   Copy-Item "backups\agent\.env.20250301" agent\.env -Force
   ```

3. **Restart services** (follow startup routine)

4. **Verify everything works**
   - Health checks
   - Send test SMS
   - Check logs

---

## Emergency Procedures

### If Hacked / Compromised

1. **Immediately stop bridge**
   ```powershell
   Ctrl+C in bridge terminal
   ```

2. **Rotate API key**
   - Generate new key (see Monthly Maintenance)
   - Update both `.env` files
   - Restart services

3. **Investigate**
   - Check logs for unauthorized activity
   - Check workspace for unexpected files
   - Check Twilio for mysterious messages

4. **Prevent future**
   - Enable stricter sender allowlisting
   - Reduce API key exposure
   - Add extra security (see Security Hardening)

---

## Uptime & Reliability Tips

### The System is NOT Designed for 24/7 Uptime

- **Stops when you turn off your PC** (OK, that's expected)
- **Stops if your internet disconnects** (public tunnel dependency)
- **Stops if Twilio has outage** (external dependency)
- **Stops if service crashes** (need manual restart)

### To Improve Reliability

1. **Monitor regularly** - Check logs often
2. **Restart on schedule** - Weekly restart recommended
3. **Update regularly** - Keep dependencies current
4. **Test regularly** - Send test SMS weekly
5. **Backup regularly** - Monthly backups

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [RUNBOOK.md](RUNBOOK.md), [SECURITY-HARDENING.md](SECURITY-HARDENING.md), [Troubleshooting](legacy/TROUBLESHOOTING.md)
