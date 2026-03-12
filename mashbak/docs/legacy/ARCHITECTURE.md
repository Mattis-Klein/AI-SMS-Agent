# Current Architecture

This file describes the current implemented system, not the future design ideas.

## Runtime Flow

1. A phone sends an SMS to the Twilio number.
2. Twilio sends an HTTP POST webhook to the public Tailscale Funnel URL.
3. The SMS bridge in `sms_bridge/sms-server.js` validates the request and sender.
4. The bridge either handles a fixed command directly or sends the message to the AI model.
5. The local agent in `agent/agent.py` performs the file or command action.
6. The bridge returns TwiML to Twilio.
7. Twilio sends the SMS reply back to the phone.

## Components

### SMS Bridge

- Node.js + Express
- Internet-facing through Tailscale Funnel
- Validates Twilio signatures when configured
- Restricts allowed senders when configured
- Writes durable logs to `data/logs/bridge.log`
- Can use an OpenAI model for natural-language tool calling when configured

### Local Agent

- FastAPI service
- Local-only tool server
- Reads and writes only inside `data/workspace`
- Runs only commands in the hard-coded allowlist
- Writes durable logs to `data/logs/agent.log`

## Current Commands

- `hello`
- `help`
- `run dir_inbox`
- `run dir_outbox`
- `read inbox/file.txt`
- `write inbox/file.txt :: text`
- `overwrite inbox/file.txt :: text`
- Any other message can be routed through the AI layer when configured.

## Not Implemented Yet

- OAuth account integrations
- Approval workflow for risky actions
- Rate limiting
- Desktop automation
