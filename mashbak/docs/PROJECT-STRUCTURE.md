# Project Structure

This document describes the Mashbak subtree rooted at mashbak/.

## Directory Tree

```text
mashbak/
├── .env.master
├── .env.master.example
├── README.md
├── Mashbak.spec
├── agent/
│   ├── __init__.py
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
│   ├── bucherim.py
│   ├── bucherim_config.json
│   ├── requirements.txt
│   ├── tools/
│   └── workspace/
├── bucherim/
│   ├── README.md
│   └── data/
│       └── users/
├── desktop_app/
│   ├── main.py
│   ├── ui.py
│   ├── widgets.py
│   ├── agent_client.py
│   └── agent_service.py
├── sms-bridge/
│   ├── sms-server.js
│   ├── access-control-config.js
│   ├── redaction.js
│   ├── package.json
│   ├── tests/
│   └── logs/
├── tests/
├── docs/
├── scripts/
├── build/
├── dist/
└── workspace/
```

## Role Of Each Area

- agent/: backend API, reasoning, interpreter, dispatcher, tool registry, and tools
- bucherim/: Bucherim user data and subsystem notes
- desktop_app/: local desktop transport and UI only
- sms-bridge/: Twilio transport and sender access-control only
- tests/: Python regression tests for backend behavior
- sms-bridge/tests/: bridge regression tests
- docs/: operational and developer documentation
- scripts/: launch and packaging scripts

## Environment Files

- Committed template: mashbak/.env.master.example
- Local runtime source: mashbak/.env.master

## Build Output

- Default executable: mashbak/dist/Mashbak.exe
- One-dir output: mashbak/dist/Mashbak/

## Runtime-Generated/Local Folders

Common local artifacts:
- agent/.venv/
- agent/__pycache__/
- agent/workspace/logs/
- sms-bridge/node_modules/
- sms-bridge/logs/
- build/
- dist/

Last Updated: March 11, 2026
