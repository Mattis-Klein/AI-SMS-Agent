# Security Hardening Guide

Advanced security practices beyond the baseline.

---

## Overview

The basic security is:
- API key authentication
- Sender allowlisting
- Workspace isolation
- Path validation

This guide adds layers on top for higher security.

---

## 1. API Key Management

### Current State

the `mashbak/.env.master` file use the same API key:
- `mashbak/.env.master`: `AGENT_API_KEY=...`
- `mashbak/.env.master`: `AGENT_API_KEY=...`

### Hardening: Rotate Keys Regularly

**Monthly security practice:**

```powershell
# 1. Generate new key
$newKey = [guid]::NewGuid().ToString()
Write-Output $newKey  # Copy this

# 2. Update the mashbak/.env.master file
# Edit: mashbak/.env.master
# AGENT_API_KEY=<paste-new-key>

# Edit: mashbak/.env.master
# AGENT_API_KEY=<paste-new-key>

# 3. Restart both services
# Terminal 1: Ctrl+C, restart agent
# Terminal 2: Ctrl+C, restart bridge

# 4. Test with: curl http://127.0.0.1:8787/health
```

---

### Hardening: Use Secrets Manager (Advanced)

For production, store keys in Windows Credential Manager:

```powershell
# Store secret
$cred = New-Object System.Management.Automation.PSCredential("agent-api-key", (ConvertTo-SecureString "your-secret-key" -AsPlainText -Force))
$cred | Export-Clixml "$HOME\Secrets\agent-api-key.xml"

# Retrieve in script
$cred = Import-Clixml "$HOME\Secrets\agent-api-key.xml"
$apiKey = $cred.GetNetworkCredential().Password
```

But for this project, `mashbak/.env.master` is OK if:
- `mashbak/.env.master` is never committed to git (check `.gitignore`)
- File permissions set to user-only (no others can read)

---

### Hardening: File Permissions

Ensure only your user can read `mashbak/.env.master`:

```powershell
# Remove inherited permissions
$path = "C:\AI-SMS-Agent\mashbak\\.env.master"
$acl = Get-Acl $path
$acl.SetAccessRuleProtection($true, $false)
Set-Acl $path $acl

# Grant only yourself
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
  [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
  "FullControl",
  "Allow"
)
$acl.AddAccessRule($rule)
Set-Acl $path $acl

# Verify
Get-Acl $path | Select-Object Owner, Access
```

---

## 2. Twilio Security

### Current State

- `TWILIO_AUTH_TOKEN` validates webhook signatures
- `SMS_ACCESS_REQUEST_NUMBERS` restricts sender numbers
- Both are checked before processing

### Hardening: Verify Twilio Signatures

Ensure signature validation is enabled:

```env
# In mashbak/.env.master
TWILIO_AUTH_TOKEN=your-actual-token-from-console

# NOT LIKE THIS (empty = disabled):
TWILIO_AUTH_TOKEN=
```

**Verify it's working:**
```powershell
# Check bridge logs for "signature_validated"
Get-Content data\logs\bridge.log | Select-String "signature_validated"
```

---

### Hardening: Strict Sender Allowlisting

Only allow your actual phone number:

```env
# Instead of blank or multiple numbers, use ONLY your number:
SMS_ACCESS_REQUEST_NUMBERS=+18005551234

# Check it's working:
# Send SMS from a different number - should be rejected
# Check logs: "sender_not_allowed"
```

**Verify:**
- Get your real phone number
- Set it in `SMS_ACCESS_REQUEST_NUMBERS`
- Test sending from different number (should fail)

---

### Hardening: Verify Your Twilio Number

If you get error 30032 in outbound SMS:

1. Twilio Console → Phone Numbers
2. Select your number
3. Verify it's SMS-capable
4. If Twilio shows "trial account", verify your phone:
   - Account → Settings
   - Add and verify personal number
   - Wait 24 hours for full verification

---

## 3. Network Security

### Current State

Bridge is exposed via Cloudflare Tunnel (encrypted HTTPS tunnel).

### Hardening: Restrict Tunnel Exposure

Prefer a named Cloudflare tunnel with access policies for long-term use.

```powershell
# Keep using sender allowlisting and Twilio signature validation.
```

---

### Hardening: HTTPS Only

Currently supports HTTPS through Cloudflare Tunnel (good).

**Avoid:**
- Don't disable your tunnel and expose bridge directly
- Don't run on public HTTP without auth

---

### Hardening: Firewall Rules

Close ports that shouldn't be accessible:

