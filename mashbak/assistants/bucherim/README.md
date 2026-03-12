# Bucherim Subsystem

Bucherim is an SMS-first assistant flow that is separate from Mashbak access control and routing behavior.

Current implementation highlights:
- Dedicated bridge routing by destination Twilio number: +18772683048
- Backend-owned membership gating and deterministic routing rules
- File-based membership storage for small private-group operation
- Per-user profile/message logs under assistants/bucherim/logs/users/
- Media-aware message logging ready for future media processors

Membership states:
- unknown
- pending
- approved
- blocked

Core modules:
- mashbak/assistants/bucherim/membership.py
- mashbak/assistants/bucherim/storage.py
- mashbak/assistants/bucherim/bucherim_router.py
- mashbak/assistants/bucherim/bucherim_service.py

Config files:
- mashbak/assistants/bucherim/config/approved_numbers.json
- mashbak/assistants/bucherim/config/pending_requests.json
- mashbak/assistants/bucherim/config/blocked_numbers.json

Per-user logs:
- mashbak/assistants/bucherim/logs/users/<normalized_phone>/profile.json
- mashbak/assistants/bucherim/logs/users/<normalized_phone>/messages.jsonl

See mashbak/docs/BUCHERIM.md for full behavior and operations.
