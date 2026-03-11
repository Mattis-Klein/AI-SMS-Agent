# Mashbak Architecture (v2.1)

## Overview

Mashbak is a **desktop-first personal AI assistant** with a shared backend reasoning core. Messages from both the desktop application and SMS are processed by the same backend — which interprets natural language, decides whether to call tools or reply conversationally, and returns a natural-language response to the transport layer.

## Core Philosophy

- **Single brain**: All AI reasoning lives in the backend. Transport layers (desktop, SMS) are pure clients.
- **Safety first**: All tool execution goes through a validated whitelist; no arbitrary command execution.
- **Transparency**: Every action is logged with full context and a shared request ID.
- **Conversational**: Responses are natural language, not raw tool output.

## System Architecture

```
Desktop App (Tkinter)               SMS (Twilio)
    │                                   │
    │  AgentClient.execute_nl()         │  bridge: POST /execute-nl
    │  POST /execute-nl  HTTP           │
    └──────────────┬────────────────────┘
                   ↓
        [FastAPI Agent] - agent.py
            ├─ /health
            ├─ /tools
            ├─ /execute       (direct tool call, structured)
            └─ /execute-nl    (natural language entry point)
                   ↓
        [AssistantCore] - assistant_core.py   ← REASONING LAYER
            ├─ Classify intent (conversation vs tool vs mixed)
            ├─ If conversation → BackendOpenAIClient → natural reply
            └─ If tool → Runtime.execute_tool()
                   ↓
        [AgentRuntime] - runtime.py
            ├─ Source-aware routing (desktop vs sms)
            └─ Tool execution path:
                   ↓
        [Dispatcher] - dispatcher.py
            ├─ Builds RequestContext
            ├─ Logs incoming request
            └─ Passes to Tool Registry
                   ↓
        [Tool Registry] - registry.py + tools/
            ├─ Validates tool exists and is allowed
            └─ Executes selected tool
                   ↓
        [Built-in Tools] - tools/builtin/
            ├─ dir_inbox / dir_outbox
            ├─ list_files
            ├─ system_info / cpu_usage / disk_space
            ├─ current_time / uptime
            ├─ network_status / list_processes
            └─ email tools (list, summarize, search, read thread)
                   ↓
        [AssistantCore] wraps tool output in natural language
                   ↓
        [Structured Logger] - logger.py
            └─ JSON log lines per request lifecycle
                   ↓
        Natural-language response back to transport
```

## Key Components

### 1. AssistantCore (`agent/assistant_core.py`) — The Reasoning Layer

The single reasoning brain shared by all transports. Sits between the FastAPI endpoints and the tool registry.

- **Input**: natural-language message + metadata (source, sender, unlock state)
- **Decision**: classify as conversation, tool request, or policy block (locked)
- **If conversation**: calls `BackendOpenAIClient` → returns natural-language reply
- **If tool**: calls `runtime.execute_tool()` → wraps raw output in natural language
- **Output**: always a human-readable string, never raw JSON or tool output

The `BackendOpenAIClient` uses the standard OpenAI REST API via `urllib` (no SDK dependency). When `OPENAI_API_KEY` is not configured, it falls back to simple canned responses.

### 2. Tool System (`agent/tools/`)

**Base Tool Class** (`base.py`):
- Every tool inherits from `Tool` base class
- Each tool has:
  - `name`: Unique identifier
  - `description`: Human-readable description
  - `requires_args`: Boolean indicating if tool needs arguments
  - `validate_args()`: Validate input format
  - `execute()`: Async execution method
  - `get_info()`: Return metadata

**Tool Registry** (`registry.py`):
- Central registry for all tools
- Full discovery and introspection support
- Easy to register new tools

**Built-in Tools** (`builtin/`):
- 10 pre-configured system monitoring tools
- Each implements safe command execution
- All return structured output

### 2. Configuration System (`config.py`)

