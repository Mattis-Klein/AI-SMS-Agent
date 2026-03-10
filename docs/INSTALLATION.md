# Complete Installation Guide

Full step-by-step setup from scratch.

## System Requirements

- Windows 10 or later
- Python 3.9+ (with venv)
- Node.js 18+ (with npm)
- Cloudflare Tunnel (`cloudflared`) installed
- Administrator access for some steps

## Quick Note: Unified Launcher

After completing the setup steps below, you can launch the entire system with a single command:

```powershell
.\scripts\start-all.ps1
```

This unified launcher handles virtual environment creation, dependency installation, and launches all three services (agent, bridge, tunnel) automatically. The manual steps below are useful for understanding what happens under the hood and for troubleshooting.

## Step 1: Prerequisites & Dependencies

### 1.1 Python Virtual Environment

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install fastapi uvicorn python-dotenv
```

### 1.2 Node.js Dependencies

```powershell
cd sms-bridge
npm install
npm run check  # Verify syntax
```

## Step 2: Configure Local Agent

### 2.1 Create `.env` file

In `agent/` directory, create `.env`:

```
AGENT_API_KEY=dev-secret-key-change-this
AGENT_WORKSPACE=agent/workspace
```

**IMPORTANT**: Change `AGENT_API_KEY` to a random string. This must match the bridge.

### 2.2 Verify Agent Setup

```powershell
cd agent
.\.venv\Scripts\activate
python -m py_compile agent.py
curl.exe http://127.0.0.1:8787/health  # Should fail (not running yet)
```

## Step 3: Configure SMS Bridge

### 3.1 Create `.env` file

In `sms-bridge/` directory, create `.env`:

```
# Local agent connection
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=dev-secret-key-change-this

# Bridge settings
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://YOUR-CLOUDFLARE-URL.trycloudflare.com

# Twilio credentials (get from Twilio Console)
TWILIO_AUTH_TOKEN=your-auth-token
ALLOWED_SMS_FROM=+18005551234

# Optional: AI mode
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4.1-mini
```

### 3.2 Verify Bridge Setup

```powershell
cd sms-bridge
npm run check
```

Expected: No errors.

## Step 4: Setup Cloudflare Tunnel

### 4.1 Install cloudflared

Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

### 4.2 Start Tunnel

```powershell
cloudflared tunnel --url http://localhost:34567
```

### 4.3 Copy Public URL

```powershell
Copy the `https://...trycloudflare.com` URL printed by cloudflared.
```

Use that URL as your bridge public base URL.

### 4.4 Update `.env` with Public URL

Update `sms-bridge/.env`:

```
PUBLIC_BASE_URL=https://YOUR-CLOUDFLARE-URL.trycloudflare.com
```

## Step 5: Setup Twilio

### 5.1 Create Twilio Account

1. Go to https://www.twilio.com/console
2. Create a new account or use existing one
3. Get a phone number (SMS enabled)
4. Note the Auth Token (in Account Settings)

### 5.2 Configure Webhook

In Twilio Console, for your SMS number:

- **Incoming Messages Webhook**: `https://YOUR-CLOUDFLARE-URL.trycloudflare.com/sms`
- **Method**: POST

### 5.3 Update Bridge `.env`

Set `TWILIO_AUTH_TOKEN` and `ALLOWED_SMS_FROM`.

## Step 6: Test Local System (Without Twilio)

### 6.1 Start Agent

```powershell
cd agent
.\.venv\Scripts\activate
uvicorn agent:app --host 127.0.0.1 --port 8787
```

Wait for: `Uvicorn running on...`

### 6.2 Start Bridge (in new terminal)

```powershell
cd sms-bridge
npm start
```

Wait for: `Bridge listening on port 34567`

### 6.3 Test Agent

```powershell
$headers = @{"X-API-Key" = "dev-secret-key-change-this"}
curl.exe -X POST http://127.0.0.1:8787/read `
  -H "Content-Type: application/json" `
  -H @headers `
  -d '{"path":"inbox/test.txt"}'
```

Expected: Either `404` (file missing) or content.

### 6.4 Test Bridge ↔ Agent

```powershell
curl.exe -X POST http://127.0.0.1:34567/sms `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "Body=hello&From=%2B18005551234"
```

Expected: TwiML response in XML format.

## Step 7: Enable Public Access

### 7.1 Start Cloudflare Tunnel

In a new terminal:

```powershell
cloudflared tunnel --url http://localhost:34567
```

### 7.2 Verify Public Endpoint

```powershell
curl.exe https://YOUR-CLOUDFLARE-URL.trycloudflare.com/sms
```

Expected: Connection works (or 405 status - that's fine for now).

## Step 8: Test End-to-End with Twilio

### 8.1 Have All Three Running

- Terminal 1: Agent (`uvicorn agent:app...`)
- Terminal 2: Bridge (`npm start`)
- Terminal 3: Tunnel (`cloudflared tunnel --url ...`)

### 8.2 Send SMS

Send any SMS to your Twilio number.

### 8.3 Check Logs

**Bridge log**:
```powershell
Get-Content sms-bridge/logs/bridge.log -Tail 20
```

**Agent log**:
```powershell
Get-Content agent/workspace/logs/agent.log -Tail 20
```

### 8.4 Verify Reply

You should receive a reply SMS within 10 seconds.

## Step 9 (Optional): Enable AI Mode

Edit `sms-bridge/.env` and add:

```
OPENAI_API_KEY=sk-your-real-key
```

Then restart the bridge. Natural-language messages will now be AI-powered.

## Step 10: Secure Your Setup

Read [Security Hardening](SECURITY-HARDENING.md) and apply recommendations:

- Change all default keys
- Enable Twilio signature validation (already in `.env`)
- Verify your phone number in `ALLOWED_SMS_FROM`
- Consider Cloudflare Access or additional gateway restrictions for production

---

## Troubleshooting Installation

| Issue | Solution |
|-------|----------|
| Python not found | Install Python 3.9+, add to PATH |
| Node not found | Install Node.js 18+, restart terminal |
| `pip install` fails | Run `python -m pip install --upgrade pip` first |
| Port already in use | Change `BRIDGE_PORT` or kill conflicting process |
| cloudflared not found | Install cloudflared or add it to PATH |
| Twilio webhook unreachable | Ensure `PUBLIC_BASE_URL` matches current cloudflared URL |

## Next Steps

1. [Quick Start](QUICK-START.md) - Fast verification
2. [Runbook](RUNBOOK.md) - Daily operations
3. [SMS Commands](COMMANDS.md) - What you can do
4. [Troubleshooting](legacy/TROUBLESHOOTING.md) - If something breaks

---

**Installation Time**: ~30 minutes  
**Support**: See [FAQ](FAQ.md)
