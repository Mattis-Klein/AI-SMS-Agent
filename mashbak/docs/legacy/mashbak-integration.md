# Original Design Notes

This file contains the original design thinking and requirements that led to the AI SMS Agent system.

## Original Request

i want an ai model that i can communicate with through sms on my flip phone and it will have access to my files on my pc and any programs/apps that i use and my accounts on various websites like amazon or just access to my google account which has all of my passwords

### Safety Notes on Original Request

You can absolutely build "SMS → AI agent → your PC/apps/web," but you should not give it your Google passwords or "all my passwords." That's the fastest way to get your life wrecked if anything leaks.

What you can do safely is give the agent controlled access via:

- OAuth logins (Google, Amazon, etc.) with scopes and revocable tokens
- A password manager (1Password / Bitwarden) where the agent can request credentials only when needed (ideally with an approval step), instead of "knowing everything"
- A local PC "control server" that the AI can call to read/write specific folders and run specific commands—allowlisted, logged, and permissioned.

## Safe Architecture (Recommended)

### 1) SMS in/out (Twilio)
Your flip phone texts a Twilio number.

### 2) Cloud "Router" (tiny web service)
Twilio hits a webhook (your server). This server:
- validates the SMS is really from Twilio
- sends the message to your AI model
- calls your PC Local Agent for any on-computer tasks
- sends the result back as SMS

### 3) PC Local Agent (runs on your Windows machine)
A small local service that can:
- access specific folders/files
- run specific automations (PowerShell scripts, launching apps, editing files)
- optionally control UI (carefully!)
- All behind authentication, allowlists, and logging.

## What NOT to Do

❌ Don't dump your Google password vault into an AI.
❌ Don't give "full access to Amazon" with a session that can buy things.
❌ Don't run an agent that can execute arbitrary commands without guardrails.

Instead:
- Use OAuth for Google (Drive/Gmail/Calendar) with minimal scopes
- Use "approval required" for purchases or anything high-risk
- Use a separate "agent" Google account where possible

## Implementation Decisions

### Operating Mode
The built system only operates when the PC and local agent are running. This is the safest approach - the system cannot perform actions remotely when offline.

### Current Capabilities

**Fixed Commands (Always Work):**
- `hello` - Test connectivity
- `help` - Show available commands
- `run dir_inbox` - List inbox files
- `run dir_outbox` - List outbox files
- `read inbox/file.txt` - Read a file
- `write inbox/file.txt :: text` - Create/append to file
- `overwrite inbox/file.txt :: text` - Replace file contents

**AI Mode (Optional):**
- Any other message gets passed to AI for natural language understanding
- AI can call the same tools above based on your request
- Requires `OPENAI_API_KEY` to be configured

### Security Layers Implemented

1. **Authentication:** API key shared between bridge and agent
2. **Path Isolation:** All file ops limited to `data/workspace/`
3. **Command Allowlist:** Only pre-approved commands can run
4. **Twilio Validation:** Webhook signature verification
5. **Sender Filtering:** Only accept SMS from configured number
6. **Audit Logging:** All actions logged to file

### Not Yet Implemented

- OAuth account integrations
- Approval workflow for risky actions
- Rate limiting
- Desktop automation
- Multi-user support
- Immutable audit logs

## Scope Decision

This implementation focuses on the core "PC access + SMS" functionality. Extended features like OAuth integrations, desktop automation, and approval workflows are documented as future enhancements but not included in the current build.

---

**Created:** Original design phase  
**Updated:** March 8, 2026
