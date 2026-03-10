# AI SMS Agent Documentation Index

Welcome to the AI SMS Agent project. This is your master navigation guide to all documentation.

## ⚡ Quick Tip: Unified Launcher

The entire system can now be started with a single command:
```powershell
.\scripts\dev-start.ps1
```

This replaces the previous three-terminal workflow. See [Runbook](RUNBOOK.md) or [Quick Start](QUICK-START.md) for details.

## 🖥️ Desktop App Tip

The project also ships a local desktop interface in `desktop_app/` that can be packaged as a Windows executable:

```powershell
.\scripts\build-app.ps1 -Clean
```

This creates `dist/AISMSDesktop.exe`, which launches with no terminal window and starts the local agent automatically.

## 📂 Documentation Organization

**All current documentation** is in the `docs/` folder.  
**Legacy reference materials** (original architecture, design notes) are in `docs/legacy/` for reference.  
**Project structure guide** - See [PROJECT-ORGANIZATION.md](../PROJECT-ORGANIZATION.md) for file layout and environment configuration details.

## 📚 Getting Started

**Start here if you're new to the project:**

1. [Quick Start](QUICK-START.md) - Get the system running in under 5 minutes
2. [Installation](INSTALLATION.md) - Complete setup from scratch
3. [Project Architecture](legacy/ARCHITECTURE.md) - Understand the system design

## 🚀 Running & Operations

- [Runbook](RUNBOOK.md) - Start/stop/restart commands and operational procedures
- [Environment Configuration](ENVIRONMENT.md) - All `.env` settings explained
- [Logging Guide](LOGGING.md) - Where to find logs and how to read them

## 🔧 Using the System

- [SMS Commands Reference](COMMANDS.md) - All available SMS commands
- [API Reference](API.md) - Local agent API endpoints and payloads
- [AI Integration](AI-INTEGRATION.md) - Enable natural language AI mode with OpenAI

## 🐛 Troubleshooting

- [Troubleshooting Guide](legacy/TROUBLESHOOTING.md) - Debug SMS delivery failures step-by-step
- [Common Issues](FAQ.md) - Frequently asked questions and solutions

## 🔐 Security & Best Practices

- [Security Baseline](legacy/SECURITY.md) - Core security requirements
- [Security Hardening](SECURITY-HARDENING.md) - Advanced hardening steps
- [Best Practices](BEST-PRACTICES.md) - Operational best practices

## 💻 Development

- [Project Structure](PROJECT-STRUCTURE.md) - Detailed folder organization
- [Development Guide](DEVELOPMENT.md) - Contributing and extending
- [Testing](TESTING.md) - How to test the system

## 📖 Reference Materials

- [Component Details](COMPONENTS.md) - SMS Bridge and Agent internals
- [System Architecture (Legacy)](legacy/ARCHITECTURE.md) - Original system design

---

## Quick Navigation by Role

### Just Getting Started?
→ [Quick Start](QUICK-START.md) → [Installation](INSTALLATION.md)

### Running the System Daily?
→ [Runbook](RUNBOOK.md) → [Logging Guide](LOGGING.md) → [Troubleshooting](legacy/TROUBLESHOOTING.md)

### Customizing or Contributing?
→ [Architecture](legacy/ARCHITECTURE.md) → [Development Guide](DEVELOPMENT.md) → [Components](COMPONENTS.md)

### Securing the System?
→ [Security Baseline](legacy/SECURITY.md) → [Security Hardening](SECURITY-HARDENING.md) → [Best Practices](BEST-PRACTICES.md)

### Enabling AI Features?
→ [AI Integration](AI-INTEGRATION.md) → [Environment](ENVIRONMENT.md)

---

## File Descriptions at a Glance

| Doc | Purpose | Audience |
|-----|---------|----------|
| QUICK-START.md | 5-minute setup | Everyone |
| INSTALLATION.md | Complete setup | First-time users |
| RUNBOOK.md | Daily operations | Operators |
| legacy/ARCHITECTURE.md | System design | Developers |
| API.md | Endpoint reference | Developers |
| ENVIRONMENT.md | Config settings | Operators, Developers |
| LOGGING.md | Log locations & formats | Operators |
| AI-INTEGRATION.md | Enable OpenAI | Advanced users |
| legacy/TROUBLESHOOTING.md | Debug failures | Operators |
| FAQ.md | Common questions | Everyone |
| legacy/SECURITY.md | Security baseline | Everyone |
| SECURITY-HARDENING.md | Advanced security | Security team |
| COMPONENTS.md | Internal details | Developers |
| PROJECT-STRUCTURE.md | Folder layout | Developers |
| DEVELOPMENT.md | Contributing guide | Developers |
| TESTING.md | Test procedures | Developers |

---

## Key Concepts

### The System Has Three Parts

1. **Local Agent** (`agent/`) - FastAPI service on your PC, manages files and commands
2. **SMS Bridge** (`sms-bridge/`) - Node.js service, receives SMS from Twilio
3. **Desktop App** (`desktop_app/`) - Local chat/status UI that calls the same agent pipeline without sending SMS replies

### Tool Pipeline vs SMS Transport

- **Tool Pipeline**: All requests flow through interpreter/dispatcher/tool registry/sandboxed tools
- **SMS Transport**: Twilio bridge delivers external messages into the same agent pipeline
- **Desktop Transport**: Local UI sends local requests to the local agent service only (no Twilio replies)

### Security Layers

- Twilio signature validation
- Allowlist-based phone number filtering
- Agent workspace isolation
- Command allowlist

---

## Troubleshooting Path

```
SMS not working?
  → Is the bridge running? (RUNBOOK.md)
  → Is the agent running? (RUNBOOK.md)
  → Check Twilio logs
  → Read legacy/TROUBLESHOOTING.md
  → Check bridge log (LOGGING.md)
  → Check agent log (LOGGING.md)
  → Still stuck? See FAQ.md
```

---

## Documentation Structure

```
C:\AI-SMS-Agent\
├── README.md                 # Main overview
├── PROJECT-ORGANIZATION.md   # Root structure guide
├── .gitignore                # Git ignore rules
├── .vscode/                  # VS Code workspace settings
├── scripts/                  # Start helper scripts
├── docs/                     # 📍 PRIMARY DOCUMENTATION
│   ├── INDEX.md              # This file - navigation hub
│   ├── QUICK-START.md        # Fast 5-min setup
│   ├── INSTALLATION.md       # Full 30-min setup
│   ├── RUNBOOK.md            # Daily operations
│   ├── COMMANDS.md           # SMS commands
│   ├── ENVIRONMENT.md        # .env config
│   ├── LOGGING.md            # Log guide
│   ├── API.md                # Agent API
│   ├── AI-INTEGRATION.md     # AI setup
│   ├── FAQ.md                # Q&A
│   ├── SECURITY-HARDENING.md # Advanced security
│   ├── BEST-PRACTICES.md     # Best practices
│   ├── COMPONENTS.md         # Technical details
│   ├── PROJECT-STRUCTURE.md  # Folder layout
│   ├── DEVELOPMENT.md        # Contributing
│   ├── TESTING.md            # Testing guide
│   └── legacy/               # Historical/reference docs
│       ├── ARCHITECTURE.md
│       ├── SECURITY.md
│       ├── TROUBLESHOOTING.md
│       └── mashbak-integration.md
│
├── agent/                    # Python service
├── sms-bridge/               # Node.js service
└── (runtime folders excluded)
```

---

**Last Updated**: March 8, 2026  
**Version**: 1.0
