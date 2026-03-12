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

Desktop file creation phrases supported:
- create a new file on my desktop called Mashbak
- create a file on my desktop called notes
- make a file on the desktop called todo

Contextual folder follow-ups supported when a real prior folder creation exists in the current session:
- create a file named states in that folder
- put a file in it
- add a file inside that folder
- create a file in the folder we just made

If there is no execution-backed folder context, Mashbak asks for clarification instead of inventing a path.

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
