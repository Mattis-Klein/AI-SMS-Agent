# FAQ - Frequently Asked Questions

Common questions and quick answers.

## General / Getting Started

### Q: What is this project?
**A:** An SMS bridge that connects a Twilio phone number to a local AI agent on your PC. Text commands to control files and programs, with optional natural language AI.

---

### Q: Do I need a flip phone?
**A:** No! Any phone that can send SMS works. Flip phones, smartphones, anything. The bridge is designed to be simple and universal.

---

### Q: How much does it cost?
**A:** 
- Twilio SMS: ~$0.01-0.03 per message
- Cloudflare Tunnel: free quick tunnels available
- OpenAI (optional): ~$0.005 per message if AI enabled
- **Total**: ~$1-2/month if you use it lightly

---

### Q: Is this secure?
**A:** It has basic security (API keys, sender allowlisting, path isolation), but should not be exposed to untrusted networks without hardening. See [Security Hardening](SECURITY-HARDENING.md).

---

### Q: Can I use this for production?
**A:** Not recommended yet. It's functional but lacks rate limiting, approval workflows, and advanced security. Good for personal use or learning.

---

## Installation & Setup

### Q: What OS does this run on?
**A:** Windows (primary). Could support Mac/Linux with modifications to Python/Node/shell scripts.

---

### Q: Do I need Node.js and Python?
**A:** Yes. Python for the agent, Node.js for the SMS bridge.
- Python 3.9+: https://www.python.org
- Node.js 18+: https://nodejs.org

---

### Q: I get "Python not found" error.
**A:** 
1. Install Python from https://www.python.org
2. Make sure to check "Add Python to PATH" during install
3. Restart your terminal or VS Code
4. Test: `python --version`

---

### Q: I get "npm: command not found"
**A:**
1. Install Node.js from https://nodejs.org
2. Restart your terminal
3. Test: `npm --version`

---

### Q: Do I need all three terminals running?
**A:** The system has three components that must all run simultaneously:
1. **Agent** (Python/FastAPI) - handles file/command operations
2. **Bridge** (Node.js/Express) - receives SMS from Twilio
3. **Tunnel** (Cloudflare Tunnel) - makes bridge publicly accessible

**Recommended:** Use the unified launcher which runs all three in a single terminal:
```powershell
.\scripts\dev-start.ps1
```

The launcher handles everything automatically and provides labeled log output. Alternatively, you can run each component in a separate terminal manually (see [Runbook](RUNBOOK.md)).

---

### Q: A port is already in use
**A.**
Change `BRIDGE_PORT` in `mashbak/.env.master`:

```env
BRIDGE_PORT=34568
```

Then restart bridge and update tunnel/Twilio webhook accordingly.

---

## Configuration

### Q: Where are the `mashbak/.env.master` file?
**A:** Two locations:
- `mashbak/.env.master` - Agent config
- `mashbak/.env.master` - Bridge/Twilio config

---

### Q: What if I lose my `mashbak/.env.master` file?
**A:** 
- Both directories have `.env.example` templates
- Copy the example: `copy .env.master.example .env.master`
- Fill in your secrets again

---

### Q: How do I get my Cloudflare URL?
**A:**
```powershell
cloudflared tunnel --url http://localhost:34567
```

Use the printed `https://...trycloudflare.com` URL.

---

### Q: How do I get my Twilio Auth Token?
**A:**
1. Go to https://www.twilio.com/console
2. Click your account (top right)
3. Settings
4. Copy "Auth Token"

---

### Q: What if my tunnel URL changes?
**A:** It can change if your machine restarts or you reconnect. If it does:

1. Start tunnel and get new URL: `cloudflared tunnel --url http://localhost:34567`
2. Update `mashbak/.env.master`: `PUBLIC_BASE_URL=...`
3. Update Twilio webhook in console: `https://NEW-URL.trycloudflare.com/sms`
4. Restart bridge

---

## Running & Operations

### Q: How do I know if everything is running?
**A:** Health check all three services:

```powershell
curl.exe http://127.0.0.1:8787/health  # Agent
curl.exe http://127.0.0.1:34567/health # Bridge
cloudflared tunnel --url http://localhost:34567  # Tunnel (prints URL)
```

