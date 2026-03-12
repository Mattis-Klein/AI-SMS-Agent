# Mashbak Assistant

Mashbak is a desktop-first assistant with one shared backend reasoning engine.

- Desktop UI is transport and presentation only.
- SMS bridge is transport and access-control only.
- Tool execution runs only through backend interpreter, dispatcher, and tool registry.

Bucherim is now implemented as a separate SMS assistant flow inside this project:
- Destination Twilio number: +18772683048
- Bridge routing stays transport-only and forwards Bucherim payloads to backend endpoint /bucherim/sms
- Backend module `assistants/bucherim/service.py` owns membership gating, per-user logs, and conversational behavior

## Run

From repository root:

```powershell
# Backend (FastAPI)
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787

# SMS bridge
cd mashbak/sms_bridge
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

Bucherim-specific behavior:
- allowlist and responses are configured in `mashbak/assistants/bucherim/config.json`
- per-user Bucherim logs are stored in `mashbak/data/users/bucherim/`
- pending join requests are stored in `mashbak/data/users/bucherim/pending_requests.jsonl`
- admin approval utility: `mashbak/scripts/approve-bucherim-member.ps1`

## Filesystem Action Grounding

Mashbak now enforces hard grounding for filesystem actions in backend runtime:

- Action completion language is allowed only after a real successful tool execution.
- If no tool is selected, validation is skipped, or execution fails, Mashbak will not claim changes were applied.
- Successful filesystem mutation tools must return a resolved verified path (`created_path` for create, `deleted_path` for delete).
- Filesystem tools now verify effects post-execution (create confirms exists, delete confirms missing) before success is reported.

Examples that map to concrete backend tools:

```text
create a folder on my desktop called TripPack
create a new file on my desktop called Mashbak
make a file on the desktop called todo
create a file named notes.txt
add a file in that folder with all 50 states
put a file in it
delete that file
```

Context follow-ups are resolved from last verified action state (session memory only, reset on restart):

```text
where is it?
did you create it?
add states to that folder
create a file named states in that folder
delete that file
```

If no prior successful filesystem action exists in the current session, follow-ups like "that folder" or "delete that file" trigger clarification instead of guessing a path.

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for complete variable reference and restart details.