```powershell
# Allow only localhost to bridge (if not using Funnel):
New-NetFirewallRule -DisplayName "SMS Bridge - Localhost Only" `
  -Direction Inbound -LocalPort 34567 -Protocol TCP `
  -LocalAddress "127.0.0.1" -Action Allow

# Allow only localhost to agent:
New-NetFirewallRule -DisplayName "Agent - Localhost Only" `
  -Direction Inbound -LocalPort 8787 -Protocol TCP `
  -LocalAddress "127.0.0.1" -Action Allow
```

---

## 4. Workspace Isolation

### Current State

Agent only accesses `data/workspace/`. Outside paths are rejected.

### Hardening: Restrict Workspace Access

Make workspace read-only to others:

```powershell
$path = "C:\AI-SMS-Agent\mashbak\data\workspace"

# Remove inherited permissions
$acl = Get-Acl $path
$acl.SetAccessRuleProtection($true, $false)
Set-Acl $path $acl

# Your user: full access
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
  [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
  "FullControl",
  "ContainerInherit, ObjectInherit"
)
$acl.AddAccessRule($rule)
Set-Acl -Path $path -AclObject $acl
```

---

### Hardening: Scan Workspace for Sensitive Files

**Before deploying:**

```powershell
# Don't put passwords or keys in workspace!
Get-ChildItem "C:\AI-SMS-Agent\mashbak\data\workspace\" -Recurse |
  Select-String "password|apikey|secret|token" -List

# Better: Use separate "safe" folder for agent data
# Don't put your real passwords there
```

---

### Hardening: Encrypt Workspace (Advanced)

For highly sensitive files:

```powershell
# Enable BitLocker (Windows Pro/Enterprise/Education)
# Or use folder-level encryption:
cipher /e /s:"C:\AI-SMS-Agent\mashbak\data\workspace"
```

---

## 5. Logging & Monitoring

### Current State

Logs are written locally in plain JSON (readable).

### Hardening: Protect Logs

Make logs readable only by you:

```powershell
# Secure bridge logs
$path = "C:\AI-SMS-Agent\mashbak\data\logs"
$acl = Get-Acl $path
$acl.SetAccessRuleProtection($true, $false)
Set-Acl $path $acl

# Secure agent logs
$path = "C:\AI-SMS-Agent\mashbak\data\workspace\logs"
$acl = Get-Acl $path
$acl.SetAccessRuleProtection($true, $false)
Set-Acl $path $acl
```

---

### Hardening: Regular Log Audits

Set a calendar reminder:

**Weekly:**
- Check for unexpected errors in logs
- Look for sender_not_allowed entries (attempted hack?)
- Check auth_failed entries (wrong key tries?)

```powershell
# Check for suspicious activity
Get-Content data\logs\bridge.log | 
  ConvertFrom-Json | 
  Where-Object event_type -match "error|rejected|failed"
```

---

### Hardening: Archive Old Logs

Prevent logs from growing indefinitely:

```powershell
# Archive logs older than 30 days
$archiveDir = "C:\AI-SMS-Agent\mashbak\data\logs\archive"
mkdir $archiveDir -ErrorAction SilentlyContinue

Get-ChildItem "C:\AI-SMS-Agent\mashbak\data\logs\*.log" |
  Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
  Move-Item -Destination $archiveDir

# Clear current logs
Clear-Content "C:\AI-SMS-Agent\mashbak\data\logs\bridge.log"
```

---

## 6. OpenAI (AI Mode) Security

### Current State

OpenAI API key is stored in `mashbak/.env.master` and used for all AI requests.

### Hardening: Limit OpenAI Scope

If using OpenAI:

1. **Create dedicated API key** (not your main account key)
2. **Set usage limits** in OpenAI Console
3. **Monitor costs** weekly

```powershell
# Check OpenAI usage
Invoke-WebRequest -Uri "https://api.openai.com/v1/usage/summary" `
  -Headers @{"Authorization" = "Bearer sk-..."}
```

---

### Hardening: Rate Limit AI Requests

Not yet implemented in bridge, but you can:

```powershell
# Manually limit: Don't send more than 10 messages/day
# Monitor bridge logs for "ai_request" entries
Get-Content data\logs\bridge.log | 
  Select-String "ai_request" | 
  Measure-Object
```

---

### Hardening: Audit AI Decisions

AI logs what tools it calls:

```powershell
Get-Content data\logs\bridge.log | 
  ConvertFrom-Json | 
  Where-Object event_type -eq "ai_response"