All should return OK or "Running".

---

### Q: I don't see anything happen when I send an SMS
**A:** Check in this order:

1. **Is everything running?**
   - Check health endpoints above
   - Check if you have 3 terminals with running services

2. **Did Twilio receive the SMS?**
   - Twilio Console → Messages
   - Do you see an inbound message?

3. **Is your phone number allowed?**
   - Check `SMS_ACCESS_REQUEST_NUMBERS` in `mashbak/.env.master`
   - Is your phone number there?

4. **Check the logs**
   - Bridge: `Get-Content sms-bridge\logs\bridge.log -Tail 20`
   - Agent: `Get-Content agent\workspace\logs\agent.log -Tail 20`
   - Look for your request ID

See full guide: [Troubleshooting](legacy/TROUBLESHOOTING.md)

---

### Q: My agent won't start
**A:**
```powershell
# Check Python syntax
cd agent
python -m py_compile agent.py

# Check if 8787 is in use
netstat -ano | findstr 8787

# Try using python.exe explicitly
python.exe -m uvicorn agent:app --host 127.0.0.1 --port 8787
```

---

### Q: My bridge won't start
**A:**
```powershell
# Check Node syntax
cd sms-bridge
npm run check

# Check if 34567 is in use
netstat -ano | findstr 34567

# Check npm dependencies
npm ls
npm install  # Reinstall if missing
```

---

### Q: The Funnel keeps disconnecting
**A:**
- Funnel may disconnect if your network changes or PC sleeps
- Run in terminal: `cloudflared tunnel --url http://localhost:34567`
- Copy the printed public URL and set `PUBLIC_BASE_URL`
- Or just restart: `Ctrl+C` and run again

---

## SMS Commands

### Q: What commands can I send?
**A:** See [SMS Commands Reference](COMMANDS.md).

Quick ones:
- `hello` - test
- `help` - list all commands
- `read inbox/file.txt` - read a file
- `write inbox/file.txt :: content` - create a file
- Or natural language if AI is enabled

---

### Q: Can I send very long messages?
**A:** 
- SMS limit: 160 characters per message
- Responses are also limited
- For longer content, use multiple messages or create files locally

---

### Q: What if my file command doesn't work?
**A:** Check:
- File path is correct (use `run dir_inbox` to list)
- File exists (for `read`, not `write`)
- Path is in `inbox/` or `outbox/`
- No special characters in path

---

### Q: Can the AI access my Google/Amazon accounts?
**A:** Not yet. AI can only:
- Read/write files in workspace
- Run pre-approved commands

Would need custom integration (not yet built).

---

## Logs & Debugging

### Q: Where are the logs?
**A:** Two log files:
- `sms-bridge/logs/bridge.log` - SMS events
- `agent/workspace/logs/agent.log` - File operations

---

### Q: How do I read JSON logs?
**A:** 
```powershell
# Pretty print last entry
Get-Content sms-bridge\logs\bridge.log -Tail 1 | ConvertFrom-Json | Format-List
```

---

### Q: Logs are getting too big
**A:**
```powershell
# Clear them
Clear-Content sms-bridge\logs\bridge.log
Clear-Content agent\workspace\logs\agent.log

# Or set auto-rotation in mashbak/.env.master
BRIDGE_LOG_MAX_BYTES=1000000
```

---

### Q: How do I find my request in the logs?
**A:** Bridge logs include `request_id`. Search for it:
```powershell
Select-String "request-id-here" sms-bridge\logs\bridge.log
```

---

## Twilio

### Q: How do I get a Twilio phone number?
**A:**
1. Create account: https://www.twilio.com/console
2. Buy a number (usually $1/month)
3. Enable SMS
4. Note the number and auth token

---

### Q: SMS sent but no reply
**A:** Usually Twilio issue:
1. Check Twilio Console → Messages → that message
2. Look for "outbound" message to your phone
3. Check status (if shows "failed", see error code)
4. Common: Error 30032 = verify your number with Twilio

---

