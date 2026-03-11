# Development Guide

## Architecture Constraints

Do not violate these boundaries:
- desktop_app stays UI-only
- agent stays the single reasoning engine
- tools execute through interpreter + dispatcher + registry
- sms-bridge stays transport and access-control only

## Local Dev Loop

From mashbak root:

```powershell
python -m pytest -q
cd sms-bridge
npm test
```

Run backend:

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

Run desktop:

```powershell
python desktop_app/main.py
```

Run bridge:

```powershell
cd sms-bridge
npm start
```

## Adding Or Updating A Tool

1. Implement tool in agent/tools/builtin/.
2. Register in agent/tools/builtin/__init__.py.
3. Keep argument validation strict in tool.validate_args().
4. Ensure tool output is deterministic and safe for assistant wrapping.
5. Add regression tests under mashbak/tests/.

## Updating Interpreter Behavior

- Keep mappings deterministic and test-backed.
- Preserve config-through-chat parsing for both assignment and natural language forms.
- Preserve follow-up context behavior through session_context fields.

## Logging And Redaction

- Use agent/redaction.py for backend trace/log sanitization.
- Use sms-bridge/redaction.js for bridge sanitization.
- Never add raw secret values to logs or debug surfaces.

## Compatibility Behavior

- /run endpoint remains for compatibility and forwards to /execute.
- Alias env names (IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS) remain supported as compatibility fields.

## Packaging

Desktop packaging script:

```powershell
.\scripts\build-app.ps1 -Clean
```

Outputs Mashbak executable under dist/.
