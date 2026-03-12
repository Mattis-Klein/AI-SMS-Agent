# Troubleshooting

Use this file when an SMS fails or no reply arrives.

## 1. Check Twilio First

In Twilio, inspect the incoming message and webhook request.

You want to know:

- Did Twilio receive the SMS?
- Did Twilio call your webhook URL?
- What HTTP status came back?

If Twilio never called your webhook, the problem is outside the local app.

## 2. Check Bridge Health

Verify the bridge is running:

```powershell
curl.exe -i http://127.0.0.1:34567/health
```

Expected: `HTTP/1.1 200 OK`

## 3. Check Agent Health

Verify the agent is running:

```powershell
curl.exe -i http://127.0.0.1:8787/health
```

Expected: `HTTP/1.1 200 OK`

## 4. Check the Bridge Log

Open:

```text
data/logs/bridge.log
```

Look for these stages:

- `incoming_sms`
- `rejected`
- `agent_request`
- `agent_response`
- `reply_ready`
- `reply_sent`

Common outcomes:

- No `incoming_sms`: Twilio never reached the bridge.
- `rejected` with `invalid_twilio_signature`: the auth token, public URL, or Twilio request signature does not match.
- `rejected` with `sender_not_allowed`: the `From` number is not in `SMS_ACCESS_REQUEST_NUMBERS`.
- `agent_request` but no successful `agent_response`: the bridge could not complete the local tool call.

## 5. Check the Agent Log

Open:

```text
data/logs/agent.log
```

Match the `requestId` from the bridge log to `request_id` in the agent log.

Common outcomes:

- `auth_failed`: the API keys do not match.
- `invalid_path`: the requested file path was outside the allowed workspace.
- `read_missing`: a requested file did not exist.
- `command_rejected`: the requested command is not in the allowlist.

## 6. Check the Webhook URL

The Twilio webhook must exactly match:

```text
https://YOUR-CURRENT-URL.ts.net/sms
```

Method must be:

```text
HTTP POST
```

## 7. If You Still Get No Reply

If Twilio shows a 200 from the webhook but your phone gets nothing back, the next likely issue is Twilio outbound message handling or carrier delivery.

At that point, inspect the Twilio message details for the reply attempt.

One important Twilio-specific case:

- Error `30032` means the toll-free number has not been verified for outbound messaging yet.
- In that case, your app can still process inbound SMS correctly, but Twilio will block the reply from reaching your phone.
