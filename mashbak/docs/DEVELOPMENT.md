# Development Guide

## Architecture Constraints

Do not violate these boundaries:
- desktop_app stays UI-only
- agent stays the single reasoning engine
- tools execute through interpreter + dispatcher + registry
- sms_bridge stays transport and access-control only

For control-board features:

- Add operational state endpoints in backend (`agent/agent.py`) and consume them from desktop client.
- Do not mutate runtime policy/config directly from desktop file writes.
- Keep forms as UI adapters to backend-owned config/state updates.

## Local Dev Loop

From repository root:

```powershell
python -m pytest -q mashbak/tests
cd mashbak/sms_bridge
npm test
```

Desktop smoke tests:

```powershell
python desktop_app/main.py --ui-smoke
python desktop_app/main.py --service-smoke-test
```

Run backend:

```powershell
python -m uvicorn agent.agent:app --app-dir mashbak --host 127.0.0.1 --port 8787
```

Run desktop:

```powershell
python mashbak/desktop_app/main.py
```

Run bridge:

```powershell
cd mashbak/sms_bridge
npm start
```

## Adding Or Updating A Tool

1. Implement tool in mashbak/agent/tools/builtin/.
2. Register in mashbak/agent/tools/builtin/__init__.py.
3. Keep argument validation strict in tool.validate_args().
4. Ensure tool output is deterministic and safe for assistant wrapping.
5. Add regression tests under mashbak/tests/.

## Updating Interpreter Behavior

- Keep mappings deterministic and test-backed.
- Preserve config-through-chat parsing for both assignment and natural language forms.
- Preserve follow-up context behavior through session_context fields.
- Keep extractor binding pattern-specific (tool name alone is not enough when multiple regexes map to the same tool).
- Follow-up actions like `delete that file` must resolve from execution-backed context (`last_result=success` + path state), not guesses.

## Filesystem Mutation Safety

- Creation/deletion tools must perform post-execution verification before returning success.
- Assistant success wording for filesystem changes must be grounded in tool result data only.
- If verification fails, assistant must state failure and avoid completion claims.

## Desktop UI Response Rendering

- Exactly one assistant completion should be rendered per send cycle.
- Pending placeholder replacement must remove the pending block in-place to avoid duplicate timestamp artifacts.
- Debug/status details should reflect the current request trace (`assistant_response_source`, selected tool, execution status).

## Logging And Redaction

- Use mashbak/agent/redaction.py for backend trace/log sanitization.
- Use sms_bridge/redaction.js for bridge sanitization.
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
