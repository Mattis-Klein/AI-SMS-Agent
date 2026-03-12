# Bucherim SMS Assistant

Bucherim is a dedicated SMS assistant flow inside Mashbak runtime.

Twilio destination for Bucherim:
- +18772683048

## Architecture Boundary

Bucherim follows the same core architecture principles as Mashbak:
- SMS bridge is transport-only and does routing plus payload extraction.
- Backend is the intelligence layer and owns membership state, conversation handling, and logging.
- Assistant behavior is implemented in backend module: mashbak/agent/bucherim.py.

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
1. @bucherim from allowlisted number:
- admitted immediately
- membership status becomes active
- welcome confirmation is returned

2. @bucherim from non-allowlisted number:
- not admitted
- status becomes rejected
- explicit response instructs user to send join@bucherim

3. join@bucherim from non-member:
- membership status becomes pending_request
- request is logged in per-user requests file and global pending list
- acknowledgement response is returned

4. normal message from active member:
- routed to Bucherim assistant conversation flow
- session context is used for coherent follow-up handling

5. normal message from non-member:
- blocked with explicit not-authorized / not-joined response

## Membership State Model

States:
- not_known
- pending_request
- allowed_not_joined
- active
- rejected

Transitions:
- initial new sender:
- allowlisted -> allowed_not_joined
- blocked list -> rejected
- otherwise -> not_known

- allowlisted sender sends @bucherim -> active
- non-allowlisted sender sends @bucherim -> rejected
- non-member sender sends join@bucherim -> pending_request
- active sender remains active for normal conversation

## Configuration

Config file:
- mashbak/agent/bucherim_config.json

Key fields:
- assistant_number: E.164 destination number for Bucherim route
- allowlist: pre-approved E.164 numbers
- blocked_numbers: explicit denied E.164 numbers
- responses: customizable user-facing messages

Number handling:
- numbers are normalized to E.164 in backend before matching
- filesystem user paths use sanitized deterministic phone keys

## Data Storage And Logs

Per-user storage path:
- mashbak/bucherim/data/users/<normalized_user_key>/

Current files:
- profile.json
- membership.json
- conversation.jsonl
- requests.jsonl
- media/index.jsonl
- media/ (folder for future downloaded files)

Global pending list:
- mashbak/bucherim/data/pending_requests.jsonl

Logged artifacts include:
- inbound/outbound text
- timestamps
- request/message metadata
- membership events and transitions
- media references and processing mode
- response mode (text, join_request_ack, image_analysis_unavailable, etc.)

## Context Handling

Bucherim keeps per-user session context keyed by sender number.

Session tracking includes:
- recent turns
- topic continuity
- intent continuity markers
- assistant reply history for follow-up coherence

## MMS And Image Support Status

Current implementation:
- inbound media is detected and logged with references
- media entries are recorded in conversation and media index logs
- image analysis and outbound image generation are not fully wired yet
- assistant responds honestly when image capabilities are unavailable

Planned expansion points:
- media downloading and local file indexing
- image analysis model integration
- outbound MMS image sending

## Operations

To add/remove allowlisted users:
1. Edit mashbak/agent/bucherim_config.json
2. Update allowlist with E.164 numbers
3. Save file (backend reloads config on request)

To review join requests:
- inspect mashbak/bucherim/data/pending_requests.jsonl
- inspect per-user requests.jsonl files

To review a specific user:
- open user folder under mashbak/bucherim/data/users/
- inspect profile, membership, conversation, and media index files
