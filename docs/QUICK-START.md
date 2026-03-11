# Quick Start (5 Minutes)

Get the AI SMS Agent running in under 5 minutes.

## Prerequisites

✅ Windows PC with Python and Node.js  
✅ Twilio account and SMS number  
✅ Cloudflare Tunnel (`cloudflared`) installed on this PC  
✅ (Optional) OpenAI API key for AI mode  

## Step 1: Configure Environment (2 min)

Create `sms-bridge/.env` from the template:

```
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=your-secret-key-here
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://YOUR-CLOUDFLARE-URL.trycloudflare.com
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_FROM_NUMBER=+15551234567
OPENAI_API_KEY=sk-... (optional)
```

Create `agent/.env` from the template:

```
AGENT_API_KEY=your-secret-key-here
AGENT_WORKSPACE=agent/workspace
```

## Step 2: Launch All Services (1 min)

From the repository root, run:

```powershell
.\scripts\dev-start.ps1
```

This single command will:
- Create the Python virtual environment if needed
- Install all Python and Node.js dependencies
- Launch the FastAPI agent (port 8787)
- Launch the SMS bridge (port 34567)
- Launch the Cloudflare tunnel with a public URL

Watch for the tunnel URL in the `[tunnel]` log output. It will look like:
```
[tunnel] https://abc-def-123.trycloudflare.com
```

## Step 3: Update Configuration with Tunnel URL (1 min)

1. Stop the launcher (Ctrl+C)
2. Copy the tunnel URL from the logs
3. Update `PUBLIC_BASE_URL` in `sms-bridge/.env` with that URL
4. Restart: `.\scripts\dev-start.ps1`

## Step 4: Update Twilio Webhook (1 min)

In Twilio Console, set your SMS number webhook to:

```
https://YOUR-CLOUDFLARE-URL.trycloudflare.com/sms
```

## Done! ✅

Send a text to your Twilio number. You should get a reply!

Try:

- `list` — See available commands
- `echo hello` — Test the connection

## Desktop App (No Terminal)

If you want a normal desktop app experience:

```powershell
.\scripts\build-app.ps1 -Clean
```

Then launch:

`dist\AISMSDesktop.exe`

Behavior:
- opens as a normal Windows app (no terminal window)
- starts the local agent automatically
- sends local chat requests through the same dispatcher/tool pipeline
- does not send SMS replies

## Alternative: Manual Startup

If you prefer to launch components separately (for debugging), see the original steps below.

### Manual Step 2: Start the Agent

```powershell
cd agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787
```

Expected: `Uvicorn running on http://127.0.0.1:8787`

### Manual Step 3: Start the Bridge

In a new terminal:

```powershell
cd sms-bridge
npm start
```

Expected: `Bridge listening on port 34567`

### Manual Step 4: Enable Public Access

In a new terminal:

```powershell
cloudflared tunnel --url http://localhost:34567
```

Use the public URL shown by `cloudflared` and set it in `sms-bridge/.env`.
- `hello` - connectivity test
- `help` - list commands
- `read inbox/test.txt` - read a file

## If It Doesn't Work

See [Troubleshooting Guide](legacy/TROUBLESHOOTING.md) or [FAQ](FAQ.md).

## Next Steps

- [Full Installation Guide](INSTALLATION.md)
- [SMS Commands Reference](COMMANDS.md)
- [Enable AI Mode](AI-INTEGRATION.md)
- [Security Hardening](SECURITY-HARDENING.md)
