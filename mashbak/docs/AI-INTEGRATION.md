# AI Integration

Mashbak uses one shared backend assistant core for both desktop and SMS.

## Enable AI Replies

Set in mashbak/.env.master:

- OPENAI_API_KEY
- OPENAI_MODEL (default gpt-4.1-mini)
- OPENAI_BASE_URL (default https://api.openai.com/v1)
- OPENAI_TIMEOUT_SECONDS (default 25)
- OPENAI_TEMPERATURE (default 0.3)
- MODEL_RESPONSE_MAX_TOKENS

If OPENAI_API_KEY is missing, backend falls back to deterministic non-AI responses.

## Request Flow

Desktop and SMS both use backend /execute-nl.

- Desktop sends local request to backend with source=desktop.
- Bridge forwards SMS text to backend with source=sms.
- AssistantCore decides conversation vs tool execution.
- Tool execution still runs through interpreter, dispatcher, and registry.

AI is used for response shaping and conversation replies, not for bypassing tool safety controls.

## Config Through Chat

AI mode does not change config validation rules.

Config updates still route through set_config_variable and write to mashbak/.env.master.

## Safety Notes

- Redaction runs before traces/logs are persisted.
- Bridge remains transport/access-control only.
- Backend remains the only reasoning engine.
- Time-sensitive factual queries (current events, elections, officeholders, schedules, laws, prices, statistics) must be verified via an available tool path before answering.
- If verification is not available in-runtime, Mashbak refuses cleanly instead of guessing.
- Conversation traces now include verification metadata:
- verification_state: Verified | Tool-assisted | Local-only | Unverified
- verification_reason: short reason explaining why the reply was or was not verified
