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
- **SMS bridge** (Node.js) via its master env loader at startup
- **Desktop** indirectly through backend API calls

### Configuration Policy

Mashbak now uses a **master-only** configuration model.

- Single source of truth: `mashbak/.env.master`
- Chat updates write to `mashbak/.env.master`
- Runtime services (agent, desktop flow, bridge) read from `mashbak/.env.master`
- Process environment variables can still override values when explicitly set in the shell

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for all variables and their meanings.
