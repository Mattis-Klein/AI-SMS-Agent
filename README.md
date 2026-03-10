# AI SMS Agent

AI SMS Agent lets you control safe, local actions on your computer from a flip phone by SMS.

## Architecture Overview

The system connects your flip phone to your computer through the following flow:

1. **SMS** → You send a text message from your flip phone
2. **Twilio** → Your Twilio number receives the message
3. **Cloudflare Tunnel** → Twilio forwards the webhook through a secure tunnel
4. **SMS Bridge** (Node.js) → Receives and validates the Twilio webhook
5. **FastAPI Agent** (Python) → Executes controlled commands on your local machine
6. **Response** → Results flow back through the bridge and Twilio to your phone

## Project Structure

- **`agent/`** — Python FastAPI agent that executes local commands
- **`sms-bridge/`** — Node.js Express server that handles Twilio webhooks
- **`scripts/`** — PowerShell launcher scripts for easy startup
- **`docs/`** — Complete project documentation and guides

## Quick Start

The entire system can now be launched with a single command:

```powershell
.\scripts\start-all.ps1
```

**What this script does:**

1. Checks if the Python virtual environment exists (creates it if needed)
2. Installs Python dependencies from `agent/requirements.txt`
3. Installs Node.js dependencies for the SMS bridge
4. Launches all three services with labeled log output:
   - `[agent]` — FastAPI server on port 8787
   - `[bridge]` — SMS bridge on port 34567
   - `[tunnel]` — Cloudflare tunnel exposing the bridge publicly
5. Monitors all processes and shuts down cleanly when you press Ctrl+C

All log output is labeled by component, making it easy to see which service each message comes from.

## Environment Files

Before first run, create local `.env` files from the templates:

- `agent/.env` (from `agent/.env.example`)
- `sms-bridge/.env` (from `sms-bridge/.env.example`)

Only the `.env.example` templates are tracked in the repository. Your actual `.env` files with secrets remain local.

## Alternative: Manual Startup

If you prefer to launch components individually, use these helper scripts:

```powershell
.\scripts\start-agent.ps1
.\scripts\start-bridge.ps1
.\scripts\start-cloudflare.ps1
```

Or run the manual commands:

```powershell
# Agent
cd agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn agent:app --host 127.0.0.1 --port 8787

# Bridge
cd ..\sms-bridge
npm install
npm start

# Cloudflare tunnel
cloudflared tunnel --url http://localhost:34567
```

## Notes

- Bridge start command is defined in `sms-bridge/package.json` as `start: node sms-server.js`.
- Runtime artifacts such as `node_modules`, `__pycache__`, logs, and `.venv` are hidden from normal VS Code Explorer view.
- See `docs/INDEX.md` for full documentation.
