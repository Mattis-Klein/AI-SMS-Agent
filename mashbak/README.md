# Mashbak Assistant

Mashbak is the current production assistant in this repository.

- Desktop-first local application
- Optional SMS bridge for remote transport
- Shared backend runtime for both desktop and SMS inputs

## Run

```powershell
# Agent
cd mashbak/agent
python -m uvicorn agent:app --host 127.0.0.1 --port 8787

# SMS bridge
cd mashbak/sms-bridge
npm start

# Desktop UI
python mashbak/desktop_app/main.py
```

## Build

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

## Configuration

### Single Master Configuration File

All system configuration is now centralized in a single file for easy inspection and management:

```
mashbak/.env.master
```

This file contains all variables for desktop, backend, email, SMS bridge, and Twilio integration.

**Setup:**
1. Copy the template: `cp mashbak/.env.master.example mashbak/.env.master`
2. Fill in your values
3. The file is automatically loaded by both Python and Node services

### Via Chat (Recommended for Users)

Configure variables directly through assistant chat:

```
User:  EMAIL_ADDRESS = myemail@gmail.com
Assistant: ✓ Configuration updated: EMAIL_ADDRESS has been set.

User:  EMAIL_PASSWORD = app-password
Assistant: ✓ Configuration updated: EMAIL_PASSWORD has been set.
```

Variables are validated, persisted to `mashbak/.env.master`, and take effect on next tool execution.

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for the complete list of chat-configurable variables.

### Via Master Config File (Developers)

Edit `mashbak/.env.master` directly:

```powershell
# Copy template
cp mashbak/.env.master.example mashbak/.env.master

# Edit with your values
notepad mashbak/.env.master
```

The master config is loaded by:
- **Python backend** via `ConfigLoader` at startup
- **SMS bridge** (Node.js) via dotenv at startup
- **Desktop** indirectly through backend API calls

### Legacy .env Files (Deprecated)

Old per-component `.env` files (`agent/.env`, `sms-bridge/.env`) are still supported as **local overrides** for development:
- Master config loaded first
- Local `.env` values override master if needed
- .gitignore prevents accidental commits of secrets

```powershell
# Copy default
cp mashbak/agent/.env.example mashbak/agent/.env

# Edit with your values
notepad mashbak/agent/.env
```

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for all variables and their meanings.
