# SMS Commands Reference

All SMS commands you can send to your Twilio number.

## Basic Commands

### `hello`

Quick connectivity test.

**Usage:**
```
hello
```

**Response:**
```
Hello from the AI SMS agent! I'm alive.
```

---

### `help`

Shows the list of available commands.

**Usage:**
```
help
```

**Response:**
```
Fixed commands:
- hello: Connectivity test
- help: This message
- run dir_inbox: List inbox
- run dir_outbox: List outbox
- read <path>: Read a file
- write <path> :: <text>: Create file
- overwrite <path> :: <text>: Replace file
Or ask in natural language (if AI enabled).
```

---

## File Operations

### `read <path>`

Read a file from your agent workspace.

**Usage:**
```
read inbox/notes.txt
read outbox/response.txt
```

**Rules:**
- Path must be inside `agent/workspace/`
- File must exist
- `.` and `..` are blocked (no directory traversal)

**Response:**
```
[File contents, first ~160 characters in SMS]
```

**Errors:**
- `File not found` - file doesn't exist
- `Invalid path` - path is outside workspace

---

### `write <path> :: <text>`

Create a new file (will not overwrite).

**Usage:**
```
write inbox/todo.txt :: Buy milk, eggs, bread
write inbox/list.txt :: Item 1, Item 2
```

**Rules:**
- Path must be inside `agent/workspace/`
- File cannot already exist (use `overwrite` instead)
- Max length: ~120 characters per SMS

**Response:**
```
File created: inbox/todo.txt
```

**Errors:**
- `File already exists` - use `overwrite` to replace
- `Invalid path` - path is outside workspace

---

### `overwrite <path> :: <text>`

Replace an existing file or create if missing.

**Usage:**
```
overwrite inbox/status.txt :: Updated: 2025-03-08
overwrite outbox/message.txt :: New content here
```

**Rules:**
- Path must be inside `agent/workspace/`
- Will replace existing file
- Max length: ~120 characters per SMS

**Response:**
```
File updated: inbox/status.txt
```

---

## System Commands

### `run <command_name>`

Execute a pre-approved command from the allowlist.

**Available Commands:**

#### `run dir_inbox`

List contents of `agent/workspace/inbox/`

**Usage:**
```
run dir_inbox
```

**Response:**
```
Volume in drive C is ...
Directory of C:\AI-SMS-Agent\agent\workspace\inbox
 03/08/2025 10:30 AM   <DIR> .
 03/08/2025 10:30 AM   <DIR> ..
 03/08/2025 10:35 AM      1,234 notes.txt
```

---

#### `run dir_outbox`

List contents of `agent/workspace/outbox/`

**Usage:**
```
run dir_outbox
```

**Response:**
```
[Directory listing of outbox folder]
```

---

## Natural Language (AI Mode Only)

If you have `OPENAI_API_KEY` configured, any message that's not a fixed command becomes natural language:

### Examples

```
Read my inbox and tell me what's there
```

```
Create a file called notes.txt with a shopping list
```

```
What files are in my outbox folder?
```

```
Write a grocery list to inbox/shopping.txt
```

The AI will:
- Call the local tools (read, write, run commands)
- Combine results
- Send back a natural-language response

---

## Command Limits & Rules

| Aspect | Limit | Note |
|--------|-------|------|
| SMS length | 160 chars | Standard SMS size |
| Response length | 160 chars | May be split into multiple SMS |
| File size | 1 MB | For read operations |
| Write size | ~120 chars | Due to SMS format |
| Workspace | `agent/workspace/` | Cannot access outside |
| Commands | Allowlist only | See `agent/agent.py` |
| AI rounds | 6 max | Per AI mode message |

---

## Error Responses

| Error | Meaning | Fix |
|-------|---------|-----|
| `Unauthorized` | Wrong API key | Check `AGENT_API_KEY` |
| `File not found` | File doesn't exist | List with `run dir_inbox` first |
| `File already exists` | Use `overwrite` instead | Change command or delete file |
| `Invalid path` | Path is outside workspace | Path must be in `inbox/` or `outbox/` |
| `Command rejected` | Not in allowlist | See `help` for valid commands |
| `No reply within 30s` | Bridge or agent crashed | Check logs, restart services |
| `Invalid Twilio token` | Signature validation failed | Verify `TWILIO_AUTH_TOKEN` |
| `Sender not allowed` | Your number not in allowlist | Add to `ALLOWED_SMS_FROM` |

---

## Workspace Paths

You can access files in two main folders:

```
agent/workspace/
├── inbox/          (read/write your incoming files)
└── outbox/         (read/write your outgoing files)
```

Examples:
- `read inbox/notes.txt`
- `write outbox/response.txt :: Thank you`
- `run dir_inbox`

---

## Tips

1. **Keep messages short** - SMS is 160 characters
2. **Use natural language if stuck** - The AI can interpret fuzzy requests
3. **Check logs if confused** - See [Logging Guide](LOGGING.md)
4. **Read help** - Type `help` to see current command list
5. **Test with `hello` first** - Quick way to verify system is running

---

## Command Syntax Cheat Sheet

| Task | Command |
|------|---------|
| Test connection | `hello` |
| List commands | `help` |
| List inbox | `run dir_inbox` |
| List outbox | `run dir_outbox` |
| Read file | `read inbox/FILE` |
| Create file | `write inbox/FILE :: CONTENT` |
| Update file | `overwrite inbox/FILE :: CONTENT` |
| Ask AI (if enabled) | `Anything natural language` |

---

**Last Updated**: March 8, 2026  
**Version**: 1.0
