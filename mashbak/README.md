# Mashbak Assistant

Mashbak is a desktop-first assistant with one shared backend reasoning engine.

- Desktop UI is transport and presentation only.
- SMS bridge is transport and access-control only.
- Tool execution runs only through backend interpreter, dispatcher, and tool registry.

## Run

From repository root:

```powershell
# Backend (FastAPI)
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787

# SMS bridge
cd mashbak/sms-bridge
npm start

# Desktop UI
cd ..
python desktop_app/main.py
```

## Build Desktop Executable

```powershell
.\mashbak\scripts\build-app.ps1 -Clean
```

Output:
- `mashbak/dist/Mashbak.exe` for one-file mode (default)
- `mashbak/dist/Mashbak/` for one-dir mode (`-OneDir`)

## Configuration

Canonical configuration files:
- Runtime source: `mashbak/.env.master`
- Committed template: `mashbak/.env.master.example`

Create local runtime config:

```powershell
Copy-Item mashbak/.env.master.example mashbak/.env.master
notepad mashbak/.env.master
```

Config updates through chat use the same backend path as all requests and write to `mashbak/.env.master` via `set_config_variable`.

Accepted assignment styles include:

```text
EMAIL_PASSWORD = app-password
set MODEL_RESPONSE_MAX_TOKENS to 250
and password is app-password   (when continuing a config thread)
```

Reload behavior:
- Backend/OpenAI/email/runtime tuning values reload in-process.
- Bridge transport and access-control values are startup-loaded and require bridge restart.
- `AGENT_API_KEY` change requires callers to use the new key and typically restart active clients.

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for complete variable reference and restart details.
