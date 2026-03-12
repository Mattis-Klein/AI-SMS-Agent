# Mashbak Architecture

## Core Boundaries

Mashbak preserves these strict architecture rules:

- Desktop app is UI-only and never performs reasoning or direct tool logic.
- Backend is the single reasoning engine for both desktop and SMS.
- Tools execute only through interpreter -> dispatcher -> tool registry.
- SMS bridge stays transport and access-control only.
- Bucherim is a separate backend assistant flow with independent membership state and logs.

## Runtime Topology

```text
Desktop UI (desktop_app/) ----\
                               \--> FastAPI backend (agent/agent.py)
SMS bridge (sms_bridge/) -----/

FastAPI backend request path:
/execute-nl or /execute
  -> AgentRuntime
  -> AssistantCore
  -> NaturalLanguageInterpreter
  -> Dispatcher
  -> ToolRegistry
  -> Built-in tool
  -> AssistantCore response shaping

Bucherim SMS path:
Twilio inbound to +18772683048
  -> sms_bridge transport parsing
  -> POST /bucherim/sms
  -> AgentRuntime.execute_bucherim_sms
  -> BucherimService (membership + conversation + logging)
```

## Backend Endpoints

- GET /health
- GET /tools
- GET /tools/{tool_name}
- POST /execute for direct tool calls
- POST /execute-nl for natural language
- POST /bucherim/sms for Bucherim SMS flow
- POST /run legacy compatibility wrapper to /execute

Request headers:
- x-api-key required on protected endpoints
- x-sender optional sender identifier
- x-source optional source (desktop or sms)
- x-request-id optional external request id

## Session And Context Model

Session ids are source-aware and normalized:
- Desktop: desktop:<sender_key>
- SMS: sms:<10-digit-normalized-sender>
- Bucherim SMS: bucherim:<normalized-e164-digits>

Current session context fields include:
- last_topic
- last_intent
- last_tool
- last_failure_type
- last_entities
- missing_config_fields
- config_progress_state
- pending_restart_components
- recent_turns

Context is in-memory and resets when backend process restarts.

Bucherim keeps a separate in-memory session context manager from Mashbak runtime context.

## Tool System

Current built-in tool count: 15

- 10 system/file tools
- 4 email tools
- 1 configuration tool (set_config_variable)

All tool calls are validated before execution and logged with structured trace fields.

## Config Through Chat

Natural-language config updates are interpreted into set_config_variable when patterns match.

Examples:
- EMAIL_IMAP_HOST = imap.gmail.com
- set MODEL_RESPONSE_MAX_TOKENS to 250
- Follow-up in config thread: and password is ...

set_config_variable writes to mashbak/.env.master, validates values, reloads backend-safe fields immediately, and reports restart requirements for bridge/startup-loaded fields.

## SMS Bridge Responsibilities

Bridge responsibilities only:
- Twilio request handling and signature validation
- Sender access-control decisions
- Forwarding to backend /execute-nl
- Destination routing for Bucherim number (+18772683048) to backend /bucherim/sms
- Returning TwiML responses
- Structured bridge logging with redaction

Bridge does not perform reasoning and does not execute backend tools directly.

## Security And Redaction

Redaction is centralized and applied to traces/logs:
- Backend: agent/redaction.py
- Bridge: sms_bridge/redaction.js

Sensitive assignment values and sensitive keys are masked before persistence to logs.

## Restart Model Summary

- Backend dynamic values: reload in-process on request execution.
- Bridge access-control and Twilio transport values: reload on bridge restart.
- API key changes: require clients to use new key and restart/re-auth where applicable.
