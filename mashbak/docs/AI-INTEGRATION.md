# AI Integration Guide

Enable natural language SMS with OpenAI.

## What is AI Mode?

By default, the SMS bridge only understands these fixed commands:
- `hello`
- `help`
- `read <path>`
- `write <path> :: <text>`
- `overwrite <path> :: <text>`
- `run <command>`

**AI Mode** lets you send plain English SMS instead:

```
List what's in my inbox
Create a file with my grocery list
What files are in my outbox?
Read my notes and summarize them
```

The OpenAI model:
1. Receives your natural language message
2. Decides which local tools to call (read, write, run)
3. Calls them and interprets results
4. Sends back a natural language response

---

## Prerequisites

1. OpenAI API account (https://platform.openai.com)
2. Valid API key with sufficient credits
3. AI SMS bridge component running

### Check Your API Key

```powershell
# Verify API key format (should start with sk-proj-)
$env:OPENAI_API_KEY
```

### Check Your Credits

1. Go to https://platform.openai.com/account/billing/overview
2. Check "Available balance"
3. Ensure credit is > $0 (or use paid plan)

---

## Step 1: Get OpenAI API Key

### 1.1 Create an Account

1. Go to https://platform.openai.com
2. Click "Sign up"
3. Create account with email
4. Verify email

### 1.2 Generate API Key

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Name it "SMS Agent" (optional)
4. Copy the key (starts with `sk-proj-`)
5. **Save it somewhere secure** - you can't see it again

### 1.3 Set Up Billing (Optional)

For higher rate limits:

1. Go to https://platform.openai.com/account/billing/overview
2. Add payment method
3. Set usage limits to protect from runaway costs

---

## Step 2: Enable AI Mode

### 2.1 Update Configuration

Edit `mashbak/.env.master`:

```env
OPENAI_API_KEY=sk-proj-your-key-here
```

Optional: Choose a different model:

```env
OPENAI_MODEL=gpt-4.1-mini
OPENAI_MODEL=gpt-4
OPENAI_MODEL=gpt-3.5-turbo
```

### 2.2 Restart Bridge

```powershell
cd sms-bridge
npm start
```

Wait for: `Bridge listening on port 34567`

### 2.3 Verify AI is Enabled

Check bridge log for:

```
OpenAI API key configured
OpenAI model: gpt-4.1-mini
```

---

## Step 3: Test AI Mode

Send a text that's NOT a fixed command.

**Example messages:**

```
hello
```
(This is a fixed command, handled directly - no AI)

```
List my inbox
```
(This is natural language - goes to AI)

### Expected Response

The AI will:
1. Interpret "List my inbox"
2. Call agent `run dir_inbox`
3. Get the directory listing
4. Format as natural English
5. Reply with a summary

Response might be:
```
You have 3 files in your inbox:
- notes.txt
- todo.txt  
- meeting-notes.txt
```

---

## How AI Calls Work

### Behind the Scenes

When you send: `Read my inbox and summarize`

1. **Bridge receives SMS**
2. **Bridge checks**: Is this a fixed command? No.
3. **Bridge calls OpenAI**:
   ```json
   {
     "messages": [
       {"role": "user", "content": "Read my inbox and summarize"}
     ],
     "tools": [
       {"name": "read_file", "description": "..."},
       {"name": "write_file", "description": "..."},
       {"name": "run_command", "description": "..."}
     ]
   }
   ```
4. **OpenAI decides**: "I need to run `dir_inbox`"
5. **Bridge calls agent**: `run dir_inbox`
6. **Agent returns**: List of files
7. **OpenAI summarizes** the results
8. **Bridge sends SMS reply**

### Tool Limitations

The AI can **only** call these tools:
- `read_file` - Read files from workspace
- `write_file` - Create/overwrite files
- `run_command` - Run dir_inbox or dir_outbox

It **cannot**:
- Access your Google account
- Access Amazon
- Access any website or API (yet)
- Run arbitrary shell commands
- Modify system files

---

## Pricing

### Cost Per Message

Costs vary by model:

| Model | Cost / Answer | Notes |
|-------|---------------|-------|
| gpt-3.5-turbo | ~$0.001 | Cheapest, less capable |
| gpt-4.1-mini | ~$0.005 | Good balance |
| gpt-4 | ~$0.10+ | Most capable, expensive |

### Example Costs

Assuming $0.005 per message:
- 1 message/day = ~$0.15/month
- 10 messages/day = ~$1.50/month
- 100 messages/day = ~$15/month

### Monitor Usage

```
https://platform.openai.com/account/billing/overview
```

Set alerts for unexpected usage.

---

## Recommended Models

### `gpt-4.1-mini` (Recommended Default)

**Pros:**
- Good balance of cost and capability
- Understands context well
- Handles file operations reliably
- Fast responses

**Cons:**
- More expensive than gpt-3.5-turbo
- Slightly slower

**Use when:** Starting out, general use.

---

### `gpt-4`

**Pros:**
- Most capable
- Best at complex reasoning
- Better at natural language understanding

**Cons:**
- 20x more expensive
- Slower

**Use when:** Complex requests, don't mind cost.

---

### `gpt-3.5-turbo`

**Pros:**
- Cheapest option
- Very fast

**Cons:**
- Less capable
- May misunderstand fuzzy requests
- Less reliable at tool calling

**Use when:** Cost is a concern, simple requests only.

---

## Examples

### Example 1: List Inbox

**You send:**
```
What's in my inbox?
```

**AI does:**
1. Calls `run_command` with `dir_inbox`
2. Gets file listing
3. Formats nicely

**You receive:**
```
You have 3 files in your inbox:
- notes.txt (text file)
- todo.txt (text file)
- meeting.txt (text file)
```

---

### Example 2: Create a File

**You send:**
```
Create a grocery list for me
```

**AI does:**
1. Calls `write_file` to create `inbox/grocery-list.txt`
2. Writes a sample grocery list
3. Returns confirmation

**You receive:**
```
I created a grocery list in inbox/grocery-list.txt with eggs, milk, bread, and more.
```

---

### Example 3: Read and Summarize

**You send:**
```
Read my notes and give me the highlights
```

**AI does:**
1. Calls `read_file` for `inbox/notes.txt`
2. Reads the content
3. Summarizes using OpenAI

**You receive:**
```
Your notes mention:
- Important meeting on March 15
- Follow up with Sarah
- Review budget proposal
```

---

### Example 4: Create from Conversation

**You send:**
```
I need to remember to call the dentist, buy groceries, and book a flight
```

**AI does:**
1. Creates `inbox/reminders.txt`
2. Writes structured list

**You receive:**
```
I created a reminder file with your 3 tasks. Check inbox/reminders.txt.
```

---

## Debugging AI Issues

### AI Not Calling Tools

If the AI responds but doesn't call the tools you expected:

**Likely cause:** The prompt was ambiguous.

**Fix:** Be more specific.

**Instead of:** `Check my stuff`  
**Try:** `List all files in my inbox`

---

### Wrong Tool Called

If AI calls the wrong endpoint:

**Likely cause:** Your request was unclear.

**Fix:** Be explicit about what you want.

**Instead of:** `Show me my folder`  
**Try:** `List the files in inbox`

---

### API Rate Limit Error

If you get an error about rate limits:

**Likely cause:** Too many requests in short time.

**Fix:** Wait a minute, then retry.

**Prevention:** Don't send 100 messages/minute.

---

### Invalid API Key Error

If you get auth error:

**Likely cause:** API key is wrong or expired.

**Fix:**
1. Go to https://platform.openai.com/api-keys
2. Generate a new key
3. Update `mashbak/.env.master`
4. Restart bridge

---

### "Insufficient Credits"

If OpenAI says no credit:

**Fix:**
1. Go to https://platform.openai.com/account/billing/overview
2. Add payment method or credits
3. Wait 5 minutes
4. Retry

---

## Advanced Configuration

### Max AI Tool Rounds

How many times AI can call tools in one message:

```env
AI_MAX_TOOL_ROUNDS=6
```

**Default:** 6 times per message

**Examples:**
- 3: Faster, less complex
- 6: Good balance
- 10: Slower, more flexible

---

### Custom System Prompt (Future)

Not yet implemented, but planned:
- Customize AI personality
- Set tone and style
- Add domain-specific knowledge

---

## Costs & Monitoring

### Real-Time Usage

```
https://platform.openai.com/account/usage/overview
```

Shows usage for current month.

### Set Billing Alerts

Settings → Billing → Usage limits

### Set Hard Limit

To prevent runaway costs:

1. Go to https://platform.openai.com/account/billing/limits
2. Set "Hard limit" to a monthly amount
3. API fails when exceeded (safer than surprise bill)

---

## When AI Mode Isn't Needed

**Use fixed commands instead if:**

- You know exactly what command you want
- Response time is critical (fixed commands are faster)
- You want to minimize costs
- Your network is slow

**Fixed commands are:**
- Instant (no API latency)
- Free (no OpenAI charges)
- More predictable

---

## Future AI Capabilities

Planned (not yet available):

- OAuth integrations (Google, Amazon)
- Web browsing access
- Email reading/sending
- Calendar access
- Custom knowledge bases
- Multi-turn memory

---

## Common Questions (FAQ)

**Q: Does AI see my files?**  
A: Only the files it reads. Doesn't scan your entire disk.

**Q: Can I use a different AI provider?**  
A: Currently OpenAI only. Could add Claude, Gemini later.

**Q: Is there a free tier?**  
A: OpenAI has free $5 trial credits. Then paid.

**Q: Can I disable AI?**  
A: Yes, remove `OPENAI_API_KEY` from `mashbak/.env.master`.

**Q: How do I see AI logs?**  
A: Check `sms-bridge/logs/bridge.log` for `ai_request` and `ai_response` entries.

---

**Last Updated**: March 8, 2026  
**Version**: 1.0

See also: [Environment Config](ENVIRONMENT.md), [Logging Guide](LOGGING.md), [Troubleshooting](legacy/TROUBLESHOOTING.md)