```

Review periodically for unexpected behavior.

---

## 7. Operational Security (OpSec)

### Hardening: Change Default Passwords

Before going "live":

1. Change `AGENT_API_KEY` from `dev-secret-key`
2. Don't use the same key as examples online
3. Make it random: `[guid]::NewGuid().ToString()`

---

### Hardening: Don't Share Secrets

- Never paste API keys in chat/email
- Never commit `mashbak/.env.master` to git
- Check `.gitignore` contains `.env.master`

```powershell
# Verify .env.master is ignored
git status  # Should NOT show mashbak/.env.master
```

---

### Hardening: Separate Dev/Prod Keys

If you have multiple instances:

```env
# Development machine
AGENT_API_KEY=dev-key-abc123

# Production machine
AGENT_API_KEY=prod-key-xyz789
```

Never reuse the same key across environments.

---

### Hardening: Document Access

Keep a log of who has access:

```
Access Log:
- 2025-03-08: Enabled SMS bridge for personal use
- 2025-03-15: Changed API key (monthly rotation)
- 2025-04-01: Added Twilio sender allowlisting

Incidents:
- None recorded
```

---

## 8. Incident Response

### If You Think You Were Hacked

1. **Immediate:**
   - Stop bridge: `Ctrl+C` in bridge terminal
   - Check logs for suspicious activity
   - Note the timestamp

2. **Investigate:**
   - Check bridge logs for unauthorized senders
   - Check agent logs for invalid paths
   - Check Twilio message history

3. **Respond:**
   - Change API key (the `mashbak/.env.master` file)
   - Clear logs
   - Restart services
   - Monitor for 24 hours

4. **Prevent:**
   - Review sender allowlist
   - Check workspace for unexpected files
   - Verify Twilio signature validation is enabled

---

### If You Exposed API Key

1. **Immediately:**
   - Remove old key from the `mashbak/.env.master` file
   - Generate new key
   - Restart both services

2. **Prevent:**
   - Don't paste keys in chat, email, or public code
   - Use git pre-commit hooks to prevent accidental commit

---

## 9. Compliance & Best Practices

### Regular Security Review

**Monthly checklist:**

- [ ] API key still secret (check file permissions)
- [ ] Twilio signature validation enabled
- [ ] Allowed senders list still correct
- [ ] No unexpected files in workspace
- [ ] Logs cleaned and archived
- [ ] Services running as expected
- [ ] No recent errors in logs

---

### Annual Security Update

- [ ] Rotate API keys
- [ ] Update cloudflared
- [ ] Update Python and Node.js dependencies
- [ ] Review Twilio account settings
- [ ] Check for new security threats

---

## Recommendations by Use Case

### Personal Use (Recommended)

- ✅ Sender allowlisting (your phone only)
- ✅ Twilio signature validation
- ✅ Strong API key (not default)
- ✅ No highly sensitive files in workspace

### Small Team (Not Recommended)

- Would need: approval workflows, rate limiting, audit logs
- Current system lacks these
- Not suitable for multi-user

### Production (Not Recommended)

- Missing: rate limiting, approval flows, comprehensive logging
- Needs: load balancing, failover, monitoring
- Would require major rework

---

## Testing Security

### Test 1: Wrong API Key

```powershell
# Use wrong key - should be rejected
$headers = @{"X-API-Key" = "wrong-key"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"inbox/test.txt"}'

# Should see: "Unauthorized" or 401 error
```

---

### Test 2: Path Traversal

```powershell
# Try to access outside workspace - should be rejected
$headers = @{"X-API-Key" = "your-key"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -Headers $headers `
  -Body '{"path":"../../etc/passwd"}'

# Should see: "Invalid path" or 400 error
```

---

### Test 3: Wrong Sender

```powershell
# Send SMS from non-allowlisted number
# Should see "sender_not_allowed" in bridge logs
Get-Content data\logs\bridge.log | Select-String "sender_not_allowed"
```

---

### Test 4: Bad Twilio Signature

```powershell
# This is hard to test without modifying Twilio request
# But you can verify validation is enabled by checking logs

Get-Content data\logs\bridge.log | Select-String "signature_validated"
```

---

## Further Reading

- [SECURITY.md](legacy/SECURITY.md) - Baseline security
- [ENVIRONMENT.md](ENVIRONMENT.md) - Secret management
- [TROUBLESHOOTING.md](legacy/TROUBLESHOOTING.md) - Common issues
- [BEST-PRACTICES.md](BEST-PRACTICES.md) - Operational practices

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

Remember: No system is 100% secure. These hardening steps significantly improve security for personal/small-scale use. For production systems, additional infrastructure and specialized security review is needed.
