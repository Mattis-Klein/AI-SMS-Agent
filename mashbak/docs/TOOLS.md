# Tool Reference

Mashbak registers built-in tools in backend only.

## Execution Paths

- Natural language: POST /execute-nl
- Structured tool call: POST /execute

Both paths converge to dispatcher + registry validation before tool execution.

## Tool Groups

System/File tools:
- dir_inbox
- dir_outbox
- list_files
- system_info
- cpu_usage
- disk_space
- current_time
- network_status
- list_processes
- uptime

Email tools:
- list_recent_emails
- summarize_inbox
- search_emails
- read_email_thread

Config tool:
- set_config_variable

## Safety Rules

- Tool names must exist in registry.
- Arguments must pass tool-level validation.
- Allowed-tools and allowed-directories policy is enforced by backend config.
- Bridge and desktop do not execute tools directly.