The `config.json` file controls:
- `allowed_directories`: Paths tools can access
- `allowed_tools`: Tools available to users (optional; if missing, all tools allowed)
- `logging`: Log retention and level
- `security`: File size limits, blocked extensions, sender validation

```json
{
  "allowed_directories": [
    "C:\\Users\\Public\\Documents",
    "C:\\Users\\owner\\Documents",
    "C:\\Projects",
    "C:\\Temp"
  ],
  "logging": {
    "max_log_size_bytes": 5000000,
    "log_retention_days": 30,
    "log_level": "info"
  },
  "security": {
    "max_file_size_bytes": 10485760,
    "blocked_extensions": [".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js"],
    "require_sender_validation": true
  }
}
```

### 3. Dispatcher (`dispatcher.py`)

Routes requests through a structured decision tree:

1. **Request Reception**
   - Receives SMS via bridge
   - Creates request context with sender, workspace, allowed dirs

2. **Interpretation** (if natural language)
   - NL interpreter maps message to tool
   - Extracts any arguments (like file paths)
   - Returns tool name and args

3. **Validation**
   - Checks tool exists in registry
   - Checks tool is in allowed_tools list (if configured)
   - Validates argument schema

4. **Execution**
   - Gets tool from registry
   - Passes validated arguments and context
   - Logs execution details

5. **Response**
   - Logs outcome (success/error)
   - Returns output to SMS bridge
   - Bridge truncates to SMS length (1500 chars)

### 4. Natural Language Interpreter (`interpreter.py`)

Rule-based pattern matcher that maps SMS messages to tools:

**Examples:**

```
Input Message           →  Tool          Arguments
"check my inbox"        →  dir_inbox     {}
"list files in docs"    →  list_files    {"path": "docs"}
"what time is it"       →  current_time  {}
"show cpu usage"        →  cpu_usage     {}
"network status"        →  network_status {}
```

The interpreter:
- Handles variations in phrasing
- Extracts paths and parameters
- Returns confidence score (0-1)
- Falls back gracefully if no match

### 5. Structured Logging (`logger.py`)

All events logged as JSON lines for easy parsing:

```json
{"time": "2026-03-09T14:30:15", "hostname": "desktop", "request_id": "abc123", "event_type": "request", "sender": "+15551234567", "raw_message": "what time is it"}
{"time": "2026-03-09T14:30:15", "request_id": "abc123", "event_type": "tool_execution", "tool_name": "current_time", "arguments": {}, "success": true, "output": "3/9/2026 2:30 PM"}
{"time": "2026-03-09T14:30:16", "request_id": "abc123", "event_type": "response", "status": "success", "response_message": "3/9/2026 2:30 PM", "tool_name": "current_time"}
```

**Log Fields:**
- `request_id`: Unique per SMS request (for tracing)
- `sender`: Phone number of requester
- `raw_message`: Original SMS text
- `interpreted_intent`: Tool selected
- `tool_name`: Final tool executed
- `arguments`: Validated/passed arguments
- `output`: Tool result (truncated)
- `error`: Error message if applicable
- `event_type`: request, tool_execution, response, error, etc.

### 6. SMS Bridge (`sms-bridge/sms-server.js`)

Node.js Express server that stays transport-only:
- Receives Twilio webhook requests
- Validates Twilio signature (optional) and applies sender access control in bridge
- Forwards non-empty messages to the shared core endpoint: `POST /execute-nl`
- Sends TwiML SMS responses

Sender access control (bridge):
- Owner number is forwarded to the agent
- Special numbers get fixed responses without agent forwarding
- Access-request numbers get a fixed response; if they text `@mashbak`, bridge sends owner notification SMS
- All other senders are denied in bridge

Bridge endpoints:

```
GET  /health              Bridge status
GET  /                    Basic liveness
GET  /sms                 SMS endpoint liveness
POST /sms                 Twilio webhook entry point
```