### Q: How do I update the webhook URL?
**A:**
1. Twilio Console → Phone Numbers
2. Select your SMS number
3. Edit Messaging section
4. Change webhook URL
5. Save

The URL should be: `https://YOUR-CLOUDFLARE-URL.trycloudflare.com/sms`

---

### Q: Can I use Twilio without signature validation?
**A:** Yes, but not recommended:
```env
TWILIO_AUTH_TOKEN=
```

But then any SMS from any URL could hit your bridge. Use sender allowlisting instead.

---

### Q: My number isn't verified
**A:** If Twilio won't send replies:
1. Twilio Console → Account
2. Verify your phone number
3. Wait a few minutes
4. Try again

---

## AI Mode

### Q: Is AI enabled by default?
**A:** No. You need to set `OPENAI_API_KEY` in `mashbak/.env.master`.

Without it, only fixed commands work.

---

### Q: How much does AI cost?
**A:** Depends on model. See [AI Integration Guide](AI-INTEGRATION.md).

Roughly: $0.001 - $0.10 per message

---

### Q: How do I get an OpenAI API key?
**A:**
1. Go to https://platform.openai.com
2. Create account
3. API keys section
4. Create new key
5. Copy it to `mashbak/.env.master`: `OPENAI_API_KEY=sk-...`

---

### Q: What if I run out of API credits?
**A:** 
- Free trial: $5 limit
- After that: Need paid account
- Go to https://platform.openai.com/account/billing/overview

---

### Q: Can I use a different AI provider?
**A:** Currently OpenAI only. Could add Claude, Gemini later.

---

### Q: AI responses are wrong
**A:** Tips:
- Be more specific with your message
- Use simpler language
- Remember: AI only has access to files and dir commands

---

## Security

### Q: Is my data safe?
**A:** 
- Local files stay on your PC (never sent to cloud)
- SMS messages go through Twilio (use secure auth)
- Workspace is isolated (filespath checks)
- But: Twilio can see message content; use HTTPS

---

### Q: Should I change my API key?
**A:** 
- Yes, change from default before production use
- If you shared/exposed the key, regenerate it
- the `mashbak/.env.master` file must match

---

### Q: Can someone hack my PC through this?
**A:** Unlikely if:
- API key is strong (random string)
- You limit allowed senders to your number
- Workspace doesn't contain sensitive files
- You keep cloudflared updated

But nothing is 100% secure. See [Security Hardening](SECURITY-HARDENING.md).

---

### Q: Should I restrict IP addresses?
**A:** Best practice:
- Add only your phone's IP to Twilio webhook allowlist (if supported)
- Use sender allowlisting and Twilio signature validation
- Consider using VPN

---

## Troubleshooting

### Q: None of my SMS are working, where do I start?
**A:** 

1. Health check all three:
   ```powershell
   curl http://127.0.0.1:8787/health
   curl http://127.0.0.1:34567/health
   cloudflared tunnel --url http://localhost:34567
   ```

2. Check Twilio message history (did it arrive?)

3. Check bridge log: `Get-Content sms-bridge\logs\bridge.log -Tail 20`

4. Check agent log: `Get-Content agent\workspace\logs\agent.log -Tail 20`

5. See [Troubleshooting Guide](legacy/TROUBLESHOOTING.md)

---

### Q: I need more help
**A:** Check these docs in order:
1. [Troubleshooting](legacy/TROUBLESHOOTING.md) - step-by-step debug
2. [Logging Guide](LOGGING.md) - how to read logs
3. [Runbook](RUNBOOK.md) - operational commands
4. [Security Hardening](SECURITY-HARDENING.md) - if suspicious

---

### Q: How do I report a bug?
**A:** Check:
1. Logs for detailed error
2. Troubleshooting guide
3. This FAQ
4. [GitHub issues](https://github.com/your-username/AI-SMS-Agent) if available

---

## Still Stuck?

1. Read the relevant doc from [Documentation Index](INDEX.md)
2. Check the logs (they're very helpful)
3. Try restarting all services
4. Read [Troubleshooting](legacy/TROUBLESHOOTING.md)
5. Make sure your mashbak/.env.master file have all required fields

---

**Last Updated**: March 8, 2026  
**Version**: 1.0
