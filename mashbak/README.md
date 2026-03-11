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

### Via Chat (Recommended for Users)

Most configuration variables can be set directly through the assistant chat:

```
User:  EMAIL_ADDRESS = myemail@gmail.com
Assistant: ✓ Configuration updated: EMAIL_ADDRESS has been set.

User:  EMAIL_PASSWORD = app-password
Assistant: ✓ Configuration updated: EMAIL_PASSWORD has been set.
```

Variables are validated, persisted to `mashbak/agent/.env`, and take effect on next tool execution.

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for the complete list of chat-configurable variables.

### Via .env File (Developers)

Edit `mashbak/agent/.env` and `mashbak/sms-bridge/.env` directly:

```powershell
# Copy default
cp mashbak/agent/.env.example mashbak/agent/.env

# Edit with your values
notepad mashbak/agent/.env
```

See [ENVIRONMENT.md](docs/ENVIRONMENT.md) for all variables and their meanings.
