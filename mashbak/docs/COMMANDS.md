# Command Usage Guide

Mashbak accepts natural language through desktop and SMS.

## Primary Entry Pattern

All user messages flow to backend /execute-nl and are interpreted there.

Examples:
- list files in inbox
- show cpu usage
- summarize my unread emails
- read email thread id 42

## File/System Requests

Typical intents map to tools such as:
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

## Email Requests

Examples:
- list my recent emails
- summarize inbox
- search emails for invoice
- read thread 123

Email tools require configured email variables in mashbak/.env.master.

## Config Through Chat

Accepted forms:
- EMAIL_PASSWORD = app-password
- EMAIL_IMAP_HOST: imap.gmail.com
- set MODEL_RESPONSE_MAX_TOKENS to 250
- set SESSION_CONTEXT_MAX_TURNS to 6

Follow-up in config thread is supported:
- and password is app-password
- and username is me@example.com

## Direct Tool API (Advanced)

Use backend /execute for structured tool calls when needed.

## SMS Access-Control Notes

SMS sender authorization is enforced in bridge before backend forwarding:
- owner sender: forwarded
- access-request sender: fixed response, optional owner notification on keyword
- hershy sender: fixed response
- rejected sender: fixed rejection response
- all other senders: denial response

## Compatibility

POST /run exists for compatibility and forwards to /execute. It is not the preferred integration path.
