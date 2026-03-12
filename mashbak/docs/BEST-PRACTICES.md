# Best Practices

## Runtime Operations

- Keep mashbak/.env.master as single runtime config source.
- Restart sms_bridge after changing bridge or sender access-control variables.
- Keep backend and bridge logs under periodic review.

## Security

- Never commit .env.master.
- Rotate AGENT_API_KEY and Twilio credentials when needed.
- Validate sender access-control configuration before exposing public webhook.
- Verify redaction coverage whenever new debug fields are added.

## Development

- Add tests for every interpreter or context behavior change.
- Keep tool behavior deterministic; do not move logic into bridge or desktop.
- Preserve compatibility behavior only when explicitly labeled.

## Validation Workflow

- python -m pytest -q
- cd mashbak/sms_bridge; npm test
- python -m py_compile sweep for changed Python files
- smoke check: backend /health, bridge /health, desktop --ui-smoke

## Documentation Hygiene

- Update docs in same change set as behavior updates.
- Mark compatibility paths explicitly (example: POST /run).
- Remove stale command examples when endpoints/tooling change.
