# Project Structure

This document describes the canonical platform layout under mashbak/.

## Directory Tree

```text
mashbak/
├── .env.master
├── .env.master.example
├── README.md
├── Mashbak.spec
├── agent/
│   ├── agent.py
│   ├── runtime.py
│   ├── assistant_core.py
│   ├── interpreter.py
│   ├── dispatcher.py
│   ├── session_context.py
│   ├── logger.py
│   ├── redaction.py
│   ├── config.py
│   ├── config_loader.py
│   ├── config.json
│   ├── tools/
│   └── requirements.txt
├── assistants/
│   ├── __init__.py
│   ├── mashbak/
│   └── bucherim/
│       ├── __init__.py
│       ├── service.py          (compat re-export)
│       ├── membership.py
│       ├── storage.py
│       ├── bucherim_router.py
│       ├── bucherim_service.py
│       ├── config.json         (legacy allowlist, read by membership.py)
│       ├── config/
│       │   ├── approved_numbers.json
│       │   ├── pending_requests.json
│       │   └── blocked_numbers.json
│       ├── logs/
│       │   └── users/
│       │       └── <normalized_phone>/
│       │           ├── profile.json
│       │           └── messages.jsonl
│       └── README.md
├── sms_bridge/
│   ├── sms-server.js
│   ├── access-control-config.js
│   ├── redaction.js
│   ├── package.json
│   └── tests/
├── desktop_app/
├── data/
│   ├── users/
│   ├── logs/
│   ├── media/
│   └── workspace/
├── docs/
├── scripts/
└── tests/
```

## Role Of Each Area

- agent/: shared backend intelligence and execution core
- assistants/: assistant-specific behavior and configuration
- sms_bridge/: SMS transport routing and validation only
- desktop_app/: local UI client and controls only
- data/: runtime users, logs, media, and workspace files
- tests/: regression tests for backend behavior
- docs/: platform and operations documentation

## Build Output

- Default executable: mashbak/dist/Mashbak.exe
- One-dir output: mashbak/dist/Mashbak/
