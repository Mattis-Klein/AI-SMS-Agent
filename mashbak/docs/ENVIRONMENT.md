# Environment Configuration

Mashbak uses one canonical runtime file:

- Runtime source: mashbak/.env.master
- Committed template: mashbak/.env.master.example

Chat-based config updates also persist to mashbak/.env.master.

## Loading Rules

- Backend loads from .env.master through ConfigLoader.
- Bridge loads from .env.master at startup.
- Shell environment variables can override values for the active process.

## Required Baseline Variables

- AGENT_API_KEY
- AGENT_URL
- BRIDGE_PORT
- PUBLIC_BASE_URL

## AI Variables

- OPENAI_API_KEY
- OPENAI_MODEL
- MODEL_RESPONSE_MAX_TOKENS

## Email Variables

Canonical names:
- EMAIL_IMAP_HOST
- EMAIL_IMAP_PORT
- EMAIL_USERNAME
- EMAIL_PASSWORD
- EMAIL_MAILBOX
- EMAIL_USE_SSL

Compatibility aliases accepted by validation and checks:
- IMAP_SERVER
- IMAP_PORT
- EMAIL_ADDRESS

## SMS Access-Control Variables

- SMS_OWNER_NUMBER
- SMS_ACCESS_REQUEST_NUMBERS
- SMS_ACCESS_REQUEST_RESPONSE
- SMS_ACCESS_REQUEST_KEYWORD
- HERSHY_NUMBER
- HERSHY_RESPONSE
- REJECTED_NUMBERS
- REJECTED_RESPONSE
- SMS_DENIAL_RESPONSE
- SMS_PHONE_NORMALIZATION_DIGITS

## Twilio Bridge Variables

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM_NUMBER

## Runtime And Logging Variables

- AGENT_WORKSPACE
- LOG_LEVEL
- DEBUG_MODE
- SESSION_CONTEXT_MAX_TURNS
- TOOL_EXECUTION_TIMEOUT
- BRIDGE_LOG_MAX_BYTES

## Live Reload Versus Restart

Reloaded in-process by backend runtime:
- OPENAI_API_KEY
- OPENAI_MODEL
- MODEL_RESPONSE_MAX_TOKENS
- SESSION_CONTEXT_MAX_TURNS
- TOOL_EXECUTION_TIMEOUT
- Email settings used by email tools

Bridge restart required after change:
- AGENT_URL
- BRIDGE_PORT
- PUBLIC_BASE_URL
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM_NUMBER
- SMS_OWNER_NUMBER
- SMS_ACCESS_REQUEST_NUMBERS
- SMS_ACCESS_REQUEST_RESPONSE
- SMS_ACCESS_REQUEST_KEYWORD
- HERSHY_NUMBER
- HERSHY_RESPONSE
- REJECTED_NUMBERS
- REJECTED_RESPONSE
- SMS_DENIAL_RESPONSE
- SMS_PHONE_NORMALIZATION_DIGITS

Coordinated restart/re-auth required:
- AGENT_API_KEY

set_config_variable tool responses include metadata:
- applied_live: true or false
- restart_required: component list (for example sms_bridge or agent_auth)

## Setup

```powershell
cd mashbak
Copy-Item .env.master.example .env.master
notepad .env.master
```

## Validation Checklist

- .env.master exists in mashbak root
- AGENT_API_KEY is non-empty
- AGENT_URL points to running backend
- BRIDGE_PORT is available
- PUBLIC_BASE_URL matches current tunnel URL
- Twilio values are set for production webhook validation and owner notifications
- Email values are set before email tools are used

## Troubleshooting

- Missing configuration error: set reported fields in .env.master
- Config changed but bridge behavior unchanged: restart sms-bridge
- Config changed but desktop/backend unchanged: verify value, then retry request (backend reloads on execution)
- Auth failures after key change: update callers with new AGENT_API_KEY

## Security Notes

- Never commit .env.master
- Keep secrets only in .env.master or secure process environment
- Treat logs and traces as sensitive operational data even with redaction
