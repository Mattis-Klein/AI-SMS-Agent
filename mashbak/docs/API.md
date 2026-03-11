# API Reference

Base URL (default): http://127.0.0.1:8787

Protected endpoints require header:
- x-api-key: <AGENT_API_KEY>

Optional tracing/source headers:
- x-sender
- x-source (desktop or sms)
- x-request-id

## GET /health

Returns backend health and runtime summary.

## GET /tools

Returns all registered tools and descriptions.

## GET /tools/{tool_name}

Returns metadata for one tool.

## POST /execute

Direct tool execution.

Request body:

```json
{
  "tool_name": "list_files",
  "args": {"path": "inbox"}
}
```

## POST /execute-nl

Natural-language execution entry point.

Request body:

```json
{
  "message": "list files in inbox",
  "owner_unlocked": true
}
```

owner_unlocked is used by desktop lock policy flow.

## POST /run (Compatibility)

Legacy compatibility endpoint that forwards to /execute.

## Example: Natural Language Request

```powershell
$h = @{"x-api-key"="<AGENT_API_KEY>";"x-sender"="desktop-user";"x-source"="desktop"}
$b = '{"message":"set MODEL_RESPONSE_MAX_TOKENS to 250"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/execute-nl -Headers $h -ContentType "application/json" -Body $b
```

## Error Conventions

Common error categories returned in payloads include:
- missing_configuration
- validation_failure
- unavailable_tool
- denied_action
- timeout
- execution_failure