The bridge does not execute business logic locally and does not bypass the dispatcher.

### 7. Agent API (`agent/agent.py`)

Shared backend endpoints consumed by both desktop and SMS transports:

```
GET  /health
GET  /tools
GET  /tools/{tool_name}
POST /execute
POST /execute-nl
POST /run                 (legacy compatibility)
```

Source-aware behavior is provided via request headers:
- `x-sender`: original sender identifier (desktop client or phone number)
- `x-source`: `desktop` or `sms`

The same runtime pipeline handles both channels; only response formatting differs by source.

## Request Lifecycle

### Desktop path: "How busy is my computer right now?"

1. **User types** message in Tkinter chat panel and presses Send
2. **Desktop UI** calls `AgentClient.execute_nl(message, owner_unlocked=True)`
3. **AgentClient** POSTs `{"message": "...", "owner_unlocked": true}` to `/execute-nl` with `x-source: desktop`
4. **FastAPI** routes to `runtime.execute_nl()`
5. **AgentRuntime** delegates to `AssistantCore.respond()`
6. **AssistantCore** asks `NaturalLanguageInterpreter` which tool to use → `cpu_usage`
7. **AssistantCore** calls `runtime.execute_tool("cpu_usage")`
8. **Dispatcher** builds `RequestContext`, logs request, calls `CpuUsageTool.execute()`
9. **CpuUsageTool** reads `psutil.cpu_percent()` and returns "CPU Usage: 22.0%"
10. **AssistantCore** passes tool output through `BackendOpenAIClient` → natural reply: "Your CPU is at 22%, which is light usage."
11. **Response** travels back through FastAPI → HTTP → AgentClient → UI
12. **Desktop UI** renders the reply in the chat panel as an assistant message bubble

### SMS path: "show my inbox"

1. **SMS arrives** at bridge with `From: +15551234567, Body: show my inbox`
2. **Bridge validates** sender is in the allowlist; denies if not
3. **Bridge POSTs** `{"message": "show my inbox"}` to agent's `/execute-nl` with `x-source: sms`
4. **AssistantCore** interprets → `dir_inbox` tool → executes → wraps output in natural language
5. **Response** flows back through bridge → Twilio → SMS reply
6. **SMS response is truncated** to ≤320 compact characters if needed

Both paths use the identical `AssistantCore → Tool → NL-wrap` pipeline. Only response formatting and length limits differ between sources.

## Security Model

### Tool-Level Security

Each tool implements:

1. **Input Validation**
   - Argument schema checking
   - Type validation (string, int, bool, etc.)
   - Required/optional field checking

2. **Path Validation** (for file tools)
   - Abstract paths relative to workspace
   - Prevent `../` traversal escapes
   - Check against `allowed_directories` whitelist
   - Block access outside safe zones

3. **Signal Validation**
   - Command whitelist (no arbitrary shell)
   - Timeout enforcement (30 seconds default)
   - Error capture and safe reporting

### Agent-Level Security

1. **API Authentication**
   - X-API-KEY header required
   - Matches AGENT_API_KEY from environment

2. **Sender Validation**
   - Optional: restrict to pre-approved phone numbers
   - Logged for audit trail

3. **Tool Allowlisting**
   - Optional: restrict to subset of tools
   - Configured in config.json

### Bridge-Level Security

1. **Twilio Signature Validation**
   - Verifies SMS authenticity
   - Optional if TWILIO_AUTH_TOKEN not set (dev mode)

2. **Sender Allowlisting**
   - Optional: restrict to known phone numbers
   - Logged rejection for audit

3. **Message Length Limits**
   - Response truncated to 1500 chars max
   - Prevents accidental exposure of large data

## Adding New Tools

To add a new tool:

1. **Create a new file** in `agent/tools/builtin/your_tool.py`:

```python
from ..base import Tool, ToolResult
from typing import Any, Dict, Optional

class YourTool(Tool):
    def __init__(self):
        super().__init__(
            name="your_tool_name",
            description="What your tool does",
            requires_args=False,  # or True if it needs args
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        # Validate input arguments
        if args:  # Example: no args allowed
            return False, "your_tool_name does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            # Your logic here
            result = do_something()
            return ToolResult(success=True, output=result, tool_name=self.name, arguments=args)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
```

2. **Register in `agent/tools/builtin/__init__.py`**:

```python
from .your_tool import YourTool

ALL_BUILTIN_TOOLS = [
    # ... existing tools ...
    YourTool(),
]
```

3. **Add to interpreter patterns** (optional, in `agent/interpreter.py`):

```python
(r"(?:show|display|run|execute).*your.*description", "your_tool_name", lambda m: {}),
```

4. **Document in TOOLS.md**

5. **Test via API**:

```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: YOUR_KEY" \
  -d '{"tool_name": "your_tool_name", "args": {}}'
```

## Environment Variables

**Agent** (`agent/.env`):

```
AGENT_API_KEY=your-secret-key
AGENT_WORKSPACE=/path/to/workspace
```

**SMS Bridge** (`sms-bridge/.env`):

```
AGENT_URL=http://127.0.0.1:8787
AGENT_API_KEY=your-secret-key (must match!)
BRIDGE_PORT=34567
PUBLIC_BASE_URL=https://your-domain.com
TWILIO_AUTH_TOKEN=your-twilio-token
ALLOWED_SMS_FROM=+15551234567,+15559876543
OPENAI_API_KEY=sk-... (optional, for future AI features)
OPENAI_MODEL=gpt-4.1-mini (optional)
```

## Error Handling

### Tool Errors

Tools return structured errors:

```json
{
  "success": false,
  "output": null,
  "error": "Path is not in allowed directories",
  "tool_name": "list_files",
  "arguments": {"path": "/etc/passwd"}
}
```

### Dispatcher Errors

- **Unknown Tool**: "Could not interpret: <message>"
- **Invalid Arguments**: "<field> is required"
- **Unauthorized**: "Tool '<name>' is not allowed"
- **Execution Error**: "Tool execution failed: <error>"

All errors logged with context for debugging.

## Monitoring & Observability

### Log Analysis

Query logs for patterns:

```bash
# All requests from a sender
grep '+15551234567' agent/workspace/logs/agent.log

# Tool execution errors
grep 'event_type.*error' agent/workspace/logs/agent.log

# Specific request timeline (trace all events)
grep 'request_id=abc-123' agent/workspace/logs/agent.log
```

### Health Checks

```bash
# Agent health
curl http://localhost:8787/health

# Bridge health
curl http://localhost:34567/health
```

### Metrics (if monitoring)

- Tools available: `/health` response
- Request latency: Logged timestamps
- Error rate: Count error events
- Sender activity: Group by sender phone

## Limitations & Future Work

### Current Limitations

- Natural language interpreter is rule-based (not ML)
- No persistence (commands executed, results not stored)
- No scheduled/recurring tasks
- Files can't be read from SMS (too large)

### Future Enhancements

- ML-based NL interpretation (with OpenAI integration)
- File chunking for large reads via SMS
- Scheduled command execution
- User preferences per sender
- Command history/audit dashboard
- Multi-user support with role-based access
- Custom tool registration API

## Glossary

- **Tool**: A discrete, whitelisted capability (dir_inbox, cpu_usage, etc.)
- **Dispatcher**: Central router that maps requests to tools
- **Interpreter**: Natural language parser that maps SMS to tool names
- **Tool Registry**: In-memory catalog of all available tools
- **Request Context**: Metadata about current request (sender, workspace, etc.)
- **Tool Result**: Structured response from tool execution
- **Bridge**: SMS↔Agent adapter (Node.js)
- **Agent**: Core FastAPI service handling tool execution

