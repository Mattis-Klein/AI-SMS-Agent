# Bucherim Subsystem

Bucherim is an SMS-first assistant flow that is separate from Mashbak access control and routing behavior.

Current implementation highlights:
- Dedicated bridge routing by destination Twilio number: +18772683048
- Backend-owned membership gating and state transitions
- Allowlist-based activation with @bucherim
- Join request flow with join@bucherim and pending review logs
- Per-user data folders and JSON/JSONL audit logs
- Media-aware inbound/outbound logging (image analysis/generation placeholders)

Data root:
- mashbak/bucherim/data/users/<normalized_user_key>/

See mashbak/docs/BUCHERIM.md for full behavior and operations.
