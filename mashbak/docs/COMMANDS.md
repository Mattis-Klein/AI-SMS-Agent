# SMS Commands Reference

All SMS commands you can send to your Twilio number.

## 🔍 Discovery Commands

### `hello`

Quick connectivity test.

**Usage:**
```
hello
```

**Response:**
```
Hi. SMS link is working.
```

---

### `help`

Shows the command reference.

**Usage:**
```
help
```

**Response:**
```
Commands:
hello - Test connection
help - Show this help
commands - List all available commands
run <name> - Run a whitelisted command
	Examples: run system_info, run cpu_usage
list <path> - List files in directory
read <path> - Read a file
write <path> :: <text> - Write to file
overwrite <path> :: <text> - Overwrite file
Or just send plain English - AI will help when OpenAI is configured.
```

---

### `commands`

Get a detailed list of all available whitelisted commands with descriptions.

**Usage:**
```
commands
```

**Response:**
```
Available commands:
dir_inbox: List files in inbox directory
dir_outbox: List files in outbox directory
list_files: List files in a specified directory
system_info: Get basic system information
cpu_usage: Check CPU usage
disk_space: Check disk space on C: drive
current_time: Get current system time
network_status: Check network connection status
list_processes: List top running processes
uptime: Get system uptime
```

---

## 📁 File Operations

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


### `overwrite <path> :: <text>`

Replace an existing file or create if missing.

**Usage:**
```
overwrite inbox/status.txt :: Updated: 2026-03-09
```

**Response:**
```
Saved inbox/status.txt
```

---

### `list <path>`

List files and folders in a directory.

**Usage:**
```
list C:\Projects
list C:\Users\Public\Documents
```

**Rules:**
- Path must be in `allowed_directories` (configured in `agent/config.json`)
- Default allowed: `C:\Users\Public\Documents`, `C:\Projects`, `C:\Temp`

**Response:**
```
Volume in drive C has no label.
Directory of C:\Projects
03/09/2026  02:30 PM    <DIR>          project1
03/09/2026  03:15 PM    <DIR>          project2
							 2 File(s)
```

**Errors:**
- `Path is not in allowed directories` - path not whitelisted

---

## 🖥️ System Monitoring Commands

### `run system_info`

Get basic system information (OS, version, memory).

**Usage:**
```
run system_info
```

**Response:**
```
OS Name: Microsoft Windows 11 Pro
OS Version: 10.0.22631 N/A Build 22631
System Type: x64-based PC
Total Physical Memory: 16,384 MB
```

---

### `run cpu_usage`

Check current CPU usage percentage.

**Usage:**
```
run cpu_usage
```

**Response:**
```
23.45
```

*Value is a percentage (e.g., 23.45%)*

---

### `run disk_space`

Check free space on C: drive.

**Usage:**
```
run disk_space
```

**Response:**
```
DeviceID  FreeSpace    Size
C:        524288000    1073741824
```

*Values are in bytes*

---

### `run current_time`

Get current system date and time.

**Usage:**
```
run current_time
```

**Response:**
```
Sun 03/09/2026 14:30:15.42
```

---

### `run network_status`

Check network connection status.

**Usage:**
```
run network_status
```

**Response:**
```
IPv4 Address. . . . . . . . . . . : 192.168.1.100
```

---

### `run list_processes`

Show top 10 running processes by CPU usage.

**Usage:**
```
run list_processes
```

**Response:**
```
ProcessName      CPU WorkingSet
-----------      --- ----------
chrome        125.5  524288000
python         42.3  104857600
explorer       12.1   52428800
...
```

---

### `run uptime`

Get system uptime in hours.

**Usage:**
```
run uptime
```

**Response:**
```
72.45
```

*Value is hours since last boot*

---

### `run dir_inbox`

List files in the agent inbox directory.

**Usage:**
```
run dir_inbox
```

**Response:**
```
Volume in drive C has no label.
Directory of C:\AI-SMS-Agent\agent\workspace\inbox
03/09/2026  02:30 PM               123 notes.txt
							 1 File(s)
```

---

### `run dir_outbox`

List files in the agent outbox directory.

**Usage:**
```
run dir_outbox
```

**Response:**
```
Volume in drive C has no label.
Directory of C:\AI-SMS-Agent\agent\workspace\outbox
03/09/2026  03:15 PM               456 response.txt
							 1 File(s)
```

---

## 🤖 Natural Language Commands

If you have OpenAI configured, you can send plain English messages:

**Examples:**

```
SMS: check my inbox
Response: [Lists inbox files]

SMS: what is my CPU usage
Response: Your CPU usage is at 23.5%

SMS: show me files in my projects folder
Response: [Lists C:\Projects directory]

SMS: tell me the system uptime
Response: System has been running for 72.45 hours
```

The AI will:
1. Interpret your natural language request
2. Map it to a safe whitelisted command
3. Execute the command
4. Return a natural language response

**Note:** The AI can only execute commands from the whitelist. It cannot run arbitrary code or access unauthorized paths.

---

## ⚠️ Command Restrictions

All commands are subject to security validation:

- **Path validation**: File paths must be in workspace or allowed directories
- **Extension blocking**: Cannot write `.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js` files
- **Size limits**: Files limited to 10MB
- **Timeout**: Commands timeout after 30 seconds
- **Whitelist only**: Only pre-configured commands can execute

**Blocked operations:**
- Directory traversal (`..`, `.`, absolute paths outside allowed areas)
- Dangerous file extensions
- Commands not in the whitelist
- Arbitrary code execution

---

## 🔧 Adding Custom Commands

To add your own commands, edit `agent/config.json`:

```json
{
	"allowed_commands": {
		"your_command": {
			"description": "What your command does",
			"command": ["cmd", "/c", "your-command-here"],
			"requires_args": false,
			"validate_path": false
		}
	}
}
```

Then restart the agent and use:
```
run your_command
```

See the [README](../README.md#-adding-new-commands) for detailed instructions.

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
| `Sender not allowed` | Your number not in allowlist | Add to `SMS_ACCESS_REQUEST_NUMBERS` |

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
