# Component Details

## Backend (agent/)

Main files:
- agent.py: FastAPI entrypoints
- runtime.py: runtime wiring, dynamic config reload, source handling
- assistant_core.py: reasoning and response shaping
- interpreter.py: natural-language and config assignment parsing
- dispatcher.py: validation/execution path for tools
- session_context.py: in-memory context tracking
- redaction.py: backend redaction helpers

## Desktop (desktop_app/)

Desktop responsibilities:
- Render UI and lock/unlock state
- Send requests to backend
- Display backend responses and status

Desktop does not run local reasoning and does not execute backend tools directly.

## SMS Bridge (sms-bridge/)

Bridge responsibilities:
- Receive Twilio webhook
- Validate Twilio signature when token configured
- Apply sender access-control policy
- Forward allowed messages to backend /execute-nl
- Return TwiML SMS replies
- Log bridge events with redaction

Bridge health endpoint returns:
- status
- port
- logFile
- twilioValidationEnabled
- senderAccessControlEnabled
- accessControlConfigLoadedAt
- accessControlReloadRequiresRestart

## Tools

Registered tool categories:
- system/file tools
- email tools
- config tool (set_config_variable)

All tool invocation flows through backend registry/dispatcher path.
