# FAQ

## Why do I get Unauthorized from backend?

x-api-key must match AGENT_API_KEY from mashbak/.env.master.

## Why did config update succeed but SMS behavior did not change?

Bridge transport and sender access-control values are startup-loaded. Restart sms_bridge after those changes.

## Why does desktop run without SMS?

Desktop is local UI transport only. SMS requires bridge + Twilio path.

## Does Mashbak support direct /read and /write endpoints?

No. Current API uses /execute and /execute-nl. /run is compatibility wrapper to /execute.

## Why are secrets hidden in traces?

Redaction masks sensitive keys and assignment values before logging.

## Does AI mode bypass tool validation?

No. Tool execution still goes through interpreter, dispatcher, and registry validation.
