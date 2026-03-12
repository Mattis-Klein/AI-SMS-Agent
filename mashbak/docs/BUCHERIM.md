# Bucherim SMS Assistant

Bucherim is a dedicated SMS assistant flow inside Mashbak runtime.

Twilio destination for Bucherim:
- +18772683048

## Architecture Boundary

Bucherim follows the same core architecture principles as Mashbak:
- SMS bridge is transport-only and does routing plus payload extraction.
- Backend is the intelligence layer and owns membership state, conversation handling, and logging.
- Assistant behavior is implemented in backend modules under mashbak/assistants/bucherim/:
- membership.py
- storage.py
- bucherim_router.py
- bucherim_service.py

## Routing Rules

When inbound SMS is posted to the bridge:
1. If inbound To number is +18772683048, bridge routes request to backend endpoint POST /bucherim/sms.
2. Otherwise, existing Mashbak sender-access flow remains in effect.

Bridge payload to backend includes:
- from number
- to number
- message body
- Twilio message/account metadata
- media references (URL + content type)

## Membership Commands And Outcomes

Exact command matching is case-insensitive after trim:
- @bucherim
- join@bucherim

Deterministic behavior:
1. approved number sends any message:
- routed to Bucherim assistant logic
- response is generated from model/fallback logic using recent message history

2. unknown number sends @bucherim:
- reply: You are not currently approved for Bucherim. Text join@bucherim to request access.

3. unknown number sends join@bucherim:
- sender is recorded as pending
- pending request is stored in config/pending_requests.json
- reply: Your request to join Bucherim has been received and will be reviewed.

4. blocked number sends any message:
- reply with blocked response

5. unknown number sends anything else:
- reply: Access restricted. Text join@bucherim to request access.

## Membership State Model

States:
- unknown
- pending
- approved
- blocked

## Configuration

Membership files:
- mashbak/assistants/bucherim/config/approved_numbers.json
- mashbak/assistants/bucherim/config/pending_requests.json
- mashbak/assistants/bucherim/config/blocked_numbers.json

Number handling:
- numbers are normalized to E.164 in backend before matching
- per-user directories are keyed by normalized E.164 number

## Data Storage And Logs

Per-user storage path:
- mashbak/assistants/bucherim/logs/users/<normalized_phone>/

Current files:
- profile.json
- messages.jsonl

Global pending list:
- mashbak/assistants/bucherim/config/pending_requests.json

Logged artifacts include:
- inbound/outbound text
- timestamps
- request/message metadata
- media references and media_count (media logging ready)
- routing response mode

## MMS And Image Support Status

Current implementation:
- inbound media is parsed, captured, and logged to per-user messages.jsonl
- routing remains text-first while preserving media metadata for future processors

Planned expansion points:
- media download workers
- model-based image analysis
- outbound MMS generation

## Operations

To approve a number quickly:
1. Add number to mashbak/assistants/bucherim/config/approved_numbers.json
2. Optionally remove same number from pending_requests.json and blocked_numbers.json

To review join requests:
- inspect mashbak/assistants/bucherim/config/pending_requests.json

To review a specific user:
- open folder under mashbak/assistants/bucherim/logs/users/<normalized_phone>/
- inspect profile.json and messages.jsonl

Using the approval script:
- Run mashbak/scripts/approve-bucherim-member.ps1 -Phone "+1XXXXXXXXXX" to approve a pending member.
- Add -ActivateNow for immediate active state on classic membership.
- The script writes to both the legacy config.json allowlist (read by membership.py fallback) and the canonical approved_numbers.json.
- It also removes the number from both the legacy pending_requests.jsonl and the new config/pending_requests.json.
