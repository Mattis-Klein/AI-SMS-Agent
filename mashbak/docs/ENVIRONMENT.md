# Environment Configuration (Master File Reference)

Mashbak uses a single master configuration file for all services.

## Source Of Truth

- Primary file: mashbak/.env.master
- Template: mashbak/.env.master.example
- Chat-based updates write to: mashbak/.env.master
- Runtime services that read this file:
  - Python agent runtime
  - Desktop app runtime path (via agent config loader)
  - SMS bridge runtime

Process-level environment variables can still override values when explicitly set in the current shell.

## Setup

1. Copy the template.
2. Fill in your real values.
3. Keep the file private.

```powershell
cd mashbak
cp .env.master.example .env.master
notepad .env.master
```

## Required Core Variables

- AGENT_API_KEY
- AGENT_URL
- BRIDGE_PORT
- PUBLIC_BASE_URL

## Optional AI Variables

- OPENAI_API_KEY
- OPENAI_MODEL

## Email Variables

Canonical names:
- EMAIL_IMAP_HOST
- EMAIL_IMAP_PORT
- EMAIL_USERNAME
- EMAIL_PASSWORD
- EMAIL_MAILBOX
- EMAIL_USE_SSL

Alias compatibility names:
- IMAP_SERVER
- IMAP_PORT
- EMAIL_ADDRESS

At minimum, configure host/server, port, username/address, and password.

## SMS Access Control Variables

- SMS_OWNER_NUMBER
- SMS_ACCESS_REQUEST_NUMBERS
- SMS_ACCESS_REQUEST_KEYWORD
- SMS_ACCESS_REQUEST_RESPONSE
- SMS_DENIAL_RESPONSE
- SMS_SPECIAL_RESPONSES_JSON
- SMS_PHONE_NORMALIZATION_DIGITS

## Twilio Variables

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM_NUMBER

## Logging And Runtime Variables

- BRIDGE_LOG_MAX_BYTES
- AGENT_WORKSPACE
- LOG_LEVEL
- DEBUG_MODE
- SESSION_CONTEXT_MAX_TURNS
- TOOL_EXECUTION_TIMEOUT

## Validation Checklist

- mashbak/.env.master exists
- AGENT_API_KEY is set
- AGENT_URL points to the running agent
- BRIDGE_PORT is available
- PUBLIC_BASE_URL matches your active tunnel URL
- Twilio values are set for production webhook validation and owner notifications
- Email values are set if email tools are used

## Troubleshooting

- Missing configuration errors: set missing fields in mashbak/.env.master
- Agent auth failures: verify AGENT_API_KEY is correct in mashbak/.env.master
- Twilio signature failures: verify TWILIO_AUTH_TOKEN and PUBLIC_BASE_URL
- Email tool not configured: set EMAIL_IMAP_HOST or IMAP_SERVER, EMAIL_IMAP_PORT or IMAP_PORT, EMAIL_USERNAME or EMAIL_ADDRESS, and EMAIL_PASSWORD

## Security Notes

- Never commit mashbak/.env.master
- Keep secrets only in mashbak/.env.master or secure process environment
- Keep mashbak/.env.master.example non-secret and commit-safe

Last Updated: March 11, 2026