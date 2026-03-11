# Available Tools

Complete reference for all built-in tools in AI-SMS-Agent v2.0.

## Tool Index

| Name | Args | Description |
|------|------|-------------|
| [dir_inbox](#dir_inbox) | None | List files in inbox |
| [dir_outbox](#dir_outbox) | None | List files in outbox |
| [list_files](#list_files) | path | List files in directory |
| [system_info](#system_info) | None | System information |
| [cpu_usage](#cpu_usage) | None | Current CPU usage |
| [disk_space](#disk_space) | None | Disk space info |
| [current_time](#current_time) | None | Date and time |
| [network_status](#network_status) | None | Network config |
| [list_processes](#list_processes) | None | Running processes |
| [uptime](#uptime) | None | System uptime |

---

## dir_inbox

**List files in the inbox directory.**

### Usage

**Via Natural Language:**
```
"check my inbox"
"show inbox"
"list inbox"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "dir_inbox", "args": {}}'
```

**Via SMS Bridge Command:**
```
run dir_inbox
```

### Response

```
Volume in drive C is Windows
 Directory of C:\AI-SMS-Agent\agent\workspace\inbox

03/09/2026  02:30 PM    <DIR>          .
03/09/2026  02:30 PM    <DIR>          ..
03/09/2026  02:15 PM           1,024   meeting_notes.txt
03/09/2026  01:45 PM             512   reminder.txt
               2 File(s)          1,536 bytes
```

### Arguments

None required.

### Restrictions

- Fixed to `workspace/inbox` directory
- Cannot list parent directories
- Cannot change directory

---

## dir_outbox

**List files in the outbox directory.**

### Usage

**Via Natural Language:**
```
"check my outbox"
"show outbox files"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "dir_outbox", "args": {}}'
```

### Response

```
Volume in drive C is Windows
 Directory of C:\AI-SMS-Agent\agent\workspace\outbox

03/09/2026  02:30 PM    <DIR>          .
               0 File(s)              0 bytes
```

### Arguments

None required.

### Restrictions

- Fixed to `workspace/outbox` directory
- Cannot list parent directories
- Cannot change directory

---

## list_files

**List files in a specified directory.**

### Usage

**Via Natural Language:**
```
"list files in documents"
"show files in projects"
"what's in the temp folder"
"list my downloads"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "list_files", "args": {"path": "C:\\Users\\owner\\Documents"}}'
```

**Via SMS Bridge Command:**
```
list C:\Users\owner\Documents
```

### Response

```
 Directory of C:\Users\owner\Documents

03/09/2026  02:30 PM    <DIR>          .
03/09/2026  02:30 PM    <DIR>          ..
03/09/2026  02:15 PM           5,120   budget_2026.xlsx
03/09/2026  01:45 PM          10,240   meeting_notes.docx
03/09/2026  12:30 PM             256   todo.txt
               3 File(s)         15,616 bytes
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `path` | string | Yes | Directory path to list |

### Path Restrictions

The path must be:
- Within `workspace/` directory, OR
- Within one of `allowed_directories` from config

**Examples of valid paths:**
- `C:\Users\owner\Documents` (in allowed_directories)
- `inbox` (relative to workspace)
- `C:\Projects` (if in allowed_directories)

**Examples of BLOCKED paths:**
- `/etc/passwd` (not in allowed dirs)
- `../../../windows/system32` (traversal attack)
- `C:\Windows\System32` (system directory)

### Error Cases

```
"Path is not in allowed directories"
  Reason: Path not in workspace or allowed_directories config

"Failed to list directory"
  Reason: Permission denied or path doesn't exist
```

---

## system_info

**Get basic system information.**

Gets OS name, version, system type, and total physical memory.

### Usage

**Via Natural Language:**
```
"tell me about the system"
"what OS are we running"
"system info"
"computer info"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "system_info", "args": {}}'
```

**Via SMS Command:**
```
run system_info
```

### Response

```
OS Name:                   Microsoft Windows 11 Pro
OS Version:                10.0.22621 Build 22621
System Type:               x64-based PC
Total Physical Memory:     16,384 MB
```

### Arguments

None required.

### What It Shows

- Operating system name and edition
- Windows version and build number
- System architecture (x64, x86, etc.)
- Total RAM installed

---

## cpu_usage

**Check current CPU usage percentage.**

Returns the percentage of CPU capacity currently being used.

### Usage

**Via Natural Language:**
```
"what's my CPU usage"
"is the CPU busy"
"check processor"
"show cpu load"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "cpu_usage", "args": {}}'
```

**Via SMS Command:**
```
run cpu_usage
```

### Response

```
CPU Usage: 34.2%
```

### Interpretation

- **0-20%**: Light use (idle or minimal tasks)
- **20-50%**: Moderate use (normal operations)
- **50-80%**: Heavy use (intensive tasks)
- **80-100%**: Very heavy (system may be slow)

### Arguments

None required.

### Notes

- Measurement is instantaneous (single sample)
- May vary between consecutive calls
- High values during backups, installs, or bulk operations

---

## disk_space

**Check disk space on C: drive.**

Shows free space and total capacity of the C: drive.

### Usage

**Via Natural Language:**
```
"how much disk space is left"
"check my storage"
"is the drive full"
"disk space"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "disk_space", "args": {}}'
```

**Via SMS Command:**
```
run disk_space
```

### Response

```
FreeSpace  Size
----------  ----------
234123456  512456789123
```

*(Free bytes and total bytes)*

To convert to human-readable format:
- 234123456 bytes = ~223 GB free
- 512456789123 bytes = ~477 GB total

### Arguments

None required.

### Storage Thresholds

- **>50% free**: Good
- **25-50% free**: Moderate
- **<25% free**: Low (consider cleanup)
- **<5% free**: Critical (system may run slowly)

### Notes

- Sizes shown in bytes (divide by 1GB = 1,073,741,824)
- Only monitors C: drive
- Includes temporary files

---

## current_time

**Get current system date and time.**

Returns the system clock time.

### Usage

**Via Natural Language:**
```
"what time is it"
"current time"
"what's the date"
"tell me the time"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "current_time", "args": {}}'
```

**Via SMS Command:**
```
run current_time
```

### Response

```
03/09/2026 14:30:15
```

Format: `MM/DD/YYYY HH:MM:SS` (24-hour format)

### Arguments

None required.

### Time Zone

- Uses system local time (from Windows registry)
- Not GMT/UTC
- Respects daylight saving time

---

## network_status

**Check network connection and IP configuration.**

Displays network adapter IP addresses.

### Usage

**Via Natural Language:**
```
"check my network"
"what's my IP"
"network status"
"am I connected"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "network_status", "args": {}}'
```

**Via SMS Command:**
```
run network_status
```

### Response

```
   IPv4 Address          : 192.168.1.100
   IPv4 Address          : 10.0.0.50
```

### Interpretation

- First address is usually primary network adapter
- `192.168.x.x` = local network (WiFi/Ethernet)
- `10.x.x.x`, `172.16.x.x` = local network ranges
- `8.8.8.8`, `1.1.1.1` = public addresses (if VPN active)

### Arguments

None required.

### Limitations

- Only shows IPv4 addresses
- Does not test internet connectivity
- Does not show network name or speed

---

## list_processes

**List top running processes by CPU usage.**

Shows the 10 processes using the most CPU time.

### Usage

**Via Natural Language:**
```
"what processes are running"
"show running apps"
"list processes"
"what's using CPU"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "list_processes", "args": {}}'
```

**Via SMS Command:**
```
run list_processes
```

### Response

```
ProcessName                 CPU          WorkingSet
-------------------  ----------  ---------------
chrome                    45.2         1,245,698 KB
explorer                  12.5           876,543 KB
vsCode                     8.3           654,321 KB
python                     5.1           123,456 KB
node                       2.8            98,765 KB
```

### Columns

- **ProcessName**: Application name
- **CPU**: CPU usage in % (cumulative)
- **WorkingSet**: RAM used in KB

### Arguments

None required.

### Limitations

- Shows top 10 processes only
- CPU column reflects total usage across threads
- Memory is current working set (not committed)

### High CPU Processes

If a process consistently uses >50% CPU:
- May indicate heavy workload or busy application
- May indicate malware or runaway loop (rare on local system)

---

## uptime

**Get system uptime in hours.**

Shows how long the system has been running since last reboot.

### Usage

**Via Natural Language:**
```
"when was the system rebooted"
"how long has it been running"
"show uptime"
"system uptime"
```

**Via Direct API:**
```bash
curl -X POST http://localhost:8787/execute \
  -H "x-api-key: your-key" \
  -d '{"tool_name": "uptime", "args": {}}'
```

**Via SMS Command:**
```
run uptime
```

### Response

```
System uptime: 120.5 hours
```

To convert:
- 120.5 hours = 5 days and 0.5 hours
- 24 hours = 1 day
- Divide by 24 to get days

### Interpretation

- **<1 hour**: Recently booted (unusual unless after Windows Update)
- **1-7 days**: Normal (weekly usage)
- **>30 days**: Long uptime (good server stability)
- **0.0 hours**: Just rebooted

### Arguments

None required.

### Notes

- Resets after system restart
- Resets after sleep/hibernation wake on some systems
- Does not count sleep time (depends on power settings)

---

## Tool Input/Output Specification

### Request Format

All tools accept POST requests in this format:

```json
{
  "tool_name": "dir_inbox",
  "args": {}
}
```

With arguments:

```json
{
  "tool_name": "list_files",
  "args": {"path": "C:\\Users\\Documents"}
}
```

### Response Format

Success:

```json
{
  "success": true,
  "tool_name": "system_info",
  "output": "OS Name: Windows 11...",
  "error": null,
  "arguments": {}
}
```

Error:

```json
{
  "success": false,
  "tool_name": "list_files",
  "output": "",
  "error": "Path is not in allowed directories",
  "arguments": {"path": "/etc/passwd"}
}
```

---

## Tool Discovery API

### List All Tools

```bash
curl http://localhost:8787/tools \
  -H "x-api-key: your-key"
```

Response:

```json
{
  "tools": {
    "dir_inbox": {
      "name": "dir_inbox",
      "description": "List files in inbox directory",
      "requires_args": false
    },
    "list_files": {
      "name": "list_files",
      "description": "List files in a specified directory",
      "requires_args": true
    },
    ...
  },
  "count": 10
}
```

### Get Tool Info

```bash
curl http://localhost:8787/tools/cpu_usage \
  -H "x-api-key: your-key"
```

Response:

```json
{
  "name": "cpu_usage",
  "description": "Check CPU usage",
  "requires_args": false
}
```

---

## Error Reference

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Path is not in allowed directories` | Tried to access forbidden path | Use allowed_directories from config |
| `Failed to list directory` | Path doesn't exist or no permission | Check path exists and is readable |
| `Tool not found` | Tool name misspelled or doesn't exist | Check tool name against `/tools` endpoint |
| `Missing required argument: path` | Didn't provide required arg | Include `path` in args |
| `Invalid input` | Wrong data type for argument | Ensure path is a string |
| `Command timeout` | Tool execution exceeded 30 seconds | Try again or optimize query |

---

## Performance Notes

### Execution Times

Tool | Typical Time | Range
-----|--------------|-------
dir_inbox | <100ms | <500ms
dir_outbox | <100ms | <500ms
list_files | <100ms | <2s (large dirs)
system_info | <500ms | <2s
cpu_usage | <100ms | <1s
disk_space | <100ms | <1s
current_time | <10ms | <100ms
network_status | <100ms | <1s
list_processes | <500ms | <2s
uptime | <100ms | <1s

All tools have a 30-second timeout.

### Concurrency

- Multiple simultaneous requests are supported
- Each request is isolated (no cross-contamination)
- Logs maintain request_id for tracing

---

## Best Practices

### Naming Your Requests

When sending natural language, be clear:

✅ Good:
- "show files in documents"
- "what's the CPU usage"
- "list inbox"

❌ Vague:
- "stuff"
- "what up"
- "yo"

### Handling Large Directory List

If a directory has thousands of files, the response may be truncated:

```
Response truncated at 1500 chars. Use direct API for full results.
```

Solution: Use the direct API endpoint instead of SMS for large outputs.

### Checking Before Actions

Before running operations sensitive to state:

```
SMS: "show inbox"
Response: "meeting.txt, notes.txt"

SMS: "list files in documents"  
Response: "resume.pdf, report.docx"
```

This helps avoid accidental changes.

